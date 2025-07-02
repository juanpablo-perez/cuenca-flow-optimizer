#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import fnmatch

# Nombres de carpetas a excluir por completo
EXCLUDE_DIRS = {
    'Dev',
    'xcshareddata',
    '__pycache__',
    '.git',
    'experiments',
    'experiments_bckp'

}

# Patrones de archivos a excluir
EXCLUDE_FILES = {
    '.DS_Store',
    '*.png',
    '*.gitignore',
    '*.swiftpm',
    '*.colorset',
    '*.pyc'
}

# Nombre del script para que no se imprima a sí mismo
SCRIPT_NAME = os.path.basename(__file__)

def is_excluded(name):
    # Excluir el script
    if name == SCRIPT_NAME:
        return True
    # Excluir carpetas exactas
    if name in EXCLUDE_DIRS:
        return True
    # Excluir por patrón de archivo
    for pat in EXCLUDE_FILES:
        if fnmatch.fnmatch(name, pat):
            return True
    return False

def tree(dir_path, prefix=''):
    """Imprime recursivamente la estructura de árbol."""
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        return

    # Filtrar excluidos
    entries = [e for e in entries if not is_excluded(e)]
    count = len(entries)

    for idx, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        connector = '└── ' if idx == count - 1 else '├── '
        print(prefix + connector + entry)

        if os.path.isdir(path):
            extension = '    ' if idx == count - 1 else '│   '
            tree(path, prefix + extension)

if __name__ == '__main__':
    # Ruta raíz: argumento o directorio actual
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(os.path.abspath(root))
    tree(root)

