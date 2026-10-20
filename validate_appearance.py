"""Appearance-first evaluation: no normative order or per-stroke matching gate."""
import argparse
import json
from pathlib import Path
from dataclasses import replace
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from gfont_core import GFont,GFontMetadata,Glyph,Point,GFontV5Reader,GFontV5Writer
from image_pipeline.appearance_metrics import render_ink,compare_ink,geometry,travel
from validate_recorded_trajectories import read_record,normalize,extract
from validate_public_handwriting import RECIPE,FONT,sha,save_json


def export_roundtrip(paths,cp):
    # Working image -> 1000-unit font -> writer/reader -> same working image.
    glyph=Glyph(cp,[[Point(float(x*5),float(y*5)) for x,y in s] for s in paths])
    metadata=replace(GFontMetadata(),name='AppearanceValidation',glyph_count=1)
    font=GFont(metadata,{cp:glyph},[cp])
    loaded=GFontV5Reader.loads(GFontV5Writer.dumps(font))
    recovered=[[[p.x/5,p.y/5] for p in s] for s in loaded.glyphs[cp].strokes]
    assert len(recovered)==len(paths)
    for a,b in zip(paths,recovered):
        assert len(a)==len(b) and np.allclose(a,b,atol=.0001,rtol=0)
    return recovered


def difference(reference,predicted):
    a=reference<128;b=predicted<128
    colors=np.full((*a.shape,3),255,dtype='uint8')
    colors[a&b]=(65,75,90);colors[a&~b]=(218,50,73);colors[b&~a]=(0,137,196)
    return Image.fromarray(colors)


def make_panel(out,key,char,width,reference,images,scores):
    im=Image.new('RGB',(1100,310),'white');d=ImageDraw.Draw(im);font=ImageFont.truetype(FONT,16)
    d.text((8,5),f'{char} / {key} · 模拟笔宽 {width} 像素 · 深灰重合、红色漏画、蓝色多画',font=font,fill='#243247')
    columns=[('参照外观',Image.fromarray(reference)),('默认方案重绘',Image.fromarray(images['baseline'])),
             ('默认差异',difference(reference,images['baseline'])),('保护方案重绘',Image.fromarray(images['protected'])),
             ('保护差异',difference(reference,images['protected']))]
    for i,(title,image) in enumerate(columns):
        x=220*i+8;d.text((x,36),title,font=font,fill='#334455');im.paste(image,(x,65))
    for i,mode in [(1,'baseline'),(3,'protected')]:
        s=scores[mode];d.text((220*i+8,275),f"IoU {s['overlap_iou']:.1%} / 漏 {s['missing_fraction']:.1%}",font=font,fill='#334455')
    im.save(out/'panels'/f'{key}.png')


def report(out,rows):
    summaries=[]
    for width in (3,7):
        for mode in ('baseline','protected'):
            group=[r for r in rows if r['width']==width and r['mode']==mode]
            avg=lambda k:float(np.mean([r[k] for r in group]))
            summaries.append(dict(width=width,mode=mode,cases=len(group),
                mean_iou=avg('overlap_iou'),mean_soft_iou=avg('soft_overlap_iou'),
                mean_missing=avg('missing_fraction'),mean_extra=avg('extra_fraction'),
                mean_reference_p95=avg('reference_to_predicted_p95'),mean_predicted_p95=avg('predicted_to_reference_p95'),
                total_pen_lifts=sum(r['pen_lift_transitions'] for r in group),
                mean_air_travel=avg('pen_up_length'),mean_retrace_fraction=avg('retraced_grid_fraction')))
    save_json(out/'results.json',dict(summary=summaries,rows=rows))
    table=''.join(f"<tr><td>{s['width']}</td><td>{'默认' if s['mode']=='baseline' else '保护'}</td><td>{s['mean_iou']:.1%}</td><td>{s['mean_soft_iou']:.1%}</td><td>{s['mean_missing']:.1%}</td><td>{s['mean_extra']:.1%}</td><td>{s['mean_reference_p95']:.2f} / {s['mean_predicted_p95']:.2f}</td></tr>" for s in summaries)
    # Lowest overlap first, regardless of algorithm: no hand-picked successes.
    keys=sorted(set(r['id'] for r in rows),key=lambda key:min(r['overlap_iou'] for r in rows if r['id']==key))
    cards=''.join(f"<details><summary>{key}</summary><img loading='lazy' src='panels/{key}.png'></details>" for key in keys)
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>字形还原优先评估</title>
<style>body{{max-width:1160px;margin:28px auto;padding:0 18px;font:17px/1.7 system-ui;color:#243247}}table{{border-collapse:collapse}}th,td{{border:1px solid #ccd;padding:8px;font-size:15px}}img{{max-width:100%}}summary{{cursor:pointer}}details{{padding:10px;border-bottom:1px solid #ddd}}</style>
<h1>以最终字形为主：同笔宽重绘与差异</h1>
<p>不再以笔画顺序、方向或分笔方式一致作为主要验收项。同一条线即使反向或分段，只要落笔覆盖相同，就得到相同的外观评分；抬笔移动不会画成连线。</p>
<p>48 份已知记录，线宽 3/7 两种条件、默认/保护两种方案，共 192 次评估。所有候选经过 GFont 写入/读回，再以统一圆形笔尖重绘。未进行逐图缩放、配准或平移来提高分数，也未调整提取参数。</p>
<h2>主要结果：每组 48 个样本的平均值</h2><table><tr><th>笔宽 px</th><th>方案</th><th>墨迹 IoU</th><th>灰度墨迹 IoU</th><th>漏画比例</th><th>多画比例</th><th>中心线 P95 距离 px<br>参照→候选 / 候选→参照</th></tr>{table}</table>
<p>IoU 为重合墨迹面积/联合面积；漏画比例以参照墨迹为分母，多画比例以候选墨迹为分母。红色表示参照有而候选没有，蓝色表示候选多出的部分；边缘位置偏差也会产生红蓝条带，不能把红色都理解为完整笔画丢失。二值墨迹使用灰度&lt;128，灰度 IoU 使用 1−灰度/255 的逐像素最小值/最大值。中心线指标忽略分笔和顺序，不是轮廓边界距离。</p>
<h2>机器相关辅助指标</h2><p>完整 JSON 另有落笔长度、相邻路径之间的抬笔次数和空走距离，以及 1 像素网格上重复经过同一无向边的长度比例。重复描画可能影响墨色，但该比例只是几何代理；普通交叉点不视为重复边。不含从机器原点出发、回零、速度、加速度、墨水或压力模型。单点停留另行计数，尚不能估计其墨色。</p>
<h2>笔宽与方法边界</h2><p>本轮笔宽是工作图像像素，不是毫米；两种笔宽是同一批轨迹的重复条件，不是新书写者。输入与候选都用方向无关的圆形笔尖覆盖模型：4 倍分辨率下计算线段及圆端的并集，再按像素平均。它取代了旧测试绘图器的方向相关像素偏差；本轮重新提取，因此不要与旧逐笔匹配百分比直接比较。</p>
<p>这里是恒定笔宽的轨迹重绘图，不是纸面照片，也不能验证毛笔粗细或真实机器墨色。后续需用实际笔尖宽度与字框毫米尺寸校准。当前未给出任意“合格阈值”，这些是几何诊断结果，不是所有字体准确率。</p>
<p><a href="results.json">每图指标与辅助运行量</a> · <a href="plan.json">固定方法、参数与源码校验</a> · <a href="FINDINGS.md">结论说明</a></p>
<p>来源沿用 <a href="https://github.com/tegaki/tegaki/tree/7a74e442c4130cccc226a7e7c2b683ac94c0cccb/tegaki-lab">Tegaki / tegaki-lab</a> 的记录；AUTHORS 列出 Mathieu Blondel，上游随附 GNU GPL v2 COPYING。来源文件与许可保存在 ../trajectory_sources_v1；本报告为重新栅格化和差异叠加的派生验证，非产品字体。</p>
<h2>逐图对照（按较低重合度优先）</h2>{cards}</html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summaries),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    for folder in ['inputs','paths','panels']:(out/folder).mkdir()
    project=Path(__file__).parent;source=project/'artifacts/trajectory_sources_v1'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    records=[e for e in manifest['files'] if e['file'].endswith('.xml')]
    save_json(out/'plan.json',dict(source_manifest=manifest,recipe=RECIPE,widths=[3,7],
        renderer='direction-invariant round capsules; integer coordinates are pixel centers; 4x sampling; box mean',
        foreground_threshold=128,geometry_sample_spacing=.5,retrace_grid=1,
        normalization='200px canvas,160px glyph extent; pad16 during extraction; no post-hoc alignment',
        mode='appearance_first; order is auxiliary; known-record regression',
        sha256={name:sha((project/name).read_bytes()) for name in ['image_pipeline/appearance_metrics.py','image_pipeline/core.py','image_pipeline/component_guard.py','validate_recorded_trajectories.py','validate_appearance.py']}))
    rows=[]
    for i,e in enumerate(records):
        raw=(source/e['file']).read_bytes();assert sha(raw)==e['sha256']
        char,original=read_record(raw);truth=normalize(original);reference_travel=travel(truth)
        writer='native1' if 'japanese-native1' in e['file'] else 'learner1'
        for width in (3,7):
            key=f'U{ord(char):04X}_{writer}_w{width}'
            reference=render_ink(truth,width);Image.fromarray(reference).save(out/'inputs'/f'{key}.png')
            gray=np.pad(reference,16,constant_values=255);images={};scores={}
            for mode in ('baseline','protected'):
                padded=extract(gray,mode)
                paths=[[[x-16,y-16] for x,y in s] for s in padded]
                paths=export_roundtrip(paths,ord(char))
                images[mode]=render_ink(paths,width);scores[mode]=compare_ink(reference,images[mode])
                row=dict(id=key,character=char,width=width,mode=mode,writer=writer,
                    **scores[mode],**geometry(truth,paths),**travel(paths),reference_travel=reference_travel,
                    gfont_roundtrip=True)
                rows.append(row)
                save_json(out/'paths'/f'{key}_{mode}.json',dict(strokes=paths,coordinate_space='200px working image',status='candidate'))
            make_panel(out,key,char,width,reference,images,scores)
        assert sha((source/e['file']).read_bytes())==e['sha256']
        if (i+1)%8==0:print(f'Appearance checked {i+1}/{len(records)} records',flush=True)
    report(out,rows)


if __name__=='__main__':main()
