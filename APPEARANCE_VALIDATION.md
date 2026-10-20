# 字形外观优先验证

主报告：`artifacts/appearance_v2/index.html`。先评估重绘字形的漏画、多画、墨迹重合和中心线位置，再看重复描画、抬笔与空走。笔顺和分笔匹配保留为辅助诊断，不是主验收门槛。

新增 `image_pipeline/appearance_metrics.py`，包含：

- `render_ink`：方向无关的圆形笔尖并集，整数坐标为像素中心；支持恒定模拟笔宽。
- `compare_ink`：二值/灰度墨迹 IoU、漏画、多画比例，不进行自动配准。
- `geometry`：忽略分组和顺序的中心线集合距离。
- `travel`：落笔、空走和抬笔量，以及 1 像素网格重复边代理。不是墨色或机器时间模型。

`validate_appearance.py` 重新生成统一输入、提取候选、经过 GFont 序列化回读，再按相同笔宽与坐标渲染。未修改默认提取参数或推广保护方案。

```text
python validate_appearance.py artifacts/appearance_new
```

输出目录必须不存在。无需联网，使用 `artifacts/trajectory_sources_v1` 的冻结样本。本轮 81 项测试通过，192 次字体回读通过。细线平均 IoU 约 83%，粗线约 89%，均仅针对这些合成重绘条件。

`appearance_v1` 是统一像素中心约定之前的实验记录，已被 v2 取代。不要把 v1 与 v2 的差异算作字体提取算法的提升。
