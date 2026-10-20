"""Compare an opt-in seed guard against the frozen public-image baseline."""
import argparse
import json
import stat
import tempfile
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
from gfont_core import Glyph,Point
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes,simplify
from image_pipeline.component_guard import preserve_components
from image_pipeline.quality import inspect_glyph
from validate_public_handwriting import RECIPE,FONT,freeze_samples,save_json,sha,component_relations,check_editor

NEW_CHARACTERS='三上下不之也六八入力又子見角豆足身金長風魚馬黑齒'


def holes(mask):
    return int(ndi.label(ndi.binary_fill_holes(mask)&~mask)[1])


def analyse(mask,reference,cp,temp):
    thin=skeletonize(mask);thin,pruned=prune_spurs(thin,3)
    graph=graph_from_skeleton(thin);candidates=candidate_strokes(graph)
    assert sorted(i for s in candidates for i in s['edge_ids'])==list(range(len(graph['edges'])))
    paths=[simplify(s['points'],.65) for s in candidates]
    glyph=Glyph(cp,[])
    if paths:
        points=np.array([p for s in paths for p in s]);low,high=points.min(0),points.max(0)
        scale=800/max(float(max(high-low)),1);offset=np.array([500,500])-(low+high)*scale/2
        glyph.strokes=[[Point(float(x*scale+offset[0]),float(y*scale+offset[1])) for x,y in s] for s in paths]
    quality=inspect_glyph(glyph,1000)
    with tempfile.TemporaryDirectory(dir=temp) as folder:checks=check_editor(glyph,Path(folder))
    return dict(relations=component_relations(reference,mask),
                components=int(ndi.label(mask,np.ones((3,3)))[1]),holes=holes(mask),
                skeleton_components=int(ndi.label(thin,np.ones((3,3)))[1]),
                seed_pixels_lost=int((reference&~mask).sum()),
                added_pixels=int((mask&~reference).sum()),
                candidate_count=len(paths),short_count=quality['short_count'],
                pruned_pixels=pruned,checks=checks),paths


def render(out,entry,gray,reference,old,new,oldpaths,newpaths):
    im=Image.new('RGB',(1100,290),'white');d=ImageDraw.Draw(im)
    font=ImageFont.truetype(FONT,17)
    d.text((10,5),f"{entry['character']} / {entry['id']} / {entry['cohort']}",font=font,fill='#223344')
    source=Image.fromarray(gray[16:-16,16:-16]).convert('RGB')
    images=[source,Image.fromarray((~old[16:-16,16:-16]).astype('uint8')*255).convert('RGB'),
            Image.fromarray((~new[16:-16,16:-16]).astype('uint8')*255).convert('RGB')]
    for paths in [oldpaths,newpaths]:
        overlay=source.copy();draw=ImageDraw.Draw(overlay)
        for path in paths:
            xy=[(x-16,y-16) for x,y in path]
            if len(xy)>1:draw.line(xy,fill='#1268cf',width=1)
            else:
                x,y=xy[0];draw.ellipse((x-1,y-1,x+1,y+1),fill='#1268cf')
        images.append(overlay)
    for i,(label,image) in enumerate(zip(['原图放大','旧方案二值图','保护方案二值图','旧候选路径','保护后候选路径'],images)):
        d.text((i*220+10,35),label,font=font,fill='#334455');im.paste(image,(i*220+10,70))
    im.save(out/'panels'/f"{entry['id']}.png")


def write_report(out,plan,rows):
    summary={}
    for cohort in ['known_regression','new_characters']:
        group=[r for r in rows if r['cohort']==cohort]
        summary[cohort]={}
        for mode in ['baseline','guarded']:
            summary[cohort][mode]=dict(samples=len(group),
                merged=sum(bool(r[mode]['relations']['merged_reference_groups']) for r in group),
                removed=sum(bool(r[mode]['relations']['removed_reference_components']) for r in group),
                split=sum(bool(r[mode]['relations']['split_reference_components']) for r in group),
                hole_changes=sum(r[mode]['holes']!=r['reference_holes'] for r in group),
                skeleton_component_changes=sum(r[mode]['components']!=r[mode]['skeleton_components'] for r in group),
                empty=sum(r[mode]['candidate_count']==0 for r in group),
                short_hint_samples=sum(r[mode]['short_count']>0 for r in group))
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    table=''
    for cohort,modes in summary.items():
        for mode,s in modes.items():
            table+=f"<tr><td>{'已知回归组' if cohort=='known_regression' else '新增汉字组'}</td><td>{'旧方案' if mode=='baseline' else '分离保护'}</td><td>{s['samples']}</td><td>{s['merged']}</td><td>{s['removed']}</td><td>{s['split']}</td><td>{s['hole_changes']}</td><td>{s['skeleton_component_changes']}</td><td>{s['short_hint_samples']}</td></tr>"
    cards=[]
    for r in rows:
        a,b=r['baseline'],r['guarded']
        cards.append(f"<details><summary>{r['character']} · {r['id']} · 连通块 {a['components']} → {b['components']}；候选路径 {a['candidate_count']} → {b['candidate_count']}</summary><img loading='lazy' src='panels/{r['id']}.png'></details>")
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>分离结构保护对比</title>
<style>body{max-width:1200px;margin:28px auto;padding:0 18px;font:17px/1.7 system-ui;color:#243247}table{border-collapse:collapse;font-size:15px}td,th{padding:8px;border:1px solid #ccd}img{max-width:100%}details{padding:8px;border-bottom:1px solid #ddd}summary{cursor:pointer}</style>
<h1>分离结构保护：可选预处理方案</h1>
<p>本轮保护的是指定参照里的分离区域，不是自动恢复真实笔画。当前默认算法未替换，原有字形和字体未修改。</p>
<p>对比包括原有 24 字/96 张回归样本，以及新增 24 字/96 张样本，共 48 字/192 张。新增字符在算法运行前固定，使用本地缓存的同一公开数据集；不是新的数据来源，也没有书写者级别独立性保证。</p>
<h2>结果（单位：样本张数）</h2><table><tr><th>样本组</th><th>方案</th><th>样本</th><th>区域合并</th><th>区域消失</th><th>区域拆分</th><th>孔洞数变化</th><th>骨架连通块变化</th><th>短路径提示</th></tr>'''+table+'''</table>
<p>区域合并、消失、拆分相对于灰度小于 128 的种子掩码；孔洞数也与此参照比较。骨架连通块变化指剪枝后骨架相对该方案二值图的变化。短路径是提示，不是错误数。</p>
<h2>不能误读的结论</h2><p>保护方案保留每个种子像素，阻止不同种子连通块接触，因此种子不合并、不消失是算法约束，不是独立证明“识别准确率提高”。同一块内部孔洞仍可能改变，交叉点的真实笔顺仍未知。</p>
<p>反例测试已验证：如果同一真实笔画本来因浅色而断开，保护方案也会保留断裂；完全没有深色种子的浅色笔画不会被自动补回。因此它暂时适用于明确指定参照的实验，不能直接应用为所有照片的默认规则。</p>
<p>每张图两个方案都运行了适用的编辑、撤销重做、保存载入和导出回读检查；不代表人工修正内容或奎享显示已通过。</p>
<p><a href="plan.json">运行前固定方案与样本清单</a> · <a href="results.json">完整指标</a> · <a href="FINDINGS.md">结论说明</a></p>
<h2>来源</h2><p>AI . FREE Team，Traditional Chinese Handwriting Dataset，改作自 STUST EECS_Chinese MNIST（总集）。与上一轮相同的 50×50 手写数据图像，不是纸面照片。按上游 README 的 CC BY-NC-SA 4.0 范围保留署名及相同方式共享；License 文件的不同标示也已保留。派生图包含放大、二值化、路径叠加，不并入产品字体素材。</p>
<p><a href="https://github.com/AI-FREE-Team/Traditional-Chinese-Handwriting-Dataset">上游来源</a> · <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">许可</a></p>
<h2>逐样本对比</h2>'''+''.join(cards)+'</html>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('downloads',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    for name in ['panels','paths','temporary']:(out/name).mkdir()
    fresh=freeze_samples(args.downloads,out,characters=NEW_CHARACTERS)
    oldroot=Path(__file__).parent/'artifacts/external_handwriting_v1'
    old=json.loads((oldroot/'manifest.json').read_text(encoding='utf-8'))
    assert not set(NEW_CHARACTERS)&{e['character'] for e in old['samples']}
    samples=[]
    for e in old['samples']:
        data=(oldroot/e['file']).read_bytes();assert sha(data)==e['sha256']
        dest=out/e['file'];dest.write_bytes(data);dest.chmod(stat.S_IREAD)
        samples.append(dict(**e,cohort='known_regression'))
    samples.extend(dict(**e,cohort='new_characters') for e in fresh['samples'])
    plan=dict(samples=samples,recipe=RECIPE,reference='gray < 128 after LANCZOS 200x200, pad 16',
              selection='new characters fixed before outcome inspection; 4 entries per character by source-entry hash',
              core_sha256=sha((Path(__file__).parent/'image_pipeline/core.py').read_bytes()),
              guard_sha256=sha((Path(__file__).parent/'image_pipeline/component_guard.py').read_bytes()),
              baseline_manifest_sha256=sha((oldroot/'manifest.json').read_bytes()),
              fresh_manifest_sha256=sha((out/'manifest.json').read_bytes()),
              guarantee='Seed topology constraints are construction guarantees, not accuracy metrics.')
    save_json(out/'plan.json',plan)  # Persist the test definition BEFORE any extraction.
    rows=[]
    for i,e in enumerate(samples):
        source=(out/e['file']).read_bytes();assert sha(source)==e['sha256']
        gray=np.pad(np.asarray(Image.open(out/e['file']).convert('L').resize((200,200),Image.Resampling.LANCZOS)),16,constant_values=255)
        reference=gray<128;baseline=preprocess(gray,**RECIPE)
        baseline[:16]=False;baseline[-16:]=False;baseline[:,:16]=False;baseline[:,-16:]=False
        guarded,diagnostics=preserve_components(reference,baseline)
        a,ap=analyse(baseline,reference,e['codepoint'],out/'temporary')
        b,bp=analyse(guarded,reference,e['codepoint'],out/'temporary')
        rows.append(dict(id=e['id'],character=e['character'],cohort=e['cohort'],reference_holes=holes(reference),baseline=a,guarded=b,guard_diagnostics=diagnostics))
        save_json(out/'paths'/f"{e['id']}.json",dict(baseline=ap,guarded=bp))
        render(out,e,gray,reference,baseline,guarded,ap,bp)
        assert sha((out/e['file']).read_bytes())==e['sha256']
        if (i+1)%24==0:print(f'Compared {i+1}/{len(samples)}',flush=True)
    write_report(out,plan,rows)


if __name__=='__main__':main()
