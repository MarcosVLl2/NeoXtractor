import sys
sys.path.append("/home/codespace/.local/lib/python3.12/site-packages")
from pathlib import Path

def main():
    import argparse

    parser = argparse.ArgumentParser(description="CLI NeoXtractor (no GUI)")
    parser.add_argument("input", type=str, help="Path to .npk file")
    parser.add_argument("-o", "--output", type=str, default="extracted",
                        help="Output folder")

    args = parser.parse_args()

    npk_path = Path(args.input)
    out_dir = Path(args.output)

    print(f"📦 Extracting {npk_path} ...")

    from core.npk.npk_file import NPKFile
    from core.npk.class_types import NPKReadOptions
    import os

    # 创建输出目录
    os.makedirs(out_dir, exist_ok=True)

    # 读取NPK文件
    npk = NPKFile(str(npk_path), NPKReadOptions())

    # 遍历所有条目并保存
    for idx, entry_index in enumerate(npk.indices):
        entry = npk.read_entry(idx)
        filename = entry.filename if entry.filename else f"file_{idx}.{entry.extension}"
        out_path = out_dir / filename
        # 确保父目录存在
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(entry.data)

    print(f"✨ Done! Extracted to: {out_dir}")

if __name__ == "__main__":
    main()