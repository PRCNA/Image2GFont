"""Frozen external smoke benchmark, not a stroke-accuracy benchmark.

Inputs: official AI-FREE archive parts 001 and 004 plus README.md / License.
No network access, parameter search, automatic repairs or OCR is performed.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import platform
import stat
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import scipy
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

from gfont_core import GFont, GFontMetadata, Glyph, Point, GFontV5Reader, GFontV5Writer
from image_pipeline.core import preprocess, skeletonize, prune_spurs, graph_from_skeleton, candidate_strokes, simplify
from image_pipeline.quality import inspect_glyph
from stroke_editor.model import StrokeSession

SOURCE = 'https://github.com/AI-FREE-Team/Traditional-Chinese-Handwriting-Dataset'
REVISION = 'a9597d85a0eeaf9998294a0ad67e846be9d8829d'
CHARACTERS = '二十人大小口中回女安國學血行衣西言車門雨鳥龍體鬱'
RECIPE = dict(blur=.8, threshold=7, closing=2, min_area=12,
              background_sigma=18, silhouette_sigma=.4, max_hole_area=3)
FONT = 'C:/Windows/Fonts/msyh.ttc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def component_relations(reference, mask):
    """Overlap correspondence distinguishes vanished regions from merged ones."""
    original,n=ndi.label(reference,np.ones((3,3)))
    processed,m=ndi.label(mask,np.ones((3,3)))
    links={i:[int(v) for v in np.unique(processed[original==i]) if v]
           for i in range(1,n+1)}
    merged=[[i for i,targets in links.items() if j in targets] for j in range(1,m+1)]
    return dict(merged_reference_groups=[group for group in merged if len(group)>1],
                removed_reference_components=[i for i,targets in links.items() if not targets],
                split_reference_components=[i for i,targets in links.items() if len(targets)>1])


def freeze_samples(downloads, out, characters=CHARACTERS):
    originals = out / 'originals'
    originals.mkdir()
    lookup, archives = {}, []
    for part in ('001', '004'):
        path = downloads / f'cleaned_data(50_50)-20200420T071507Z-{part}.zip'
        archives.append(dict(file=path.name, sha256=sha(path.read_bytes()),
                             url=f'{SOURCE}/blob/{REVISION}/data/{path.name}'))
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                leaf = name.split('/')[-1]
                character = leaf.split('_')[0]
                if name.endswith('.png') and character in characters:
                    lookup.setdefault(character, []).append((part, name))
    entries = []
    for char_index, char in enumerate(characters):
        # Selection is independent of image contents and extraction outcomes.
        pool = sorted(lookup.get(char, []), key=lambda p: sha(('external-v1/'+p[1]).encode()))
        if len(pool) < 4:
            raise ValueError(f'Insufficient samples for U+{ord(char):04X}')
        for sample_index, (part, name) in enumerate(pool[:4]):
            with zipfile.ZipFile(downloads / f'cleaned_data(50_50)-20200420T071507Z-{part}.zip') as z:
                data = z.read(name)
            key = f'U{ord(char):04X}_{sample_index+1}'
            dest = originals / f'{key}.png'
            dest.write_bytes(data);dest.chmod(stat.S_IREAD)
            entries.append(dict(id=key, character=char, codepoint=ord(char),
                                source_entry=name, archive_part=part, sha256=sha(data),
                                file=f'originals/{key}.png',
                                split='development' if char_index % 2 == 0 else 'evaluation'))
    for name in ['README.md', 'License']:
        data = (downloads / name).read_bytes()
        path = originals / ('upstream_'+name)
        path.write_bytes(data);path.chmod(stat.S_IREAD)
    manifest = dict(dataset=SOURCE, revision=REVISION, archives=archives, samples=entries,
                    selection='24 preselected characters; four entries per character sorted by SHA256(external-v1/entry). Character-disjoint alternating splits.',
                    recipe=RECIPE, normalization='Entire source resized to 200x200 with LANCZOS, white pad 16; no photo-specific border component deletion.',
                    limitations=['50x50 online-handwriting-derived images; not paper photographs',
                                 'No verified pen-lift, stroke-order, or writer identity labels',
                                 'No per-sample tuning; both splits evaluated as an initial baseline',
                                 'Evaluation split becomes a regression set if its results influence future tuning'])
    save_json(out / 'manifest.json', manifest)
    return manifest


def check_editor(glyph, folder):
    """Exercise editing on external geometry, then require exact undo restore."""
    cp = glyph.codepoint
    font = GFont(replace(GFontMetadata(), name='ExternalBenchmark', glyph_count=1), {cp:glyph}, [cp])
    path = folder / 'candidate.gfont'
    GFontV5Writer.write(font, path)
    session = StrokeSession(path)
    before = session.payload()
    checked = []
    def operation(name, fn):
        old_position = session.position
        fn()
        if session.position != old_position:
            session.undo();assert session.payload() == before
            session.redo();session.undo();assert session.payload() == before
        checked.append(name)
    if glyph.strokes:
        operation('reverse', lambda:session.reverse(cp, 0))
        operation('delete', lambda:session.delete(cp, [0]))
        p = session.paths[cp][0][0]
        operation('move_point', lambda:session.move_point(cp, 0, 0, Point(p.x+3,p.y-2)))
        if len(glyph.strokes)>1:
            operation('join', lambda:session.join(cp, 0, 1))
            operation('reorder', lambda:session.move(cp, 0, 1))
        long = next((i for i,s in enumerate(glyph.strokes) if len(s)>2), None)
        if long is not None:
            operation('split', lambda:session.split(cp, long, 1))
        segment = next((i for i,s in enumerate(glyph.strokes) if len(s)>1), None)
        if segment is not None:
            a,b = session.paths[cp][segment][:2]
            operation('insert_point', lambda:session.insert_point(cp,segment,0,Point((a.x+b.x)/2,(a.y+b.y)/2)))
    operation('add_path',lambda:session.add_path(cp,[Point(100,100),Point(150,120)]))
    session.save_project(folder/'edits.json')
    session.load_project(folder/'edits.json');assert session.payload()==before
    session.export(folder/'export.gfont','ExternalBenchmark')
    readback=GFontV5Reader.read(folder/'export.gfont')
    assert readback.glyphs[cp] == session.glyph(cp)
    assert not any(session.confirmed.values())
    return checked+['save_load','export_readback']


def evaluate(entry, out):
    source=(out/entry['file']).read_bytes()
    assert sha(source)==entry['sha256']
    image=Image.open(io.BytesIO(source)).convert('L')
    working=image.resize((200,200),Image.Resampling.LANCZOS)
    gray=np.pad(np.asarray(working),16,constant_values=255)
    reference=gray<128  # Pixel proxy, not annotated ground truth.
    mask=preprocess(gray,**RECIPE)
    mask[:16]=False;mask[-16:]=False;mask[:,:16]=False;mask[:,-16:]=False
    thin=skeletonize(mask);thin,removed=prune_spurs(thin,3)
    graph=graph_from_skeleton(thin);candidates=candidate_strokes(graph)
    assert sorted(i for s in candidates for i in s['edge_ids'])==list(range(len(graph['edges'])))
    paths=[simplify(s['points'],.65) for s in candidates]
    points=np.array([p for s in paths for p in s])
    if len(points):
        low,high=points.min(0),points.max(0)
        scale=800/max(float(max(high-low)),1)
        offset=np.array([500,500])-(low+high)*scale/2
        glyph=Glyph(entry['codepoint'],[[Point(float(x*scale+offset[0]),float(y*scale+offset[1])) for x,y in s] for s in paths])
    else:
        glyph=Glyph(entry['codepoint'],[])
    glyph.validate()
    quality=inspect_glyph(glyph,1000)
    with tempfile.TemporaryDirectory(prefix='external_',dir=out/'temporary') as temp:
        editor_checks=check_editor(glyph,Path(temp))
    raw_components=ndi.label(reference,np.ones((3,3)))[1]
    components=ndi.label(mask,np.ones((3,3)))[1]
    recall=float((reference&mask).sum()/max(1,reference.sum()))
    additions=float((mask&~reference).sum()/max(1,reference.sum()))
    row=dict(**entry,source_size=list(image.size),candidate_count=len(paths),
             point_count=sum(map(len,paths)),reference_components=raw_components,
             mask_components=components,reference_dark_pixel_retention=recall,
             added_area_vs_reference=additions,pruned_pixels=removed,
             short_count=quality['short_count'],aligned_gap_count=quality['aligned_gap_count'],
             editor_checks=editor_checks,status='completed',review_flags=[])
    row['component_relations']=component_relations(reference,mask)
    if not paths:row['review_flags'].append('empty_output')
    if recall<.95:row['review_flags'].append('dark_pixel_retention_below_95pct')
    if components!=raw_components:row['review_flags'].append('component_count_changed')
    # Work-space geometry and complete hints allow independent inspection.
    save_json(out/'paths'/f"{entry['id']}.json",dict(pixel_paths=paths,glyph_paths=[[[p.x,p.y] for p in s] for s in glyph.strokes],quality=quality))
    panel=Image.new('RGB',(760,280),'white');d=ImageDraw.Draw(panel)
    label=ImageFont.truetype(FONT,17)
    d.text((10,5),f"{entry['character']} · {entry['id']} · 候选路径 {len(paths)} / 短路径 {quality['short_count']}",font=label,fill='#243247')
    for x,title in [(10,'原图放大'),(260,'二值化'),(510,'候选路径叠加')]:
        d.text((x,33),title,font=label,fill='#445566')
    panel.paste(working.convert('RGB'),(10,65))
    panel.paste(Image.fromarray((~mask[16:-16,16:-16]).astype('uint8')*255).convert('RGB'),(260,65))
    overlay=working.convert('RGB');od=ImageDraw.Draw(overlay)
    for index,s in enumerate(paths):
        xy=[(x-16,y-16) for x,y in s]
        color='#f08010' if quality['paths'][index]['short'] else '#006ad4'
        if len(xy)>1:od.line(xy,fill=color,width=1)
        else:
            x,y=xy[0];od.ellipse((x-1,y-1,x+1,y+1),fill=color)
    panel.paste(overlay,(510,65));panel.save(out/'panels'/f"{entry['id']}.png")
    assert sha((out/entry['file']).read_bytes())==entry['sha256']
    return row


def report(out, manifest, rows):
    completed=[r for r in rows if r['status']=='completed']
    summary=dict(total=len(rows),completed=len(completed),failed=len(rows)-len(completed),
                 characters=len(set(r['character'] for r in rows)),
                 empty=sum(r['candidate_count']==0 for r in completed),
                 component_changes=sum(r['reference_components']!=r['mask_components'] for r in completed),
                 retention_below_95=sum(r['reference_dark_pixel_retention']<.95 for r in completed),
                 short_hint_samples=sum(r['short_count']>0 for r in completed),
                 merged_region_samples=sum(bool(r['component_relations']['merged_reference_groups']) for r in completed),
                 editor_roundtrips_passed=len(completed),
                 algorithm_sha256=sha((Path(__file__).parent/'image_pipeline/core.py').read_bytes()),
                 versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pillow=pillow_version))
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    columns=['id','character','split','status','candidate_count','short_count','reference_components','mask_components','reference_dark_pixel_retention','added_area_vs_reference','review_flags']
    with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    import html
    cards=[]
    for r in rows:
        if r['status']!='completed':
            cards.append(f"<p>{r['id']} 失败：{html.escape(r['error'])}</p>");continue
        cards.append(f"<section><h3>{r['character']} · {r['id']} · {r['split']}</h3><img loading='lazy' src='panels/{r['id']}.png'><p>候选路径 {r['candidate_count']}；短路径提示 {r['short_count']}；连通块 {r['reference_components']} → {r['mask_components']}；暗像素保留 {r['reference_dark_pixel_retention']:.1%}。</p><p>来源条目：{html.escape(r['source_entry'])}</p></section>")
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>外部手写样本验证</title>
<style>body{{max-width:1000px;margin:30px auto;padding:0 20px;font:17px/1.7 system-ui;color:#243247}}img{{max-width:100%}}section{{border-top:1px solid #ccd;padding:15px 0}}code{{word-break:break-all}}</style>
<h1>外部手写样本验证 · 首轮基线</h1><p>{summary['characters']} 个汉字 × 4 个样本，共 {len(rows)} 张。完成 {len(completed)}，异常 {summary['failed']}。24 个字包含简单结构、包围结构、分离点画和复杂繁体字。样本编号不能证明来自不同书写者。</p>
<p>来源：<a href="{SOURCE}">AI . FREE Team · Traditional Chinese Handwriting Dataset</a>，固定版本 {REVISION}。原始数据基于 Tegaki；本次使用的是 50×50 像素手写数据图像，不是纸面照片，也没有真实笔顺标签。发布者说明低分辨率版本可能存在笔画重叠。</p>
<h2>结果与边界</h2><p>{summary['empty']} 张提取为空；{summary['component_changes']} 张二值化前后连通块数量不同；{summary['retention_below_95']} 张暗像素保留不足 95%；{summary['short_hint_samples']} 张出现短路径提示。</p>
<p>按像素重叠追踪，{summary['merged_region_samples']} 张出现原本分离区域被合并的情况。此结果相对于灰度 128 的固定参照，不应直接等同于真实笔画误连率。</p>
<p>{summary['editor_roundtrips_passed']} 个样本通过可适用的编辑、撤销重做、保存载入和字体导出回读检查。这证明这些样本上的数据操作一致性，不证明字形修正正确或奎享显示正确。</p>
<p>观察到“十”会产生不同数量的候选路径，“口”可成为单条闭合路径。当前算法保留的是几何连通关系，不能据此恢复真实落笔、抬笔和笔顺。<a href="FINDINGS.md">查看本轮发现</a></p>
<p>暗像素参照是放大图像中灰度小于 128 的像素，不是人工真值。连通块变化可能来自噪声去除或笔画合并，需要人工判断。短路径不等于断笔，候选数量不等于真实笔画数；本轮不能计算漏笔率、误连率、笔顺准确率或人工纠正成本。</p>
<p>全图统一放大到 200×200、白边 16 像素，冻结使用已有四字实验参数；没有按新样本调参，也没有采用原照片专用的边缘连通块删除。放大不会恢复丢失细节。按字符分为 development/evaluation 各 48 张；这是首次基线，未来若依据 evaluation 调参，该部分即成为回归集，需要另设未见验收集。</p>
<h2>来源与许可</h2><p>本数据集由 AI . FREE Team 改作开发自 STUST EECS_Chinese MNIST（总集）。此处保留来源说明。README 标示 CC BY-NC-SA 4.0，而仓库 License 文本为 CC BY-SA 4.0；本次按较严格的非商业、署名、相同方式共享范围进行验证，样本与派生图不并入产品素材。上游两份说明已原样保存在 originals。派生处理：放大、二值化及路径叠加。</p>
<p><a href="manifest.json">固定样本及校验清单</a> · <a href="results.csv">指标表</a> · <a href="results.json">完整结果</a> · <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a></p>
<h2>逐样本对照</h2>{''.join(cards)}</html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('downloads',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    for folder in ['paths','panels','temporary']:(out/folder).mkdir()
    manifest=freeze_samples(args.downloads,out)
    rows=[]
    for i,entry in enumerate(manifest['samples']):
        try:rows.append(evaluate(entry,out))
        except Exception as error:
            rows.append(dict(**entry,status='failed',error=f'{type(error).__name__}: {error}'))
        if (i+1)%12==0:print(f'Processed {i+1}/{len(manifest["samples"])}',flush=True)
    report(out,manifest,rows)


if __name__=='__main__':main()
