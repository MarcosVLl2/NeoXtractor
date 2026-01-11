#!/usr/bin/env python3
from pathlib import Path
import argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Batch extract NPK files into a single output folder")
    parser.add_argument("npk_files", nargs='+', help="Paths to .npk files to extract")
    parser.add_argument("-o", "--output", default="extracted2", help="Output base folder")
    args = parser.parse_args()

    # Ensure local site-packages path is available if needed (helps some web environments)
    site_user = str(Path.home() / ".local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")
    if site_user not in sys.path:
        sys.path.append(site_user)

    # Import here so script fails only after args parsed
    try:
        from core.npk.npk_file import NPKFile
        from core.npk.class_types import NPKReadOptions
    except Exception as e:
        print("Failed to import project modules:", e)
        print("Make sure you run this script with the same python that has the project's deps installed.")
        raise

    out_base = Path(args.output)
    out_base.mkdir(parents=True, exist_ok=True)

    for npk_path in args.npk_files:
        npk_path = Path(npk_path)
        if not npk_path.exists():
            print(f"File not found: {npk_path}")
            continue

        subdir = out_base / npk_path.stem
        subdir.mkdir(parents=True, exist_ok=True)

        print(f"📦 Extracting {npk_path} -> {subdir} ...")
        try:
            npk = NPKFile(str(npk_path), NPKReadOptions())
        except Exception as e:
            print(f"Failed to open {npk_path}: {e}")
            continue

        for idx in range(len(npk.indices)):
            try:
                entry = npk.read_entry(idx)
            except Exception as e:
                print(f"  [!] Failed to read entry {idx}: {e}")
                continue

            filename = entry.filename if getattr(entry, 'filename', None) else f"file_{idx}.{entry.extension}"
            out_path = subdir / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(out_path, 'wb') as f:
                    f.write(entry.data)
            except Exception as e:
                print(f"  [!] Failed to write {out_path}: {e}")

        print(f"✨ Done {npk_path} -> {subdir}")

    print(f"All finished. Outputs are under: {out_base}")

if __name__ == '__main__':
    main()
