# Image2GFont 架构 · Phase 0

节点编辑扩展：stroke_editor.model新增move_point/insert_point/delete_point/add_path；UI拖动和补画使用临时预览，仅在松开或“完成补画”时写入一次历史。闭环首尾节点同步移动，取消不改变字形；复用既有JSON点列结构，无需迁移旧记录。

笔画修正阶段：stroke_editor/model.py按字形保存独立候选副本与confirmed状态，连接/断开/删除/反转/排序均为可撤销修改；app.py复用坐标画布与配准读取，但关闭全字拖动变换，改为路径/节点选择。结构修正和坐标变换保持分离。原始字体不修改，新增连接在界面预览确认后执行。

坐标纠正器实现：coordinate_editor/model.py 提供不可变Transform和EditorSession；app.py为Tkinter原生桌面界面，依赖Pillow作参考图配准显示。用户已授权本轮最小GUI范围，取代此前“暂不做GUI”对本工具的限制。全字体共享变换，不修改源Glyph；导出复用Reader/Writer并逐点验证float32。详细范围见COORDINATE_EDITOR.md。

2026-09-23：新增 test_photo_coordinates.py，针对用户四字照片做人工区域裁切、统一参数对照、四种坐标变换和18字形诊断字体。未建立交互编辑器。core.preprocess 新增可选 max_hole_area，旧默认值保持兼容，新多笔画流程仅填微小孔洞。测试键A～P/0/1与真实汉字绑定分离，不把识字推断写为用户确认。

## 2026-09-22 单字实验扩展

用户确认四字字体可用，并提交“永”字照片，授权开始图片闭环。本轮新增 image_pipeline/core.py 和 run_single_glyph.py，复用已修正的 V5 Writer，不修改 GFont 模型。范围仅为一张已裁单字图；没有 GUI、自动字符识别、整页检测、机器控制或打包。

分层为 preprocess → skeletonize → graph_from_skeleton → candidate_strokes → Glyph → Writer。原始照片逐字节保存为只读副本；算法产物与 confirmed_strokes 分离，后者保持 null。本轮导出明确标记 experimental，不能当作人工确认字体。代码不覆盖任何已有实验目录。

图像依赖为可选的 NumPy / SciPy / Pillow，核心 GFont 仍仅需标准库。Zhang-Suen 使用 NumPy 实现；图遍历保留闭环和断开的连通分量。交叉点仅按切线连续性提出路径配对，不识别或保证正确笔顺。

本阶段只验证奎享雕刻 GFont V5。无 GUI、图像处理、模型下载、PyInstaller、机器控制。依据原对话《方案评估补充》的最终结论，以及当前恢复的 9 个原始附件；原对话关于 80 个驱动字体的统计是历史记录，不等于本次复验。

## 模块边界

```text
gfont_core/
  glyph.py       Point / Glyph(strokes)
  metadata.py    GFontMetadata：已解密字段
  font.py        GFont：Metadata + 字形映射 + Inline 顺序
  qqtea.py       纯 Python 16 轮 TEA / QQ 链接与填充
  reader.py      文件和 Metadata 的独立解码
  writer.py      文件和 Metadata 的独立编码
  minimal.py     一十人口的人工坐标
  __main__.py    inspect / roundtrip / minimal
tests/           unittest，含真实样本回归
samples/         来源和 SHA-256 清单、只读原件副本
artifacts/       新生成字体和验证报告
```

Reader 不导入 Writer，Writer 不导入 Reader；共享数据模型和 QQTea 算法，不共享字形序列化实现。文件布局仅存在于读写层，内部笔画不保存 MoveTo/LineTo 编码。所有新增字体路径均独占创建，拒绝覆盖。原始附件与只读副本都不作内容修改。

## 公共接口

```python
font = GFontV5Reader.read("input.gfont")
font.metadata.name
font.glyphs[0x4E00].strokes
GFontV5Writer.write(font, "roundtrip.gfont")
# 内存接口：loads(bytes) / dumps(font)
```

Reader 保留 Inline 的选择及顺序，ZIP 包含全部字形，Inline 是对应字形的重复副本。Writer 重新生成 Metadata 明文、QQTea 密文和 ZIP；随机填充及压缩布局允许不同，但字段与字形必须语义一致。Metadata 字形数不一致仅报告警告，不擅自修正历史文件。font_type_raw、extra_n、extra_o 原样保存，不猜含义。

V3 仅识别版本后明确报不支持；兼容读取作为后续任务，不输出 V3。不是本轮暗中实现的功能。

## 后续架构（本阶段不实现）

原图 → Character Region → 人工/模板 Unicode 绑定与锁定 → 预处理 → Skeleton → Generated Graph → Stroke Candidates → 人工确认 → Confirmed Strokes → 字体坐标 → Glyph → Exporter。

Project JSON 与最终 .gfont 分离；项目层保存 schema_version、来源哈希、处理参数与版本、变体、确认状态和修订历史。Character Region 不等于连通域。自动结果不得覆盖人工确认结果或 Unicode 锁定。正式扩展这些接口前，更新本文件、SCHEMA.md 和对应迁移/验收说明，避免每个模块各自引入一种结构。


## 疑点定位更新

质量检查通过 image_pipeline.quality.inspect_glyph 读取当前编辑快照。纠正器在修改、撤销和切字后重新计算提示；检查过程不改动路径或确认状态。


## 分离结构保护实验

image_pipeline.component_guard 为显式参照驱动的可选处理层，保留参照连通块，不推断真实笔画。默认 preprocess 保持原行为，避免将低分辨率基准的灰度阈值推广到照片。


## 孔洞保护实验

component_guard 增加 preserve_holes=False 参数；显式启用后使用前景八邻域/背景四邻域的局部连通检查，保留参照的连通块和孔洞数。该约束不代表字形或真实笔画正确。


## 字形外观优先

appearance_metrics 提供方向无关的同笔宽渲染、墨迹及中心线距离、运行量代理。整数为像素中心。笔顺/分笔匹配不作为字形主验收门槛；错误的落笔连接仍必须检查。默认提取器不变。


## Optional geometry refinement regression

See [GEOMETRY_REFINEMENT.md](GEOMETRY_REFINEMENT.md) for the raster-guided candidate API, frozen 96-condition paired results, limits and validation. Default extraction is unchanged. All 86 tests pass; this is not a physical machine validation.


## Optional junction candidates

See [JUNCTION_CANDIDATES.md](JUNCTION_CANDIDATES.md) for bounded candidate pairing, ambiguity diagnostics and the 100-case known regression. The default pipeline is unchanged. There are 91 passing tests; held-out connection accuracy and machine validation remain outstanding.
