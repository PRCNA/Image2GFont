# 数据规范 · Phase 0 / v1

Image2GFontStrokeEdits/schema_version=1包含source、source_sha256、glyphs（十进制码点键，strokes为[x,y]点序列，confirmed为bool）。字形与源文件集合必须一致；加载前核对源哈希。任一笔画修改将该字confirmed置false，显式人工确认才置true；用户确认Unicode绑定不改变本状态。导出的GFont没有确认字段，JSON为修正工程记录。

Image2GFontCoordinateProfile schema_version=1：transform包含dx/dy/scale/angle/pivot_x/pivot_y/flip_x/flip_y，scope=whole_font，source与source_sha256追踪来源，driver_verified=false。缩放须>0且<=100，各数值有限。配置与字体分开保存，加载配置不将源字形修改为人工确认笔画。

2026-09-23 坐标诊断：artifacts/photo_0923_final/report.json 按slot保存源图裁切框、四种变换(scale_x,scale_y,offset)、测试键、参数与哈希；candidates.json 的character=null、binding_confirmed=false。A～P仅为诊断输入键，不是用户汉字身份。原图保存不变，所有变换派生新字形。原样本坐标范围与驱动行为假设分开记录。

## 单字项目 schema_version=1（2026-09-22）

project.json 保存 source 原始哈希/尺寸/只读副本路径、binding(codepoint, character, locked, origin)、recipe 参数、依赖版本、生成图和候选文件引用、export 变换和 QC。永 U+6C38 来自用户提交图片及约定的“永”字任务，不使用 OCR。

generated_graph.json 的 nodes 为 id/point/degree；edges 为 id/start/end/points。stroke_candidates.json 使用加边框后的工作图像像素坐标，记录每条候选引用的 edge_ids。glyph_candidate.json 使用等比缩放居中的 1000×1000 测试空间，Y 向下；字体坐标转换在 project.json 记录。缩放保留纵横比，800 单位包围盒最大边，中心为 (500,500)。

status 始终为 candidate，confirmed_strokes=null。导出仅为实验验收，不越过人工确认状态。简化误差以工作图像像素计；每次新目录保留参数和中间结果，禁止覆盖人工数据。照片边缘缺失不作补画。

## 内部模型

Point(x, y)：有限浮点坐标；Glyph(codepoint, strokes)：有序笔画列表，每笔为有序 Point 列表。可存在无笔画字形，但不允许空笔画。保留重复点、单点笔画、负坐标和原始顺序，不简化、不归一化。

本阶段 Glyph 是 V5 导出模型，codepoint 为 0..65535；未来 Project 层可保存更高的单一 Unicode scalar，但 V5 Exporter 必须拒绝超范围值，不能截断。坐标以 float32 序列化；新建任意 Python float 会量化，真实样本读取后的 float32 可精确重写。

GFont(metadata, glyphs, inline_codepoints)：字典键等于 Glyph.codepoint；Inline 不能重复，必须属于 glyphs。Inline 对应字形同时出现在 ZIP。

GFontMetadata：creator、font_type_raw、name、font_id、description、font_size、glyph_count、extra_n、extra_o。两个 extra 字段及 type 只保留原始值，无额外推断。

## V5 二进制

所有 GFont 整数和 float 均大端。ZIP 自身遵循 ZIP 规范，不适用此大端规则。

ZIP 必须先独立生成，再拼接到 GFont 头部后面。中央目录及 Local Header 的偏移量以 ZIP 起点为 0，不以整个 .gfont 起点为 0。2026-09-22 已对 9 个原始样本复核此规则。第一版 Writer 写错此处，Python ZipFile 的兼容处理掩盖了问题；Java 读取截取后的 ZIP 会报 bad central directory offset。

```text
int32 version = 5
int32 encrypted_metadata_length
bytes QQTea encrypted metadata
int32 inline_glyph_count
Glyph[inline_glyph_count]
ZIP_DEFLATED archive：entry 名为 Unicode 十进制数

Glyph:
  uint16 codepoint
  int32 coordinate_count = 2 * point_count
  float32 coordinates[coordinate_count]  # x,y 交替
  int32 command_count = point_count
  uint8 commands[command_count]         # 0 MoveTo, 1 LineTo
```

首命令必须为 MoveTo；其他命令拒绝处理。每个 ZIP 条目完整消费、内部 codepoint 与条目名一致。Inline 与 ZIP 副本必须一致。没有任何字形时允许头部直接结束（驱动包空占位字体的历史结论；本轮用合成用例覆盖，尚无该真实附件）。

## Metadata 明文

```text
UTF creator
int32 font_type_raw
UTF name
UTF font_id
UTF description
int32 font_size
int32 glyph_count
UTF extra_n
UTF extra_o
```

UTF = uint16 大端字节长度 + Java modified UTF-8。当前样本中的常规 UTF-8 与 modified UTF-8 相同；NUL/补充平面兼容按 Java 规则实现并用合成用例验证，尚无这些字符的真实样本。名称不是 uint16 字符串数组。

QQTea：16 轮 TEA，大端 uint32，固定格式密钥 `01090809000802060109090200080208`。8 字节分组，QQ 链接，1 字节填充头、0..7 字节随机填充、2 字节随机盐、明文、7 字节零尾。密钥来自原对话，真实附件解密与完整字段解析提供交叉证据。

## 实验字体

minimal.gfont 名称/ID = Image2GFont_Phase0，creator=kvenjoy，type=0（实验选值，不解释类别），font_size=1000，glyph_count=4，extra 字段为空。四个字都写入 Inline 和 ZIP。坐标来自人工 1000×1000 测试空间，Y 方向和目标软件尺度需要预览实测，不声称单位为毫米。

## 边界与失败

Phase 0 资源限制：文件 64 MiB、Metadata 4 MiB、单 ZIP 字形 16 MiB、ZIP 解压总量 128 MiB、每字最多 100 万点、最多 65536 字形。超限、损坏 ZIP、未知命令、格式冲突均报错，不自动切换方言。限制是实现保护，不是文件格式事实。


## Manual multi-character image import

See [PAGE_IMPORT.md](PAGE_IMPORT.md) and start_page_import.bat for crop/binding projects and generation into the existing stroke editor. Automatic page detection is not implemented.


## Multi-image font collection (2026-09-28)

Image2GFontCollection schema_version=1: name and pages (relative page.json paths). Each page retains the Image2GFontPage schema, immutable original image, SHA256, integer crop boxes, and manual character bindings. Duplicate characters across pages are rejected. Combined export is a candidate; driver_verified=false. See FONT_PROJECT.md.


## Visual V2 extension

Optional vision_mode on collection, page region and confirmed OCR session entry: auto/dark/light/cyan/dark_red_grid. A region mode overrides the collection default. Absent mode preserves legacy extraction. V2 page report rows contain vision.config, resolved_mode, source_size, working_size, source_to_working, foreground_fraction, warnings and transform. V2 crop references have zero padding; legacy references retain their own padding. Recognition suggestions have confidence=null and binding_confirmed=false; never imply geometry approval.
