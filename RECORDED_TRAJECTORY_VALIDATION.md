# 记录轨迹逐笔验证

报告：`artifacts/recorded_trajectories_v1/index.html`；结论：同目录 `FINDINGS.md`。

48 份源记录、两种重绘线宽、两种算法，合计 192 次提取。这是基于记录轨迹的合成栅格测试，非纸面照片或中文规范笔顺验证。结果不能与前面的区域数保持指标混为一谈。

本轮新增：

- `image_pipeline/trajectory_metrics.py`：弧长采样、一对一匹配、方向和顺序分开报告。匹配容差为工作图像像素，默认 3/5/5，必须在查看结果前固定。
- `validate_recorded_trajectories.py`：读取冻结的 XML、统一重绘并批量提取，保存完整配对距离和逐图报告。源轨迹不传入提取函数。
- `tests/test_trajectory_metrics.py`：9 项指标测试，全项目 72 项测试通过。

复现到新目录：

```text
python validate_recorded_trajectories.py artifacts/recorded_trajectories_new
```

不需要联网，使用已下载并校验的 `artifacts/trajectory_sources_v1`。输出目录必须不存在。原始数据、已有报告与默认算法不被修改。

细线条件下全字逐笔匹配由 9/48 提高到 12/48；粗线均为 6/48。四个条件下符合记录顺序/方向的全字均为 2/48。未修改参数来美化这些结果，也未输出修复字体。
