#!/bin/bash
# 一键安装 NeoXtractor 所需依赖和工具
set -e

# Python 环境建议 >=3.12
if ! python3 --version | grep -q "3.12"; then
  echo "建议使用 Python 3.12 及以上版本！"
fi

# 安装 Python 依赖（优先使用 uv/pip）
if command -v uv &> /dev/null; then
  uv sync
else
  pip install -r requirements.txt || pip install -r pyproject.toml
fi

# 安装系统依赖
sudo apt update
sudo apt install -y imagemagick lz4 zstd python3-pip

# 安装 astcenc（如需批量转换 .astc）
if ! command -v astcenc &> /dev/null; then
  echo "正在安装 astcenc..."
  wget https://github.com/ARM-software/astc-encoder/releases/download/v4.4.0/astcenc-linux-x64 -O astcenc
  chmod +x astcenc
  sudo mv astcenc /usr/local/bin/
fi

echo "环境准备完成！可直接运行主脚本。"
