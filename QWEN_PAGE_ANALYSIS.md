# Qwen 页面分析与 Paddle 复核

此文档以下内容为历史实验记录，界面路线已更新为 RapidOCR 切割、千问单字纠错、人工歧义标注。当前用法见 [QWEN_CROP_REVIEW.md](QWEN_CROP_REVIEW.md)，不再提供千问整页定位入口。

当前默认方案：RapidOCR 切割，Paddle 提供识字复核建议。Qwen 保留为手动选择的实验选项，不接管默认切割。

本地运行结果与已知问题见 QWEN_VALIDATION.md。密集手写页仍有明显漏检和过窄框，此入口为实验选项。

入口：双击 `start_visual_project.bat` 或 `start_page_analysis.bat`，选择 Qwen 或 RapidOCR，然后选择一张或多张图片。分析完成后打开原有单字审核界面。候选框可重画，字符需人工确认；“本地模型识字建议”继续使用 PaddleOCR-VL。确认后的字符再汇总到字体工程。原来的 `start_ocr_review.bat` 仍能直接打开已有审核结果。

Qwen 处理进程退出后才打开审核，避免 Qwen 与 Paddle 同时常驻 8GB 显存。RapidOCR 仍可切换使用；未宣布 Qwen 的定位精度优于 RapidOCR。

## 模型与边界

- 基础模型：Qwen3-VL-4B-Instruct。
- 量化发布者：Unsloth，仓库 `unsloth/Qwen3-VL-4B-Instruct-bnb-4bit`。
- 固定版本：`79cd853d0bc98bb0d67f865123eb49ef8985c2ec`。
- 格式：bitsandbytes NF4，双重量化；视觉模块等按发布配置保持高精度。这不是 GGUF Q4_K_M，也不是所有参数都压为 4 位。
- 下载约 3.5 GB；使用数据文件与 Transformers 内置实现，不执行模型仓库 Python 代码。provenance.json 记录文件 SHA256，权重与发布者 LFS 哈希核对。
- 默认工作图像最多 786432 像素，输出上限 4096 token，一次处理一张图。密集页面可能漏字或达到输出上限，需分区重试；当前没有自动分块。
- 界面勾选“密集页面”将输出上限提高到 8192 token；这只增加输出容量，不保证完整检测。候选数组上限显式设为 1000，避免格式库的默认 20 项限制。
- 提示模型输出 0～1000 归一化单字框，映射回 EXIF 校正后的原图。它们只是候选框，没有进行笔迹边界自动精修；必须检查长笔画与邻字。
- 不编造置信分数：score 为 null，界面显示“未提供”。模型输出不自动绑定 Unicode，不自动改写轨迹。
- 使用 LM Format Enforcer 限制 JSON 结构，单字符长度和坐标合法性在解析时再校验。格式约束不保证识字准确性。适配器使用该库核心接口以兼容 Transformers 5；加载时显式排除 model.visual 的量化，保留发布权重中的高精度视觉层。
- 原图复制后只读，逐页保留原始模型文本、解析拒绝项、坐标叠加图、用时和 PyTorch 显存峰值。显存峰值不等于整个进程的总显存。
- 截断或非法 JSON 整页失败；非法候选框单独拒绝。失败页面不会使用伪造结果填补。

## 命令行

```powershell
.venv-vision\Scripts\python.exe -m vision_core.qwen_page image.jpg --output artifacts/new_qwen_run
.venv-vision\Scripts\python.exe ocr_review.py --results artifacts/new_qwen_run/results.json
```

输出目录必须是新目录；结果采用现有审核数据结构。自动测试验证结构和人工确认边界，不能代替手写检测精度或桌面按钮实测。

## 来源

- https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
- https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-bnb-4bit
- https://huggingface.co/docs/bitsandbytes/main/en/installation
