#!/usr/bin/env python3
"""
Scan given extracted folders for likely image resources and prepare conversion commands.

Usage:
  python3 tools/collect_images.py --inputs extracted extracted2 --out images

This script will:
 - copy already-standard images (png,jpg,bmp,tga) to the output folder preserving relative paths
 - detect probable image binaries (dds,astc,pvr,cbk,gim) and write recommended conversion
   commands into `convert_commands.sh` for manual execution
 - attempt some automatic conversions when common tools are present (ImageMagick, astcenc, PVRTexToolCLI)

Note: conversions may require external tools installed in the environment.
"""

import argparse
from pathlib import Path
import shutil
import sys
import subprocess

IMG_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.gif'}
STD_EXTS = IMG_EXTS

MAGIC_MAP = [
    (b"\x89PNG\r\n\x1a\n", 'png'),
    (b"\xff\xd8\xff", 'jpeg'),
    (b"DDS ", 'dds'),
    (b"PVR", 'pvr'),
    (b"\x13\xAB\xA1\x5C", 'astc'),
]


def detect_magic(path: Path):
    try:
        with open(path, 'rb') as f:
            head = f.read(16)
    except Exception:
        return None
    for sig, name in MAGIC_MAP:
        if head.startswith(sig) or sig in head:
            return name
    return None


def ensure_parent(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', nargs='+', default=['extracted', 'extracted2'])
    parser.add_argument('--out', default='images')
    parser.add_argument('--commands', default='convert_commands.sh')
    args = parser.parse_args()

    inputs = [Path(p) for p in args.inputs]
    out_base = Path(args.out)
    out_base.mkdir(parents=True, exist_ok=True)

    commands = []
    copied = 0
    detected = {}

    for root in inputs:
        if not root.exists():
            print(f"Skipping missing input: {root}")
            continue

        for p in root.rglob('*'):
            if not p.is_file():
                continue

            rel = p.relative_to(root)
            out_path = out_base / root.name / rel

            ext = p.suffix.lower()
            if ext in STD_EXTS:
                ensure_parent(out_path)
                shutil.copy2(p, out_path)
                copied += 1
                continue

            # Magic detection
            kind = detect_magic(p)
            if kind:
                detected.setdefault(kind, []).append((p, out_path))
            else:
                # fallback by extension hints
                if ext in ['.dds', '.pvr', '.astc', '.cbk', '.gim']:
                    detected.setdefault(ext.lstrip('.'), []).append((p, out_path))

    # Prepare conversion commands
    # DDS -> png via ImageMagick
    if 'dds' in detected:
        for src, dst in detected['dds']:
            out_png = dst.with_suffix('.png')
            commands.append(f"magick convert \"{src}\" \"{out_png}\"")

    # PVR -> png via PVRTexToolCLI
    if 'pvr' in detected:
        for src, dst in detected['pvr']:
            out_png = dst.with_suffix('.png')
            commands.append(f"PVRTexToolCLI -i \"{src}\" -o \"{out_png}\"")

    # ASTC -> png via astcenc (try common block sizes)
    if 'astc' in detected:
        block_sizes = ['4x4','5x5','6x6','8x8','12x12']
        for src, dst in detected['astc']:
            out_png = dst.with_suffix('.png')
            # write multiple candidate commands for user to try
            for bs in block_sizes:
                commands.append(f"astcenc -d \"{src}\" \"{out_png}\" {bs} -medium -silent || true")

    # CBK/GIM - unknown container, suggest inspection
    for key in ['cbk', 'gim']:
        if key in detected:
            for src, dst in detected[key]:
                commands.append(f"# Inspect {src} - custom container. Try opening in a hex editor or search repo converters")

    # write commands to file
    cmdfile = Path(args.commands)
    with open(cmdfile, 'w', encoding='utf-8') as f:
        f.write('#!/bin/bash\n')
        f.write('set -e\n')
        for c in commands:
            f.write(c + '\n')

    # Make executable
    try:
        cmdfile.chmod(0o755)
    except Exception:
        pass

    print(f"Copied {copied} standard image files into {out_base}")
    print(f"Detected categories: {', '.join(detected.keys()) if detected else 'none'}")
    print(f"Conversion commands written to: {cmdfile}")
    print("Review and run the script to perform conversions. Some commands may require external tools (ImageMagick, astcenc, PVRTexToolCLI).")


if __name__ == '__main__':
    main()
