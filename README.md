# 多玩存档转 MCWorld

将多玩我的世界盒子导出的 ZIP 存档批量转换为 Minecraft 基岩版 `.mcworld` 文件。自动识别并移除包裹存档的单层目录，以不压缩的 ZIP 格式重新打包。原始 ZIP 文件不会被修改。

## 目录结构

```text
src/
  convert_dw_to_mcworld.py  # 转换逻辑及命令行入口
  dw_mcworld_gui.py         # 图形界面入口
README.md
.gitignore
```

## 使用方法

Windows 用户可直接运行工程根目录的 `多玩存档转MCWorld.exe`，无需安装 Python。EXE 不纳入源码提交，可通过 GitHub Releases 单独发布。

从源码运行需要 Python 3.11 或更高版本，以及 Tkinter（Windows 官方 Python 安装程序通常自带）。运行时无需安装第三方库。在工程根目录执行：

```powershell
python src/dw_mcworld_gui.py
```

选择输入、输出目录后，点击“开始转换”。仅处理输入目录直接包含的 `.zip` 文件，不递归扫描子目录。文件名编码默认使用 `gbk`；遇到乱码或解码错误时，可尝试其他编码。勾选覆盖选项会替换同名输出文件；取消勾选则生成带编号的新文件。

也可使用命令行，输入支持单个 ZIP 或目录：

```powershell
python src/convert_dw_to_mcworld.py "D:/Maps" -o "D:/MCWorld"
```

添加 `--dry-run` 可预览转换，添加 `--overwrite` 可覆盖同名输出，使用 `--metadata-encoding utf-8` 可指定文件名编码。转换不升级存档版本，导入时仍需使用兼容的 Minecraft 基岩版。

## 打包 EXE

在 Windows 的工程根目录执行：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "多玩存档转MCWorld" --distpath . --workpath build --specpath build src/dw_mcworld_gui.py
```

生成的 EXE 位于工程根目录，临时构建文件位于 `build/`。
