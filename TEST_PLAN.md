# Phase 0 测试与验收

节点级编辑新增测试：节点拖动只在松开后提交一次，取消预览不修改记录；插入/删除几何、闭环端点同步、无效坐标原子拒绝、补画提交/取消、确认失效、JSON重载。沿用原项目schema，所有新增操作都产生普通点列和待确认状态。

笔画修正器：test_stroke_editor.py覆盖拆分/连接几何、显式反转、确认状态失效及撤销、跨字隔离、排序、记录加载/错误来源拒绝、源字体保护、空字形恢复。`python tests/smoke_stroke_ui.py`覆盖实际Tk图元、配准图、节点拆分、路径操作、确认、记录和导出。UI隐藏测试不代替用户视觉验收，不据此宣称复杂笔画已经正确。

坐标编辑器：tests/test_coordinate_editor.py测试变换顺序、逆旋转、参数边界、撤销/重做分支、配置复用、全字体导出、原件保护。`python tests/smoke_coordinate_ui.py`执行隐藏Tk界面测试：字体加载、字形切换、参考图配准、数值应用、撤销重做、屏幕/世界坐标转换、导出。最终仍需用户打开界面并在驱动中检查产物，程序测试不替代真实使用验收。

2026-09-23 四字照片诊断见 artifacts/photo_0923_final/README.md：新增2项孔洞保留测试；导出18个测试字形，检查float32语义与独立ZIP偏移，Java逐字形读取。用户需使用相同字号比较ABCD、EFGH、IJKL、MNOP四行，不能将离线坐标图视为目标驱动已验收。复杂字符的断笔/笔顺仍为未通过的人工质量项。

## 单字实验新增测试

`python -m unittest discover -s tests -v` 现同时包含图像测试，需要 image 可选依赖。仅运行 Phase 0 可用 `python -m unittest discover -s tests -p test_core.py -v`。

覆盖实心条骨架连通及幂等、十字四臂及两路径配对、闭环、短线、独立点与短毛刺、分离笔画。真实“永”字检查原图哈希、保存每一层、可视对照、候选边覆盖、导出后的 Metadata/Unicode/笔画/float32 坐标。自动笔顺不作为通过项，目标软件与机器另行验收。

## 自动验证

在项目根目录运行 `python -m unittest discover -s tests -v`。Python 3.9+，仅标准库，无需联网安装。

1. 模型：BMP 边界、非法坐标、空字形/空笔画、字典映射。
2. QQTea：全部填充长度、错误密钥/密文、真实字体 Metadata 解密。
3. 二进制：独立手算“一”字节向量、首命令与计数、Inline/ZIP 冲突、V3 拒绝、截断与负长度、空占位。
4. Metadata：九字段完整消费、中文、NUL、补充平面；后两项仅合成验证。
5. 原件保护：样本 SHA-256 前后不变，输出拒绝覆盖任何现有文件。
6. Golden Round-trip：逐个读取九个附件 → 重新加密并重建 → 再读；比较所有 Metadata 字段、Unicode 集合、Stroke/Point 顺序、Inline 选择与顺序。另比较解密后的 Metadata 原始字节和每个 ZIP Glyph 原始字节，避免仅依赖同一对 Reader/Writer 自洽。缺失样本明确失败，不 skip 或 mock。
7. minimal：人工“一十人口”，独立 Metadata；重读四字与原模型一致。

ZIP 整包及 QQTea 密文字节无需一致。保留原样本 Metadata glyph_count 的已知差异，并记录警告。自动通过不代表目标应用已通过。

2026-09-22 新增回归：检查 EOCD 中的中央目录偏移和中央目录中的 Local Header 偏移均相对独立 ZIP 起点；对每个真实样本与重建文件验证。额外交叉检查：用 Java ZipFile 逐项读取截取后的 ZIP。旧版两份产物在该检查中失败，不能仅用 Python 的成功读取判断封装正确。

## 目标软件验收（待用户实测）

先记录奎享雕刻版本、操作系统、写字机型号；保留原安装目录。将产物通过软件支持的方式加入测试字体环境。Round-trip 会保留原字体名/ID，应单独测试，避免与同名原字体混淆。

| 项目 | roundtrip.gfont | minimal.gfont |
|---|---|---|
| 字体列表可见 | 待测 | 待测 |
| 名称正确 | 与原件一致 | Image2GFont_Phase0 |
| 一十人口输入 | 待测 | 待测 |
| 路径/尺度/方向预览 | 与原件对比 | 与人工坐标对比 |
| 软件日志无错误 | 待测 | 待测 |
| 预览通过后实际书写 | 待测 | 待测 |

记录结果到 artifacts/APP_TEST_RESULTS.md。Round-trip 成功、minimal 失败时优先检查新建 Metadata、font_size、type、Inline 选择；两者失败时先对比原件与产物，不进入图片算法。

只有两个实验均被目标软件接受并完成必要的机器验证，才关闭 Phase 0。驱动包原始压缩附件本次未恢复，不能把历史 80 字体统计计入本次通过数。


## 疑点定位更新

新增 tests/smoke_quality_ui.py，检查疑点导航、只读性、编辑后刷新、撤销、切字和补线保护。48 项单元测试及两组笔画界面逻辑检查通过；可见界面和驱动实测待完成。


## 外部样本验证

公开样本基线采用固定字符与哈希选样，不根据结果筛选。96 张处理与编辑一致性检查完成，新增区域合并/删除/拆分指标测试；共 51 项单元测试通过。图像真实笔画准确率、纸面照片及驱动验证仍未完成。详细范围见 EXTERNAL_VALIDATION.md。


## 分离结构保护实验

分离结构保护新增 6 项测试，共 57 项通过。192 张两方案比较完成；参照连通性保证与真实笔画准确率分开报告。新增字符样本已用于检查，后续作为回归集。详见 COMPONENT_GUARD.md。


## 孔洞保护实验

孔洞保护新增 6 项测试（含 100 组固定随机掩码不变量），共 63 项通过。192 张已知样本回归的孔洞变化由 40 降为 0，短路径提示仍为 33 张/47 条。仍需真实笔画标注与驱动实测。


## 记录轨迹验证

新增 48 份记录轨迹的逐笔验证，细/粗两种重绘条件、默认/保护两种算法。新增 9 项匹配指标测试，全项目 72 项通过。参照为实际记录顺序，非中文规范笔顺；合成输入不代替照片实测。


## 字形外观优先

新增 9 项外观度量测试，总计 81 项通过。48 源记录×2 笔宽×2 方案，共 192 次字体序列化回读完成。已知合成栅格测试不替代照片、毫米尺寸与真实笔尖校准。主报告 artifacts/appearance_v2。


## Optional geometry refinement regression

See [GEOMETRY_REFINEMENT.md](GEOMETRY_REFINEMENT.md) for the raster-guided candidate API, frozen 96-condition paired results, limits and validation. Default extraction is unchanged. All 86 tests pass; this is not a physical machine validation.


## Optional junction candidates

See [JUNCTION_CANDIDATES.md](JUNCTION_CANDIDATES.md) for bounded candidate pairing, ambiguity diagnostics and the 100-case known regression. The default pipeline is unchanged. There are 91 passing tests; held-out connection accuracy and machine validation remain outstanding.


## New web handwriting evaluation

See [NEW_WEB_HANDWRITING_VALIDATION.md](NEW_WEB_HANDWRITING_VALIDATION.md): 42 new images, frozen parameters, full failure diagnostics and limitations. No default algorithm changes.


See [INK_SUPPORT_VALIDATION.md](INK_SUPPORT_VALIDATION.md): optional bright-bridge guard did not improve the 42-image regression and remains disabled by default. Local width diagnostics and 96 passing tests are documented.


See [JUNCTION_REVIEW_EDITOR.md](JUNCTION_REVIEW_EDITOR.md) for junction previews, accept/undo and source-width navigation in the existing stroke editor.


## Manual multi-character image import

See [PAGE_IMPORT.md](PAGE_IMPORT.md) and start_page_import.bat for crop/binding projects and generation into the existing stroke editor. Automatic page detection is not implemented.
