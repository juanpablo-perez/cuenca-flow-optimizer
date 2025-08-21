# src/fuzzylts/utils/extract_phase_lanes.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities to extract, per traffic light (TL) and phase, the **upstream lanes**
that feed green movements in a SUMO network (`.net.xml`), with depth measured by
*street segments* (edge **base** changes) rather than by raw edge hops.

Motivation
----------
In SUMO, a logical street is often split into several edges with suffixes like
`EDGE#1`, `EDGE#2`, ...; lane IDs inherit those suffixes as `EDGE#1_0`, etc.
When analyzing corridors feeding a TL phase, counting depth by edges tends to
overestimate how far we propagate upstream. Instead, we count depth only when
the **base** of the edge changes (substring before the first `#`).

Key behavior
------------
- For each TL and phase, identify links that are green (`'G'`/`'g'`).
- Starting from each green link's `fromEdge`, traverse upstream following only
  straight connections (`dir='s'`).
- Depth is incremented only when the upstream edge belongs to a **different**
  base (different street) than the child edge.
- Optionally stop traversal when encountering another (different) TL on the
  upstream connection (`stop_at_tl=True`) — useful for dense networks.
- Internal edges (IDs starting with `':'`) are ignored in the output.
- Returns a mapping: `{tl_id: {phase_index: [lane_id, ...]}}` with lane IDs
  sorted for determinism.

Complexity
----------
Uses a bounded reverse BFS controlled by `max_depth`.
Overall ~O(E + C), where `E` = number of edges/lanes, `C` = connections.

Notes
-----
- This module uses only Python stdlib and a small project helper to load XML.
- XML structure assumed per SUMO's `net_file.xsd`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, Final, List, Set, Tuple

import xml.etree.ElementTree as ET

from fuzzylts.utils.io import load_xml_root  # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# Constants & type aliases
# ─────────────────────────────────────────────────────────────────────────────

# Accepted TL phase states considered "green".
GREEN_CHARS: Final[Set[str]] = {"G", "g"}

# SUMO 'dir' attribute value used to restrict traversal to straight-through flows.
STRAIGHT: Final[str] = "s"

# Link tuple for TL-controlled connections:
#   (linkIndex, fromEdge, fromLaneIndex, toEdge)
Link = Tuple[int, str, int, str]

# Reverse-graph item: (fromEdge, dir, tl_id_or_empty)
UpstreamItem = Tuple[str, str, str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def edge_base(edge_id: str) -> str:
    """Return the base (street) of an edge id: substring before the first `#`.

    Examples
    --------
    >>> edge_base("337277951#3")
    '337277951'
    >>> edge_base("49217102")
    '49217102'  # no '#', returns full id
    """
    i = edge_id.find("#")
    return edge_id[:i] if i != -1 else edge_id


def is_internal_edge(edge_id: str) -> bool:
    """Whether an edge is internal (SUMO-generated, starts with ':')."""
    return edge_id.startswith(":")


def build_edge_lanes(root: ET.Element) -> Dict[str, List[str]]:
    """Build a mapping `edge_id -> [lane_id, ...]`."""
    edge_lanes: Dict[str, List[str]] = {}
    for edge in root.findall("edge"):
        eid = edge.get("id")
        if not eid:
            continue
        # Note: pedestrian/bike lanes may appear; filter upstream if needed.
        lanes = [ln.get("id") for ln in edge.findall("lane") if ln.get("id")]
        edge_lanes[eid] = lanes
    return edge_lanes


def build_connections(
    root: ET.Element,
) -> Tuple[Dict[str, List[Link]], Dict[str, Set[UpstreamItem]]]:
    """Parse `<connection>` elements and build:

    - `tl_links`   : `tl_id -> list[ (linkIndex, fromEdge, fromLaneIndex, toEdge) ]`
                     (links are sorted by linkIndex for stable order)
    - `upstream_of`: `toEdge -> set[ (fromEdge, dir, tl_id_or_empty) ]`
                     (reverse graph for BFS from child → parents)

    Returns
    -------
    tl_links, upstream_of
    """
    tl_links: Dict[str, List[Link]] = defaultdict(list)
    upstream_of: Dict[str, Set[UpstreamItem]] = defaultdict(set)

    for conn in root.findall("connection"):
        f = conn.get("from")
        t = conn.get("to")
        if not f or not t:
            continue

        d = conn.get("dir", "")  # direction: 's', 'l', 'r', ...
        tl = conn.get("tl", "")  # TL id (may be empty when not TL-controlled)

        upstream_of[t].add((f, d, tl))

        tl_id = conn.get("tl")
        if tl_id is not None:
            # Record TL-controlled links with stable ordering by linkIndex.
            try:
                link_idx = int(conn.get("linkIndex", "-1"))
            except ValueError:
                link_idx = -1
            try:
                from_lane_idx = int(conn.get("fromLane", "0"))
            except ValueError:
                from_lane_idx = 0
            tl_links[tl_id].append((link_idx, f, from_lane_idx, t))

    # Ensure deterministic ordering by linkIndex for each TL.
    for tl_id in tl_links:
        tl_links[tl_id].sort(key=lambda x: x[0])

    return tl_links, upstream_of


def build_tl_programs(root: ET.Element) -> Dict[str, List[str]]:
    """Build TL programs from `<tlLogic>`, collecting phase `state` strings.

    Returns
    -------
    Dict[str, List[str]]
        Mapping `tl_id -> [state, ...]` where each state is a binary mask string.
    """
    tl_programs: Dict[str, List[str]] = {}
    for tll in root.findall("tlLogic"):
        tid = tll.get("id")
        if not tid:
            continue
        states = [ph.get("state", "") for ph in tll.findall("phase")]
        tl_programs[tid] = states
    return tl_programs


def collect_upstream_edges_by_street(
    start_edge: str,
    upstream_of: Dict[str, Set[UpstreamItem]],
    max_depth: int,
    stop_at_tl: bool,
    current_tl: str,
) -> Set[str]:
    """Reverse BFS measuring depth by **street changes** (edge-base transitions).

    Expansion rules
    ---------------
    - Only follow connections with `dir='s'` (straight).
    - If `stop_at_tl` is True, do not cross an upstream connection that
      is controlled by a TL different from `current_tl`.
    - Depth is incremented only when `edge_base(pred) != edge_base(child)`.
    - Expansion stops when `depth >= max_depth`.

    Returns
    -------
    Set[str]
        The set of visited upstream **edge ids**.
    """
    start_base = edge_base(start_edge)
    visited_edges: Set[str] = set()
    # Queue holds (edge, depth, child_base).
    q: Deque[Tuple[str, int, str]] = deque([(start_edge, 0, start_base)])

    while q:
        edge, depth, child_base = q.popleft()
        if edge in visited_edges:
            continue
        visited_edges.add(edge)

        # Stop expanding parents if we've reached the maximum depth.
        if depth >= max_depth:
            continue

        for pred, dir_attr, tl_attr in upstream_of.get(edge, ()):
            # Only straight movements contribute to the "approach corridor".
            if dir_attr.lower() != STRAIGHT:
                continue

            # Optionally stop at foreign TLs to constrain corridors.
            if stop_at_tl and tl_attr and tl_attr != current_tl:
                continue

            pred_base = edge_base(pred)
            # Same base → does not consume depth; different base → +1 depth.
            next_depth = depth if pred_base == child_base else depth + 1

            if next_depth <= max_depth and pred not in visited_edges:
                q.append((pred, next_depth, pred_base))

    return visited_edges


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_phase_lanes(
    net_path: str | Path,
    max_depth: int = 0,
    stop_at_tl: bool = False,
) -> Dict[str, Dict[int, List[str]]]:
    """Extract a mapping of lanes per TL and phase, traversing upstream corridors
    with depth measured by **street changes**.

    Parameters
    ----------
    net_path : str | Path
        Path to the SUMO `.net.xml` (or `.net.xml.gz`) file.
    max_depth : int, optional (default: 0)
        Depth measured in **street changes**:
          - 0 → only the street immediately feeding the TL phase
          - 1 → include one previous street upstream (and all of its contiguous
                same-base segments), etc.
    stop_at_tl : bool, optional (default: False)
        If True, stop upstream traversal at connections controlled by a
        different TL than the one being analyzed.

    Returns
    -------
    Dict[str, Dict[int, List[str]]]
        `{ tl_id: { phase_index: [lane_id, ...] } }` with lanes sorted
        deterministically.

    Notes
    -----
    - Internal edges (IDs starting with `':'`) are excluded from the result.
    - If your network includes pedestrian/bicycle lanes and you want to exclude
      them, filter by edge type or lane permissions in `build_edge_lanes()`.
    """
    root = load_xml_root(path=str(net_path))
    edge_lanes = build_edge_lanes(root)
    tl_links, upstream_of = build_connections(root)
    tl_programs = build_tl_programs(root)

    result: Dict[str, Dict[int, List[str]]] = {}

    for tl_id, states in tl_programs.items():
        links = tl_links.get(tl_id, [])
        if not links:
            # No TL-controlled connections registered for this TL.
            continue

        phase_map: Dict[int, List[str]] = {}
        for phase_idx, state in enumerate(states):
            lanes_accum: Set[str] = set()

            # Iterate TL links in stable linkIndex order.
            for link_idx, from_edge, _from_lane_idx, _to_edge in links:
                # Defensive: malformed or mismatched state length.
                if link_idx < 0 or link_idx >= len(state):
                    continue
                # Only gather lanes for green (G/g) movements.
                if state[link_idx] not in GREEN_CHARS:
                    continue

                upstream_edges = collect_upstream_edges_by_street(
                    start_edge=from_edge,
                    upstream_of=upstream_of,
                    max_depth=max_depth,
                    stop_at_tl=stop_at_tl,
                    current_tl=tl_id,
                )

                # Add all lanes for all visited upstream edges (exclude internal edges).
                for e in upstream_edges:
                    if is_internal_edge(e):
                        continue
                    for lid in edge_lanes.get(e, []):
                        lanes_accum.add(lid)

            if lanes_accum:
                # Sort for reproducible outputs across runs.
                phase_map[phase_idx] = sorted(lanes_accum)

        if phase_map:
            result[tl_id] = phase_map

    return result


__all__ = [
    "extract_phase_lanes",
    "edge_base",
    "is_internal_edge",
    "build_edge_lanes",
    "build_connections",
    "build_tl_programs",
    "collect_upstream_edges_by_street",
]
