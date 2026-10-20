# Image2GFont 视觉项目 V2

## 结构

视觉流程分成三个独立阶段：

1. 识字建议：现有 PP-OCRv5 负责整页候选检测；PaddleOCR-VL-1.6 负责选定裁切的第二份文字建议。
2. 笔迹分割：从原始彩色裁切生成可见的前景掩膜，不使用识别出的文字重画字形。
3. 轨迹生成：从掩膜生成中心线候选，映射至 GFont 坐标。所有结果保持 candidate，不能代表机器书写质量已验证。

`vision_core/recognition.py`、`segmentation.py`、`trajectory.py` 分别实现上述三层。旧版图像提取保留；未指定 V2 模式的旧页面工程继续走旧流程。

## 使用审核工具

双击 `start_ocr_review.bat`，选择已有 `results.json`。

- 选择图片、单字，检查裁切边界。
- 选择处理模式：auto（自动建议）、dark（浅底深字）、light（深底亮字）、cyan（青色笔迹）、dark_red_grid（深字与红格线）。
- 点击“预览笔迹掩膜”。白色是将保留的区域，必须观察细笔画、断裂和格线残留。
- “本地模型识字建议”使用独立 Python 环境运行 PaddleOCR-VL，不上传图片；结果显示在状态栏，不自动填字、不自动确认。切换候选后返回的旧建议会注明所属裁切已切换。
- 核对字符和框后点击确认。每个确认字保存所选模式，后续更改全局模式不会覆盖其记录；要改变已确认字的模式，请重新确认该字。
- “保存审核进度”保留确认和模式；“生成并纠正字体”保存多图片工程并打开轨迹纠正器。

识字耗时可能较长，单次任务上限 300 秒；每次运行保留裁切、识别 JSON 和 runtime.log。置信度未校准，因此模型建议的 confidence 为 null，不能与 PP-OCR 分数作数值比较。

## 参数与实际限制

- 工作图最长边统一为 384 像素；低分辨率图片会插值放大，只是统一处理尺度，不恢复消失的笔迹。
- 默认最小连通域 3 个工作像素，对比阈值 10；深浅背景分别处理。
- 青色使用颜色差分排除白色格线，并仅对很短的颜色断裂作 3×3 闭运算。仍可能误连接相邻笔迹。
- 红格线模式排除偏红像素及其一圈邻域；交叠笔迹可能同时丢失。
- 不自动删除骨架短分支，避免把真实短笔画当毛刺删除。
- 同色格线尚不能可靠去除；模糊、交叉、粘连仍需人工纠正。

自动模式是启发式选择，不是训练过的场景分类器。U-Net/SAM 与 Qwen 尚未部署；仅在当前分割仍不稳定且有标注数据后再评估，不能宣称已具备训练后的泛化能力。

## 环境和复现

轨迹处理仍使用原 Python 环境；PaddleOCR-VL 使用 `.venv-vision` 的 Python 3.12、GPU PyTorch 和 Transformers，依赖版本见 `requirements-vision-lock.txt`。原 `.venv-ocr` 未升级。

模型来自官方 `PaddlePaddle/PaddleOCR-VL-1.6`。下载固定版本和文件哈希记录在模型目录 provenance.json；只使用 Transformers 内置实现，不执行远程模型 Python 文件。

```powershell
python font_project.py export path/to/font_project.json artifacts/new_export --vision-mode auto
.venv-vision\Scripts\python.exe -m vision_core.recognition path/to/crop.png --output artifacts/new_recognition
python validate_vision_v2.py artifacts/e2e_0928/font_project/font_project.json artifacts/new_comparison
python -m unittest discover -s tests -q
```

输出目录必须不存在。单字模式优先于命令行默认模式。新版导出保留每字 crop、mask、处理参数、警告和坐标映射，便于复现。

## 已有真实样本对照

`artifacts/vision_v2_real_v3/comparison.png` 使用上一轮八字失败样本，对比原图、分割掩膜、实际导出轨迹。黑底青色字及“技”较旧版明显改善；“红”等低清字仍有断笔，不能判为全部通过。

这八字参与了参数调试，不能充当独立测试集。识字模型验证、完整桌面交互以及奎享兼容性应分别记录，不能互相替代。


## 完成本地验证（2026-09-29）

PaddleOCR-VL 已安装并在本机 GPU 实际推理；参数约 0.906B。11 个单字裁切中，PaddleOCR-VL 与关闭检测后的 PP-OCRv5 均为 10/11，不能据此宣称新模型更准。报告见 artifacts/vision_recognition_validation/REPORT.md。

启动入口也可用 start_visual_project.bat。完整窗口按钮交互与奎享实测尚未完成。
