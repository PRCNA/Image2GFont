# 可选的分离结构保护

实现位置：`image_pipeline/component_guard.py`。当前尚未替换默认 `preprocess`，不改变已有照片实验结果或编辑器行为。

`preserve_components(reference, candidate)` 接收两个同尺寸二维布尔掩码，返回新掩码及诊断字段。reference 需要调用方明确提供。算法从参照区域逐步接纳候选像素，使用八邻域，拒绝会连接不同参照区域的像素；所有参照像素保留。增长按离参照的距离、行列顺序确定，结果可复现。

`preprocess_preserving_components(gray, reference_mask, **parameters)` 先调用原有预处理，再执行保护。它不会擅自为照片选择“通用”阈值。

保护保证仅针对参照的连通块。已有断笔、噪点和遗漏的浅色笔画不能由该保证解决。同一连通块内部的孔洞和抬笔位置不受保证，禁止把 `result_components == seed_components` 当作字形正确的判据。

## 复现本轮比较

```text
python compare_component_guard.py ../../work/handwriting_download artifacts/component_guard_new
```

下载缓存沿用上一轮，无须联网。输出目录必须不存在。脚本先写入固定样本及算法校验清单，再执行 192 张图的两种方案，保存逐图指标和对照图。新字符与上一轮不重合，但仍属同一数据源。

结果见 `artifacts/component_guard_v1/index.html` 和 `FINDINGS.md`：区域合并由 35 张降至 0，仍有 40 张孔洞数变化；57 项单元测试通过。该方案继续保持可选实验状态。
