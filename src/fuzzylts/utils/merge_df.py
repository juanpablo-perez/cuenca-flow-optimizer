#!/usr/bin/env python3
"""
merge_csv.py –
Merge two CSV files into one, aligning columns even if one file is missing some.
Any columns present in one CSV but not the other will be added with NaN values.

Usage:
    python merge_csv.py <csv1> <csv2> [-o OUTPUT] [--drop-duplicates]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Merge two CSVs, aligning columns even if one file is missing some."
    )
    parser.add_argument("csv1", type=Path, help="First input CSV")
    parser.add_argument("csv2", type=Path, help="Second input CSV")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("merged.csv"),
        help="Output path (default: merged.csv)"
    )
    parser.add_argument(
        "--drop-duplicates", action="store_true",
        help="Drop duplicate rows after merging"
    )
    args = parser.parse_args()

    # Load
    df1 = pd.read_csv(args.csv1)
    df2 = pd.read_csv(args.csv2)

    # Drop any stray index cols named 'Unnamed:*'
    for df in (df1, df2):
        to_drop = [c for c in df.columns if c.startswith("Unnamed")]
        if to_drop:
            df.drop(columns=to_drop, inplace=True)

    # Determine full column set, preserving order from df1 then any extras from df2
    cols1 = list(df1.columns)
    cols2 = [c for c in df2.columns if c not in cols1]
    all_cols = cols1 + cols2

    # Reindex both DataFrames to have all columns (missing → NaN)
    df1 = df1.reindex(columns=all_cols)
    df2 = df2.reindex(columns=all_cols)

    # Merge
    merged = pd.concat([df1, df2], ignore_index=True)
    if args.drop_duplicates:
        merged = merged.drop_duplicates(ignore_index=True)

    # Save
    merged.to_csv(args.output, index=False)
    print(f"✔ Merged {len(df1)} + {len(df2)} rows → '{args.output}' ({len(merged)} total rows)")

if __name__ == "__main__":
    main()
