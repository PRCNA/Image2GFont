# 公开手写样本验证

当前报告：`artifacts/external_handwriting_v1/index.html`。
结论：96 张外部样本通过处理及编辑数据一致性检查，但 20 张出现参照区域合并，尚不能确认自动提取质量普遍可靠。详见该目录 `FINDINGS.md`。

## 复现

从固定上游版本获取两个分包（001、004）及 README.md、License，置于同一下载目录。项目工作区 `work/handwriting_download` 已缓存本次下载。分包校验值、完整 URL、样本条目和只读样本校验值均在报告的 manifest.json。

```text
python validate_public_handwriting.py ../../work/handwriting_download artifacts/external_handwriting_new
```

输出目录必须不存在，避免覆盖既有基线。脚本不联网、不执行下载文件中的代码、不调参，不修改图像提取核心或原有字体。派生路径 JSON 仅为候选结果，不会标记为人工确认。

样本按预定字符列表及来源条目哈希选取，未根据提取好坏挑选。字符交错分配到开发、评估两组，各 48 张。使用既有参数，省略原照片专用的边缘区域删除。二值图与固定阈值参照比较仅是诊断指标，不是真实笔画准确率。

`tests/test_external_metrics.py` 验证区域合并、删除、拆分及不变情形的指标计算。原有编辑测试及每个外部字形的适用编辑操作检查用于验证数据操作。报告不替代真实驱动、机器书写或人工逐笔验收。
