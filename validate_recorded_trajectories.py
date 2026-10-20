"""Recorded-trajectory benchmark. The raster input is synthetic, not a photo."""
import argparse
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes,simplify
from image_pipeline.component_guard import preserve_components
from image_pipeline.trajectory_metrics import match_strokes
from validate_public_handwriting import RECIPE,FONT,sha,save_json

WIDTHS=(3,7)
METRICS=dict(geometry_tolerance=3.,endpoint_tolerance=5.,progress_tolerance=5.)
PALETTE=['#1565c0','#d43b3b','#188851','#9b45b3','#cf7510','#0097a7','#6b5f40','#dc4281']


def read_record(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML declarations with entities are not accepted')
    root=ET.fromstring(data)
    char=root.findtext('utf8','').strip()
    if root.tag!='character' or len(char)!=1:raise ValueError('Invalid character record')
    paths=[]
    for stroke in root.findall('./strokes/stroke'):
        points=np.array([[float(p.attrib['x']),float(p.attrib['y'])] for p in stroke.findall('point')])
        if points.ndim!=2 or points.shape[1]!=2 or not len(points) or not np.isfinite(points).all():
            raise ValueError('Empty or invalid recorded stroke')
        if np.max(np.abs(points))>1e7:raise ValueError('Coordinate out of bounds')
        paths.append(points)
    if not paths:raise ValueError('No recorded strokes')
    return char,paths


def normalize(paths):
    allpoints=np.concatenate(paths);low,high=allpoints.min(0),allpoints.max(0)
    scale=160/max(float(max(high-low)),1.)
    offset=np.array([100,100])-(low+high)*scale/2
    return [((p*scale)+offset).tolist() for p in paths]


def rasterize(paths,width):
    # Uniform round-tipped lines at 4x resolution; no pen-up connectors.
    im=Image.new('L',(800,800),255);d=ImageDraw.Draw(im);radius=width*2
    for stroke in paths:
        xy=[(x*4,y*4) for x,y in stroke]
        if len(xy)>1:d.line(xy,fill=0,width=width*4,joint='curve')
        for x,y in xy:d.ellipse((x-radius,y-radius,x+radius,y+radius),fill=0)
    return im.resize((200,200),Image.Resampling.LANCZOS)


def extract(gray,mode):
    mask=preprocess(gray,**RECIPE)
    mask[:16]=False;mask[-16:]=False;mask[:,:16]=False;mask[:,-16:]=False
    if mode=='protected':mask,_=preserve_components(gray<128,mask,preserve_holes=True)
    thin,removed=prune_spurs(skeletonize(mask),3)
    graph=graph_from_skeleton(thin);candidates=candidate_strokes(graph)
    assert sorted(e for s in candidates for e in s['edge_ids'])==list(range(len(graph['edges'])))
    return [simplify(s['points'],.65) for s in candidates]


def draw_paths(paths,shift=0):
    im=Image.new('RGB',(200,200),'white');d=ImageDraw.Draw(im)
    for i,stroke in enumerate(paths):
        xy=[(x-shift,y-shift) for x,y in stroke];color=PALETTE[i%len(PALETTE)]
        if len(xy)>1:d.line(xy,fill=color,width=2)
        x,y=xy[0];d.ellipse((x-2,y-2,x+2,y+2),fill=color)
        d.text((x+3,y-10),str(i+1),fill=color)
    return im


def panel(out,key,char,writer,width,truth,input_image,results,paths):
    im=Image.new('RGB',(900,320),'white');d=ImageDraw.Draw(im);font=ImageFont.truetype(FONT,17)
    d.text((10,5),f'{char} / {writer} / 线宽 {width} · 记录笔画 {len(truth)}',font=font,fill='#223344')
    columns=[('记录轨迹（点为起点）',draw_paths(truth)),('重绘输入',input_image),
             ('默认提取',draw_paths(paths['baseline'],16)),('结构保护提取',draw_paths(paths['protected'],16))]
    for i,(title,image) in enumerate(columns):
        x=i*225+8;d.text((x,38),title,font=font,fill='#334455');im.paste(image,(x,70))
        if i>=2:
            r=results[['baseline','protected'][i-2]]
            d.text((x,280),f"路径 {r['predicted_count']} / 匹配 {r['matched']}",font=font,fill='#334455')
    im.save(out/'panels'/f'{key}.png')


def aggregate(rows):
    summaries=[]
    for width in WIDTHS:
        for mode in ['baseline','protected']:
            group=[r for r in rows if r['width']==width and r['mode']==mode]
            truth=sum(r['reference_count'] for r in group);pred=sum(r['predicted_count'] for r in group);matched=sum(r['matched'] for r in group)
            summaries.append(dict(width=width,mode=mode,cases=len(group),reference_strokes=truth,
                predicted_strokes=pred,matched_strokes=matched,precision=matched/pred if pred else 0,
                recall=matched/truth if truth else 0,count_equal=sum(r['count_equal'] for r in group),
                full_unordered=sum(r['full_unordered_match'] for r in group),
                full_ordered_directed=sum(r['full_ordered_directed_match'] for r in group)))
    return summaries


def report(out,rows,cards):
    summary=aggregate(rows);save_json(out/'results.json',dict(summary=summary,rows=rows))
    table=''.join(f"<tr><td>{s['width']}</td><td>{'默认' if s['mode']=='baseline' else '结构保护'}</td><td>{s['count_equal']}/{s['cases']}</td><td>{s['full_unordered']}/{s['cases']}</td><td>{s['full_ordered_directed']}/{s['cases']}</td><td>{s['matched_strokes']}/{s['predicted_strokes']} ({s['precision']:.1%})</td><td>{s['matched_strokes']}/{s['reference_strokes']} ({s['recall']:.1%})</td></tr>" for s in summary)
    details=''.join(f"<details><summary>{html.escape(c['title'])}</summary><img loading='lazy' src='panels/{c['key']}.png'></details>" for c in cards)
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>记录轨迹逐笔验证</title>
<style>body{{max-width:1200px;margin:28px auto;padding:0 20px;font:17px/1.7 system-ui;color:#243247}}table{{border-collapse:collapse;font-size:15px}}td,th{{border:1px solid #ccd;padding:8px}}img{{max-width:100%}}details{{padding:10px;border-bottom:1px solid #ddd}}summary{{cursor:pointer}}</style>
<h1>记录轨迹逐笔验证 · 首轮基线</h1>
<p>24 个汉字 × 上游标记的两组书写者，共 48 份不同记录。各重绘为线宽 3 和 7 的图像，形成 96 个图像条件，分别测试默认/结构保护两种方案，共 192 次提取。不能把这些重复条件当作 192 份独立手写样本。</p>
<p>原始 XML 给出有序 stroke/point 数据；本轮以记录的分笔、方向和顺序作参照，不把日语书写样本当成中文规范笔顺。没有核验书写者身份；XML 无时间戳，不分析真实时间间隔。输入是轨迹重绘图，不是纸面照片。</p>
<h2>结果</h2><table><tr><th>线宽</th><th>方案</th><th>数量相同</th><th>全字逐笔匹配<br>忽略笔间顺序/方向</th><th>另满足记录顺序/方向</th><th>匹配数/候选数</th><th>匹配数/记录数</th></tr>{table}</table>
<p>数量相同不等于分笔正确。逐笔匹配使用一对一分配，不允许一条记录匹配多条碎线；形状、两端位置和沿路径的行进过程都要满足固定容差。未匹配笔画不直接标作“漏笔”，因为也可能是错分组、错连接或超出容差。</p>
<h2>固定方法</h2><p>统一等比例放入 200×200 图，字形最长边 160，白边 16；4 倍分辨率重绘再缩小。原有预处理参数不变，剪枝 3、简化 0.65、切线拼接默认 140°。保护方案以图像灰度小于 128 为参照，不接收真实分笔信息。XML 轨迹只用于重绘与事后评分，没有参与算法连线。</p>
<p>距离容差以工作图像像素计：每隔 1 像素采样，双向最近距离各自的 95 分位均不超过 3；端点最大误差不超过 5；按弧长进度均匀采样 64 点，进度距离的 95 分位不超过 5。正向或反向之一满足全部条件才可配对；最后再检查记录顺序和正向。阈值在运行前固定，未按结果调参。有限采样和容差不能证明路径严格相等。</p>
<p>这是两组书写者、小规模、合成栅格输入上的基线；不代表所有字体、照片、规范笔顺或机器书写效果。结构约束保持不能替代逐笔正确性。</p>
<p><a href="plan.json">样本与参数校验清单</a> · <a href="results.json">完整配对明细</a> · <a href="FINDINGS.md">本轮结论</a></p>
<h2>来源与许可</h2><p><a href="https://github.com/tegaki/tegaki/tree/7a74e442c4130cccc226a7e7c2b683ac94c0cccb/tegaki-lab">Tegaki / tegaki-lab</a>，AUTHORS 列出 Mathieu Blondel。所取记录位于 data/eval/japanese-native1/s1 和 japanese-learner1/s1。上游包随附 GNU GPL v2 COPYING；原始记录、README、AUTHORS、COPYING 原样保留在 ../trajectory_sources_v1。本报告的派生图由这些记录统一重绘及叠加，不并入产品字体；修改与复现方法见本项目 validate_recorded_trajectories.py，来源和修改说明随数据保留。</p>
<h2>逐记录对照</h2>{details}</html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    for folder in ['panels','inputs','paths','reference']:(out/folder).mkdir()
    project=Path(__file__).parent;source=project/'artifacts/trajectory_sources_v1'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    records=[e for e in manifest['files'] if e['file'].endswith('.xml')]
    save_json(out/'plan.json',dict(source_manifest=manifest,widths=WIDTHS,metrics=METRICS,
        recipe=RECIPE,normalization='longest side 160 centered at (100,100), working pad 16',
        sha256={name:sha((project/name).read_bytes()) for name in ['image_pipeline/core.py','image_pipeline/component_guard.py','image_pipeline/trajectory_metrics.py','validate_recorded_trajectories.py']},
        synthetic_input=True,distinct_source_records=len(records),direction_order='as recorded, not normative Chinese order'))
    rows=[];cards=[]
    for i,e in enumerate(records):
        raw=(source/e['file']).read_bytes();assert sha(raw)==e['sha256']
        char,original=read_record(raw)
        assert ord(char)==int(Path(e['file']).stem.split('_')[-1])
        writer='native1' if 'japanese-native1' in e['file'] else 'learner1'
        truth=normalize(original);reference=[[[x+16,y+16] for x,y in s] for s in truth]
        ident=f'U{ord(char):04X}_{writer}'
        save_json(out/'reference'/f'{ident}.json',dict(character=char,strokes=truth,source_file=e['file'],source_sha256=e['sha256']))
        for width in WIDTHS:
            key=f'{ident}_w{width}';image=rasterize(truth,width);image.save(out/'inputs'/f'{key}.png')
            gray=np.pad(np.asarray(image),16,constant_values=255);results={};paths={}
            for mode in ['baseline','protected']:
                paths[mode]=extract(gray,mode)
                results[mode]=match_strokes(reference,paths[mode],**METRICS)
                rows.append(dict(id=key,character=char,writer=writer,width=width,mode=mode,**results[mode]))
                save_json(out/'paths'/f'{key}_{mode}.json',dict(strokes=paths[mode],status='candidate',coordinate_space='padded working pixels'))
            panel(out,key,char,writer,width,truth,image,results,paths)
            cards.append(dict(key=key,title=f"{char} / {writer} / 线宽 {width}：记录 {len(truth)} 笔；默认匹配 {results['baseline']['matched']}，保护匹配 {results['protected']['matched']}"))
        assert sha((source/e['file']).read_bytes())==e['sha256']
        if (i+1)%8==0:print(f'Checked {i+1}/{len(records)} records',flush=True)
    report(out,rows,cards)


if __name__=='__main__':main()
