# Qwen 页面分析接入验证

日期：2026-10-11。

## 交付

start_visual_project.bat / start_page_analysis.bat：选择 Qwen NF4 或 RapidOCR，选择图片，分析结束后进入现有审核界面。可重画字符框，调用 PaddleOCR-VL 复核；显示初步识别与复核是否一致，不自动确认或改写字库。start_ocr_review.bat 仍可打开以前的结果。

模型使用 Unsloth 的 Qwen3-VL-4B-Instruct-bnb-4bit 固定版本，权重哈希已核对；252 个四位线性层，视觉塔保留高精度。详情见 QWEN_PAGE_ANALYSIS.md。

## 本地 GPU 实测

| 页面 | Qwen 有效候选 | RapidOCR 原有候选 | Qwen 用时 | PyTorch 峰值分配 |
|---|---:|---:|---:|---:|
| 青色字稀疏页 04 | 12 | 12 | 22.675 秒 | 3.72 GiB |
| 青色字稀疏页 06 | 12 | 12 | 22.105 秒 | 3.72 GiB |
| 红格密集页 07 | 90 | 101 | 230.875 秒 | 3.96 GiB |

候选数量不是准确率；RapidOCR 候选也有噪声，不能用 90/101 计算召回率。时间为当前机器上的单页处理，不含初始化，不是公平速度基准。密集页本次输出上限为 8192 token，实际生成 3182 token；有 1 项因不是单字符被拒绝。

人工查看叠加图：稀疏页能覆盖主要字符，但部分框偏紧且有错字；密集页明显存在漏检、偏移和过窄框，可能切掉笔画。Qwen 暂不具备在本项目中无条件替代 RapidOCR 的质量证据，保留可切换实验入口。

测试页来自已有资料，不是独立留出测试集。没有完整人工框真值，不公布检测准确率。

## Paddle 复核

三个实际 Qwen 裁切：右→右、京→京；第三个 Qwen 给出“燕”，Paddle 给出“坐”，两者不一致，均不得据此自动确认。复核进程可运行不等于识字正确。

## 检查与限制

- 131 项 Python 测试通过，包括超过 20 个候选的格式约束回归测试；启动脚本对应 Python 模块编译检查通过。
- 实际结果可由 OCRReview 读取，原图复制件 SHA256 一致，自动确认数量为 0。
- 桌面按钮交互尚未实测，不能声称完整 GUI 验收通过。未生成新的正式字库、未进行奎享及写字机验收。
- 格式库默认数组上限 20 曾造成密集页结果截断，现已显式设为 1000。旧 artifacts/qwen_page_validation_final 中第 3 页 20 项结果已作废；前两页有效。密集页请使用 artifacts/qwen_dense_validation_v2。
- 原先加载兼容性和 JSON 输出错误的实验文件保留供诊断，不作为成功结果。

## 结果位置

- 汇总：artifacts/qwen_validation_summary.json
- 稀疏页：artifacts/qwen_page_validation_final（仅前两页为本次有效评估）
- 密集页修正版及对照图：artifacts/qwen_dense_validation_v2/backend_comparison.png
- Paddle 实测：artifacts/qwen_paddle_review_final/recognition.json

下一步优先改善密集页面的分块与候选框边界，再进行独立图片评估；不将文字识别成功当作笔迹轨迹质量通过。
