"""Generate the four-character offline review report without changing the font."""
import hashlib
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from gfont_core import GFontV5Reader
from image_pipeline.quality import inspect_glyph


def main():
    root = Path(__file__).resolve().parent
    source = root / 'artifacts/photo_0923_hanzi'
    target = root / 'artifacts/quality_review'
    target.mkdir(exist_ok=True)
    data = (source / 'he_kou_cang_yi.gfont').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    font = GFontV5Reader.loads(data)
    provenance = json.loads((source / 'report.json').read_text(encoding='utf-8'))
    label = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 21)
    small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
    results, sections, table = [], [], []
    for row in provenance['rows']:
        g = font.glyphs[row['codepoint']]
        result = inspect_glyph(g, font.metadata.font_size)
        results.append(result)
        im = Image.new('RGB', (1100, 610), 'white')
        d = ImageDraw.Draw(im)
        d.text((20, 12), f"{chr(g.codepoint)}：原图与候选路径（Y 轴向下）", fill='#172b4d', font=label)
        crop = Image.open(source / f"crop_{row['slot']}.png").convert('RGB')
        crop.thumbnail((350, 460))
        # Enlarge small source crop for review, retaining aspect ratio.
        ratio = min(350/crop.width, 460/crop.height)
        crop = crop.resize((round(crop.width*ratio), round(crop.height*ratio)))
        im.paste(crop, (20, 75))
        def screen(x, y):
            return (440+x*.48, 65+y*.48)
        d.rectangle((440, 65, 920, 545), outline='#98a2b3', width=2)
        for n in range(0, 1001, 200):
            x, y = screen(n, n)
            d.line((x, 65, x, 545), fill='#edf0f4')
            d.line((440, y, 920, y), fill='#edf0f4')
            d.text((x-10, 548), str(n), font=small, fill='#666666')
            d.text((390, y-10), str(n), font=small, fill='#666666')
        for i, path in enumerate(g.strokes):
            pts = [screen(p.x, p.y) for p in path]
            color = '#e17b14' if result['paths'][i]['short'] else '#2865a8'
            if len(pts) > 1:
                d.line(pts, fill=color, width=3)
            else:
                x, y = pts[0]
                d.ellipse((x-3, y-3, x+3, y+3), fill=color)
        for gap in result['nearby_endpoints']:
            if gap['aligned']:
                a, b = screen(*gap['a']), screen(*gap['b'])
                d.line((a, b), fill='#d52e4e', width=3)
                for x, y in [a, b]:
                    d.ellipse((x-4, y-4, x+4, y+4), outline='#d52e4e', width=2)
        d.text((20, 578), '蓝：候选路径  橙：短路径  红：方向相对的近端点（仅提示，未连接）', font=small, fill='#333333')
        name = f"U{g.codepoint:04X}.png"
        im.save(target / name)
        short = ', '.join(str(p['stroke_index']+1) for p in result['paths'] if p['short']) or '无'
        gaps = ''.join(f"<li>路径 {q['a_stroke']+1}（{q['a_end']}） ↔ {q['b_stroke']+1}（{q['b_end']}），间距 {q['distance']:.1f}</li>" for q in result['nearby_endpoints'] if q['aligned']) or '<li>无</li>'
        table.append(f"<tr><td>{chr(g.codepoint)}</td><td>{result['stroke_count']}</td><td>{result['short_count']}</td><td>{len(result['nearby_endpoints'])}</td><td>{result['aligned_gap_count']}</td></tr>")
        sections.append(f'<h2>{chr(g.codepoint)} · U+{g.codepoint:04X}</h2><img src="{name}" alt="原图与路径对照"><p>短路径编号：{short}。编号从 1 开始，与编辑器列表对应。</p><details><summary>方向相对的近端点明细</summary><ul>{gaps}</ul></details>')
    report = dict(schema_version=1, source=str(source / 'he_kou_cang_yi.gfont'),
                  source_sha256=digest, font_size=font.metadata.font_size,
                  indices='zero-based', modified=False, results=results)
    assert hashlib.sha256((source / 'he_kou_cang_yi.gfont').read_bytes()).hexdigest() == digest
    (target / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>字形质量检查</title>
<style>body{max-width:1100px;margin:32px auto;padding:0 20px;font:17px/1.7 system-ui;color:#243247}img{width:100%;border:1px solid #ddd}table{border-collapse:collapse}td,th{padding:8px 20px;border:1px solid #ccd}summary{cursor:pointer}h2{margin-top:40px}</style>
<h1>和、扣、藏、移：离线质量检查</h1>
<p>这是候选路径的几何疑点报告，不能判定真实笔顺或自动证明断笔。原始字体未修改，也未生成“修复版”字体。</p>
<p>短路径：总长度不超过字框的 4%（40 单位）；近端点：距离不超过 3.5%（35 单位），排除重合端点和闭合路径。方向相对：两端向外的切线分别与间隙方向相差不超过 45°。这些阈值是待实测的启发式规则。正常点画、相邻独立笔画可能被提示；长路径内部的错误连接仍可能漏检。</p>
<table><tr><th>字</th><th>候选路径</th><th>短路径</th><th>近端点对</th><th>方向相对</th></tr>'''+''.join(table)+'''</table>
<p>建议先审查“藏、移”的短碎线，再对照原图判断红色间隙是否确实应连接。此处路径数量不代表汉字笔画数。矩形表示当前字体 0～1000 的坐标范围，不表示奎享已验证的基线。</p>'''+''.join(sections)+f'<p>来源校验 SHA-256：<code>{html.escape(digest)}</code></p></html>'
    (target / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['codepoint','stroke_count','short_count','aligned_gap_count']} for r in results]))


if __name__ == '__main__':
    main()
