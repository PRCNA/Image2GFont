"""Paired regression of optional bright-bridge guard; no parameter search."""
import json
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image,ImageDraw
from image_pipeline.ink_support import supported_mask,local_widths
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes
from image_pipeline.appearance_metrics import render_ink,compare_ink
from validate_public_handwriting import RECIPE,component_relations,save_json,sha
from validate_appearance import difference,export_roundtrip


def main():
    root=Path(__file__).parent;base=root/'artifacts/new_web_handwriting_v1';out=root/'artifacts/ink_support_v2'
    out.mkdir(exist_ok=False)
    for name in ('cases','panels'):(out/name).mkdir()
    inputs=sorted((base/'normalized').glob('*.png'))
    widths={r['id']:r['estimated_width'] for r in json.loads((base/'results.json').read_text())['rows']}
    save_json(out/'plan.json',dict(recipe=RECIPE,seed_threshold=128,bridge_threshold=192,
        reconstruction_width='same estimated constant width as prior evaluation; local widths not used in IoU',
        inputs={p.name:sha(p.read_bytes()) for p in inputs},
        code={n:sha((root/n).read_bytes()) for n in ('image_pipeline/ink_support.py','validate_ink_support.py')},
        scope='42 known regression images; diagnostic prototype, not unseen validation'))
    rows=[];cards=[]
    for p in inputs:
        key=p.stem;source=np.asarray(Image.open(p).convert('L'));padded=np.pad(source,16,constant_values=255)
        baseline=preprocess(padded,**RECIPE);baseline[:16]=False;baseline[-16:]=False;baseline[:,:16]=False;baseline[:,-16:]=False
        guarded,info=supported_mask(padded,baseline);modes={};images={}
        for mode,mask in [('baseline',baseline),('guarded',guarded)]:
            thin,_=prune_spurs(skeletonize(mask),3);graph=graph_from_skeleton(thin)
            for n in graph['nodes']:n['point']=[v-16 for v in n['point']]
            for e in graph['edges']:e['points']=[[x-16,y-16] for x,y in e['points']]
            strokes=candidate_strokes(graph);paths=[s['points'] for s in strokes]
            export_roundtrip(paths,0xE000)
            images[mode]=render_ink(paths,widths[key]);relations=component_relations(source<128,mask[16:-16,16:-16])
            labels,_=ndi.label(source<128,np.ones((3,3)));areas=np.bincount(labels.ravel())
            relations['substantial_merges']=int(sum(sum(areas[i]>=12 for i in g)>=2 for g in relations['merged_reference_groups']))
            measurements=local_widths(source,graph) if mode=='guarded' else []
            values=[r['width'] for r in measurements if r['width'] is not None]
            modes[mode]=dict(**compare_ink(source,images[mode]),**relations,paths=len(paths),
                components=int(ndi.label(mask,np.ones((3,3)))[1]),
                width_valid=len(values),width_unreliable=len(measurements)-len(values),
                width_quantiles=np.percentile(values,[10,50,90]).tolist() if values else None)
            if mode=='guarded':save_json(out/f'cases/{key}.json',dict(paths=paths,local_widths=measurements,guard=info,status='candidate only'))
        row=dict(id=key,**modes,guard=info);rows.append(row)
        panel=Image.new('RGB',(1100,250),'white');d=ImageDraw.Draw(panel)
        for i,(label,img) in enumerate(zip(('Source','Baseline redraw','Guarded redraw','Baseline difference','Guarded difference'),
            (Image.fromarray(source),Image.fromarray(images['baseline']),Image.fromarray(images['guarded']),difference(source,images['baseline']),difference(source,images['guarded'])))):
            d.text((220*i+5,5),label,fill='black');panel.paste(img,(220*i+5,30))
        panel.save(out/f'panels/{key}.png')
    summary={mode:dict(mean_iou=float(np.mean([r[mode]['overlap_iou'] for r in rows])),
        cases_with_substantial_merges=sum(r[mode]['substantial_merges']>0 for r in rows),
        total_components=sum(r[mode]['components'] for r in rows),
        total_paths=sum(r[mode]['paths'] for r in rows)) for mode in ('baseline','guarded')}
    summary.update(improved=sum(r['guarded']['overlap_iou']>r['baseline']['overlap_iou']+1e-12 for r in rows),
        worsened=sum(r['guarded']['overlap_iou']<r['baseline']['overlap_iou']-1e-12 for r in rows),
        cases_more_components=sum(r['guarded']['components']>r['baseline']['components'] for r in rows),
        valid_width_points=sum(r['guarded']['width_valid'] for r in rows),
        unreliable_width_points=sum(r['guarded']['width_unreliable'] for r in rows))
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    for r in sorted(rows,key=lambda r:r['guarded']['overlap_iou']-r['baseline']['overlap_iou']):
        cards.append(f'<details><summary>{r["id"]}: {r["baseline"]["overlap_iou"]:.1%} to {r["guarded"]["overlap_iou"]:.1%}</summary><img src="panels/{r["id"]}.png"></details>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Ink support regression</title><style>body{max-width:1150px;margin:30px auto;font:18px/1.7 sans-serif}img{max-width:100%}</style><h1>Bright-bridge guard: paired regression</h1><p>Largest IoU regressions first. Same constant redraw width in both modes. Local widths are source diagnostics, not exported machine instructions. Red: missing; blue: extra.</p><p><a href="FINDINGS.md">Findings and limits</a> | <a href="results.json">All metrics</a></p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
