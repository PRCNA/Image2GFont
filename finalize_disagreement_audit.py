"""Persist visual review judgments; never modify OCR bindings or source images."""
import json
from collections import Counter
from pathlib import Path

root = Path('artifacts/ocr_disagreement_audit')
cases = json.loads((root / 'cases.json').read_text(encoding='utf-8'))
assert [c['id'] for c in cases] == list(range(1, 115))
for c in cases:
    n = c['id']
    if n in (1, 2, 6, 7, 8, 9):
        verdict, text, note = 'Qwen文字较可信', c['qwen'], '对照可见字形；不代表其裁切框完整。'
    elif n in (3, 4, 30):
        verdict, text, note = '待确认', None, '草写或字形细节不足，不依据上下文强行定字。'
        if n == 30:
            note = '明显不是 Qwen 的“入”；着/著细节保留待确认。'
    elif n == 5:
        verdict, text, note = 'Rapid文字较可信', c['rapid'], '可见字形为舟，Qwen识为丹。'
    elif 10 <= n <= 62:
        verdict, text, note = 'Rapid位置文字较可信', c['rapid'], '该位置字形支持 Rapid；密集页存在连续的 Qwen 文字与坐标错配，不作为纯识字错误计数。'
    elif n == 63 or 87 <= n <= 94:
        verdict, text, note = '印刷页脚排除', None, '不是待采集手写字；不可作为手写识字准确率样本。'
        if n == 63:
            text, note = '第', '印刷“第”，Qwen文字较可信，但排除手写评估。'
    elif 64 <= n <= 83:
        verdict, text, note = 'Rapid单侧字形可辨', c['rapid'], '未获得符合阈值的空间匹配；不等于 Qwen 完全没有输出此文字。'
    elif 84 <= n <= 86:
        verdict, text, note = '单侧待确认', None, '署名草写需原作者确认，不作为已确认绑定。'
        if n == 84:
            note = '字形更像“刻”而非“到”，保留待确认。'
    else:
        verdict, text, note = 'Qwen单侧定位异常', None, '框位于列间或只覆盖字的一部分；不能当作新增正确字，也不能据此判纯识字对错。'
    c.update(review=verdict, suggested_text=text, note=note,
             evidence=f'sheet_{(n-1)//12+1:02d}.png', confirmed=False)
(root / 'reviewed_cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
counts = Counter(c['review'] for c in cases)
lines = ['# RapidOCR / Qwen 全部分歧复核', '',
         '范围：已有共同测试的 image_04、image_06、image_07 三张图片。逐一目视检查 114 项空间匹配分歧及单侧结果，另检查 1 项被解析器拒绝的页脚字符串。不是整个图片库的全量准确率测试。', '',
         '匹配：最大化 IoU 的一对一分配，IoU ≥ 0.1 且交集/较小框面积 ≥ 0.5。空间配对仅用于排查，不保证两个模型原本指向同一个字。证据图为两框并集加边距，不能据此认为各自裁切框完整。', '',
         '|图片|文字不同的空间配对|Rapid未匹配|Qwen未匹配|', '|---|---:|---:|---:|',
         '|image_04|4|0|0|', '|image_06|3|0|0|', '|image_07|56|31|20|', '',
         '主要发现：稀疏两页 7 项分歧中，4 项支持 Qwen，1 项支持 Rapid，2 项不确定。密集页出现成串文字与坐标不对应及列间窄框，必须先解决定位，不能用这些错配计算模型识字胜负。', '',
         '处理建议：保留 Rapid 切割；在同一个固定裁切上比较识字建议；排除印刷页脚；不确定项保留人工确认。此次只写审计文件，没有修改生产配置、原始图片、OCR 结果或字体绑定。', '',
         '额外拒绝项：Qwen 输出 “10X15=150”，属于页面底部印刷内容，因多字符被单字解析器拒绝；不是手写漏字。', '',
         '## 分类计数', '']
lines += [f'- {k}：{v}' for k, v in counts.items()]
lines += ['', '## 逐项记录', '', '|编号|图片|Rapid|Qwen|判断|建议字|说明|证据|', '|---:|---|---|---|---|---|---|---|']
for c in cases:
    vals = [str(c['id']), c['page'], c['rapid'] or '—', c['qwen'] or '—', c['review'], c['suggested_text'] or '待确认/不适用', c['note'], f"[查看]({c['evidence']})"]
    lines.append('|' + '|'.join(vals) + '|')
(root / 'REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps(dict(counts), ensure_ascii=False))
