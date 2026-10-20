"""Regress hole protection on the SAME 192 known samples, without tuning."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image,ImageDraw,ImageFont
from image_pipeline.core import preprocess,skeletonize,prune_spurs
from image_pipeline.component_guard import preserve_components
from compare_component_guard import analyse,holes
from validate_public_handwriting import RECIPE,FONT,sha,save_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    for folder in ['panels','paths','temporary']:(out/folder).mkdir()
    project=Path(__file__).parent;source=project/'artifacts/component_guard_v1'
    plan=json.loads((source/'plan.json').read_text(encoding='utf-8'))
    previous=json.loads((source/'results.json').read_text(encoding='utf-8'))
    lookup={r['id']:r for r in previous['rows']}
    save_json(out/'plan.json',dict(source_plan_sha256=sha((source/'plan.json').read_bytes()),
        source_plan=str((source/'plan.json').resolve()),samples=plan['samples'],recipe=RECIPE,
        preserve_holes=True,reference='gray < 128; 200x200 LANCZOS; white pad 16',
        guard_sha256=sha((project/'image_pipeline/component_guard.py').read_bytes()),
        core_sha256=sha((project/'image_pipeline/core.py').read_bytes()),
        scope='Known 192-sample regression, not an unseen or cross-dataset evaluation'))
    label=ImageFont.truetype(FONT,17);rows=[]
    for i,e in enumerate(plan['samples']):
        raw=(source/e['file']).read_bytes();assert sha(raw)==e['sha256']
        gray=np.pad(np.asarray(Image.open(source/e['file']).convert('L').resize((200,200),Image.Resampling.LANCZOS)),16,constant_values=255)
        seed=gray<128;candidate=preprocess(gray,**RECIPE)
        candidate[:16]=False;candidate[-16:]=False;candidate[:,:16]=False;candidate[:,-16:]=False
        old,_=preserve_components(seed,candidate)
        assert holes(old)==lookup[e['id']]['guarded']['holes']
        new,diagnostics=preserve_components(seed,candidate,preserve_holes=True)
        result,paths=analyse(new,seed,e['codepoint'],out/'temporary')
        thin,_=prune_spurs(skeletonize(new),3)
        result['skeleton_holes']=holes(thin)
        prior=lookup[e['id']]['guarded']
        rows.append(dict(id=e['id'],character=e['character'],reference_holes=holes(seed),
                         previous=prior,current=result,diagnostics=diagnostics))
        save_json(out/'paths'/f"{e['id']}.json",dict(pixel_paths=paths,status='candidate_unconfirmed'))
        panel=Image.new('RGB',(1100,290),'white');draw=ImageDraw.Draw(panel)
        draw.text((10,4),f"{e['character']} / {e['id']} · 孔洞 {holes(seed)} / {holes(old)} / {holes(new)}（参照 / 上轮 / 本轮）",font=label,fill='#223344')
        source_image=Image.fromarray(gray[16:-16,16:-16]).convert('RGB')
        overlay=source_image.copy();od=ImageDraw.Draw(overlay)
        for path in paths:
            xy=[(x-16,y-16) for x,y in path]
            if len(xy)>1:od.line(xy,fill='#1864cb',width=1)
            else:
                x,y=xy[0];od.ellipse((x-1,y-1,x+1,y+1),fill='#1864cb')
        diff=np.repeat(np.where(new,90,255).astype('uint8')[:,:,None],3,axis=2)
        diff[old&~new]=(220,35,65);diff[new&~old]=(0,150,80)
        images=[source_image,Image.fromarray((~old[16:-16,16:-16]).astype('uint8')*255),Image.fromarray((~new[16:-16,16:-16]).astype('uint8')*255),Image.fromarray(diff[16:-16,16:-16]),overlay]
        for j,(title,image) in enumerate(zip(['原图放大','上轮：仅分离保护','本轮：另加孔洞保护','红：本轮未添加像素','本轮候选路径'],images)):
            draw.text((j*220+8,36),title,font=label,fill='#334455');panel.paste(image,(j*220+8,70))
        panel.save(out/'panels'/f"{e['id']}.png")
        assert sha((source/e['file']).read_bytes())==e['sha256']
        if (i+1)%24==0:print(f'Checked {i+1}/192',flush=True)
    summary=dict(samples=len(rows),
        previous_hole_changes=sum(r['previous']['holes']!=r['reference_holes'] for r in rows),
        current_hole_changes=sum(r['current']['holes']!=r['reference_holes'] for r in rows),
        current_merges=sum(bool(r['current']['relations']['merged_reference_groups']) for r in rows),
        current_removed=sum(bool(r['current']['relations']['removed_reference_components']) for r in rows),
        current_splits=sum(bool(r['current']['relations']['split_reference_components']) for r in rows),
        skeleton_hole_changes=sum(r['current']['skeleton_holes']!=r['current']['holes'] for r in rows),
        skeleton_component_changes=sum(r['current']['skeleton_components']!=r['current']['components'] for r in rows),
        previous_short_samples=sum(r['previous']['short_count']>0 for r in rows),
        current_short_samples=sum(r['current']['short_count']>0 for r in rows),
        previous_short_paths=sum(r['previous']['short_count'] for r in rows),
        current_short_paths=sum(r['current']['short_count'] for r in rows),
        more_candidates=sum(r['current']['candidate_count']>r['previous']['candidate_count'] for r in rows),
        less_candidates=sum(r['current']['candidate_count']<r['previous']['candidate_count'] for r in rows),
        empty=sum(r['current']['candidate_count']==0 for r in rows))
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    cards=[]
    for r in rows:
        cards.append(f"<details><summary>{r['character']} · {r['id']} · 孔洞（参照/上轮/本轮）{r['reference_holes']}/{r['previous']['holes']}/{r['current']['holes']} · 路径 {r['previous']['candidate_count']} → {r['current']['candidate_count']}</summary><img loading='lazy' src='panels/{r['id']}.png'></details>")
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>孔洞保护回归对比</title>
<style>body{{max-width:1160px;margin:30px auto;padding:0 18px;font:17px/1.7 system-ui;color:#243247}}img{{max-width:100%}}summary{{cursor:pointer}}details{{padding:10px;border-bottom:1px solid #ccd}}</style>
<h1>孔洞保护：192 张已知样本回归</h1>
<p>在分离保护上增加 preserve_holes=True。默认值仍为 False；原来的预处理参数、灰度参照、尺寸及默认算法均未改动。</p>
<p>相对参照的孔洞数变化：{summary['previous_hole_changes']} → {summary['current_hole_changes']} 张。区域合并 {summary['current_merges']}，区域消失 {summary['current_removed']}，区域拆分 {summary['current_splits']}。骨架阶段孔洞数变化 {summary['skeleton_hole_changes']}，连通块变化 {summary['skeleton_component_changes']}。</p>
<p>有短路径提示的样本：{summary['previous_short_samples']} → {summary['current_short_samples']}；短路径总数：{summary['previous_short_paths']} → {summary['current_short_paths']}。候选路径增加 {summary['more_candidates']} 张、减少 {summary['less_candidates']} 张。提示并不等于错误，候选路径数量也不等于真实笔画数。</p>
<p>192 张都完成适用的编辑、撤销重做、保存载入和导出回读检查。没有真实笔画标注或奎享实测，不生成“已修复字体”。</p>
<h2>边界</h2><p>孔洞与连通块保持属于算法约束，不是字形准确率。规则以八邻域前景、四邻域背景判断，保留原参照像素，并拒绝会分割或消灭背景区域的新增像素。孔洞面积和轮廓仍可能改变，小孔洞可能缩小到很小。错误参照中的断笔、噪点和孔洞也会被保留。</p>
<p>这批图已在上一轮查看，属于已知回归集，不是新的泛化验证。下一阶段需要带真实落笔/抬笔轨迹的数据或人工逐笔标注，避免仅优化参照掩码指标。</p>
<p>来源：<a href="https://github.com/AI-FREE-Team/Traditional-Chinese-Handwriting-Dataset">AI . FREE Team · Traditional Chinese Handwriting Dataset</a>，改作自 STUST EECS_Chinese MNIST（总集）。同一批 50×50 图像经放大、二值化及路径叠加。按上游 README 的 <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a> 范围用于非商业验证；上游不同 License 标示及原始样本保存在上轮目录。</p>
<p><a href="plan.json">固定参数及样本校验清单</a> · <a href="results.json">完整指标</a></p><h2>逐图对比</h2>{''.join(cards)}</html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
