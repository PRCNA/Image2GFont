# Image2GFont

<img src="frontend/logo.svg" width="80" alt="Image2GFont logo">

将手写图片整理为可人工审核、可修正轨迹的 GFont 字体工程，面向写字机使用场景。

**项目处于实验阶段。** 识字结果与矢量轨迹需要人工核对，尚不能保证任意手写体或复杂交叉笔画都能正确还原。

## 功能

- 批量选择或拖放图片，使用 RapidOCR 进行初步检测与识别。
- Qwen3-VL-4B NF4 提供单字裁切的识字纠错建议，不自动修改框选坐标或确认字符。
- 人工修改字符、调整矩形裁切、记录歧义、确认字符；删除误识别空白框并撤销删除。
- 多张图片汇集为一个字体工程，导出包含多个字符的 `.gfont`。
- 图像预处理、骨架与路径提取、平滑处理，以及独立坐标和笔画编辑工具。
- 三栏桌面工作区、可调整面板比例、独立拆分窗口、九种语言与自定义主题。
- GFont V5 Reader/Writer、格式重建和最小字体验证工具。

## 工作流程

```text
批量图片 → 初步识字与分区 → 人工裁切及字符确认
                              ↓ 可选千问纠错建议
                         字体工程 → 轨迹提取与修正 → GFont V5
```

识字与轨迹提取是不同环节。识字模型给出正确字符，不代表骨架、断笔、交叉连接或轨迹已经正确。本项目优先关注轨迹与原始笔迹的相似度，而非自动还原标准笔顺。

## 从源码运行（Windows）

1. 安装 Python 3.9、Python 3.12 及 Windows `py` 启动器。
2. 运行 `setup_windows.bat` 安装 OCR、视觉与桌面依赖，首次安装需要网络。
3. 可选运行 `download_models.bat` 下载千问模型。千问后端需要兼容的 NVIDIA 驱动与足够显存。
4. 确保已安装 Microsoft Edge WebView2 Runtime。
5. 双击 `Image2GFont.vbs` 或 `start_frontend.bat` 打开独立桌面窗口。

RapidOCR 模型会在首次使用时下载。源码仓库不包含 Python 运行环境、模型权重、用户图片、原始字体样本、生成结果或大型免安装 ZIP。

## 使用

1. 将图片拖入中间图片区，等待识别。
2. 选择框选或右侧文字，核对裁切与字符；空白误识别项可用“删除框选”移除。
3. 对歧义内容记录标注，必要时请求千问建议，最后人工确认。
4. 保存审核进度；“保存字体工程”保存工程，“生成字体”输出字体。

生成文件位置：

```text
artifacts/frontend_export_日期时间/font/generated/candidate.gfont
```

保存审核进度才能保留确认、裁切、标注与删除记录。独立轨迹编辑器的使用见相关文档。

## 目录

| 路径 | 用途 |
| --- | --- |
| `gfont_core/` | GFont V5 数据模型与二进制读写 |
| `vision_core/`、`image_pipeline/` | 图像分割、识字与轨迹处理 |
| `frontend/` | 界面、语言及主题 |
| `desktop_app.py`、`frontend_server.py` | 桌面窗口与本地服务 |
| `ocr_review.py` | 人工审核与进度保存 |
| `font_project.py`、`page_import.py` | 字体集合与页面工程 |
| `coordinate_editor/`、`stroke_editor/` | 坐标与路径人工编辑 |
| `tests/` | 自动测试 |

## 验证与限制

- 最近本地完整测试记录：147 项通过；桌面启动、图标、分离窗口和批量导入做过实测。这不等于已在全新电脑或全部写字机上验证。
- 部分手写图片仍会漏字、多分框或产生错误轨迹；复杂字需要人工修正。
- 千问曾发生显存分配失败，打包不解决此问题。
- 仅支持矩形裁切；尚未提供多边形裁切及画笔、橡皮工具。
- GFont V5 导出限制在 BMP 字符范围；目标软件及机器仍需实际验证。
- 部分历史实验文档引用未公开的本地数据，相关实验无法仅靠仓库复现。

测试入口：

```powershell
.venv-vision\Scripts\python.exe -m unittest discover -s tests
node tests/check_frontend.cjs
node tests/check_drop_import.cjs
```

## 文档

- [界面使用说明](FRONTEND.md)
- [字体工程](FONT_PROJECT.md)
- [人工复核与千问纠错](QWEN_CROP_REVIEW.md)
- [坐标纠正器](COORDINATE_EDITOR.md)
- [笔画修正器](STROKE_EDITOR.md)
- [架构](ARCHITECTURE.md)、[格式约定](SCHEMA.md)、[测试计划](TEST_PLAN.md)

## 第三方依赖与许可

本项目使用 RapidOCR、PyTorch、Transformers、pywebview 等第三方组件；模型与依赖分别受其上游许可约束。本仓库尚未指定项目源码的开源许可证，公开可见不等于授予任意使用、修改和再分发许可。
