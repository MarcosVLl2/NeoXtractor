# 一键运行指南

## 环境准备

1. 拖入你要解包的 NPK 文件（如 chr.part.2a.npk 等）到本项目根目录。
2. 运行一键安装脚本：

```bash
bash setup_env.sh
```

## 批量解包 NPK 文件

假如你已将所有 NPK 文件拖入项目根目录，直接运行：

```bash
python3 batch_extract.py chr.part.*.npk
```

所有资源将自动解包到 `extracted2/` 文件夹。

## 结果说明
- 解包后的文件都在 `extracted2/` 目录下。
- 你可以用 `grep`、`find` 等命令在解包目录中搜索、处理资源。

## 依赖问题
如遇依赖缺失或 Python 版本不符，请优先运行 `setup_env.sh`。

## 进阶用法
- 支持拖入任意 NPK 文件，自动批量解包。
- 支持自定义输出目录：
  ```bash
  python3 batch_extract.py chr.part.*.npk -o my_output_folder
  ```

## 问题反馈
如遇问题请联系项目维护者或在 GitHub 提 issue。
