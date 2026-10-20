"""Frozen known-sample regression for optional raster-guided refinement."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from image_pipeline.refine_geometry import refine_geometry, topology
from image_pipeline.appearance_metrics import render_ink, compare_ink, geometry
from validate_appearance import export_roundtrip, difference
from validate_public_handwriting import sha, save_json


def main():
    root=Path(__file__).parent
    base=root/'artifacts/appearance_v2'
    out=root/'artifacts/geometry_refinement_v1'
    out.mkdir(exist_ok=False)
    for folder in ('paths','panels'):(out/folder).mkdir()
    cases=[r for r in json.loads((base/'results.json').read_text(encoding='utf-8'))['rows'] if r['mode']=='baseline']
    inputs=[base/'results.json']+[base/f'inputs/{r["id"]}.png' for r in cases]+[base/f'paths/{r["id"]}_baseline.json' for r in cases]
    hashes={str(p.relative_to(root)):sha(p.read_bytes()) for p in inputs}
    save_json(out/'plan.json',dict(max_step=.75,rounds=2,cases=len(cases),
        scope='Known regression; clean constant-width raster; no stroke truth used by refinement',
        inputs=hashes,implementation_sha256=sha((root/'image_pipeline/refine_geometry.py').read_bytes())))
    rows=[]
    for n,r in enumerate(cases):
        key=r['id'];width=r['width']
        source=np.asarray(Image.open(base/f'inputs/{key}.png').convert('L'))
        old=json.loads((base/f'paths/{key}_baseline.json').read_text())['strokes']
        old_image=render_ink(old,width);before=compare_ink(source,old_image)
        assert abs(before['overlap_iou']-r['overlap_iou'])<1e-12
        candidate,info=refine_geometry(source,old,width)
        candidate=export_roundtrip(candidate,ord(r['character']))
        new_image=render_ink(candidate,width);after=compare_ink(source,new_image)
        fallback=(after['soft_overlap_iou']<before['soft_overlap_iou'] or after['overlap_iou']<before['overlap_iou'] or topology(new_image)!=topology(old_image))
        if fallback:candidate=old;new_image=old_image;after=before
        assert [len(s) for s in old]==[len(s) for s in candidate]
        truth=json.loads((root/f'artifacts/recorded_trajectories_v1/reference/{key.rsplit("_w",1)[0]}.json').read_text(encoding='utf-8'))['strokes']
        rows.append(dict(id=key,width=width,before=before,after=after,
            geometry_before=geometry(truth,old),geometry_after=geometry(truth,candidate),
            diagnostics=info,quantization_fallback=fallback))
        save_json(out/f'paths/{key}.json',dict(strokes=candidate,status='optional candidate',coordinate_space='200px working image'))
        panel=Image.new('RGB',(1100,250),'white');draw=ImageDraw.Draw(panel)
        for i,(label,img) in enumerate(zip(('Source','Baseline','Refined','Baseline difference','Refined difference'),
            (Image.fromarray(source),Image.fromarray(old_image),Image.fromarray(new_image),difference(source,old_image),difference(source,new_image)))):
            draw.text((i*220+5,5),label,fill='black');panel.paste(img,(i*220+5,30))
        panel.save(out/f'panels/{key}.png')
        if (n+1)%16==0:print(f'Checked {n+1}/{len(cases)}',flush=True)
    summary=[]
    for width in (3,7):
        group=[r for r in rows if r['width']==width]
        summary.append(dict(width=width,cases=len(group),
            improved=sum(r['after']['soft_overlap_iou']>r['before']['soft_overlap_iou']+1e-7 for r in group),
            missing_worse=sum(r['after']['missing_fraction']>r['before']['missing_fraction']+1e-12 for r in group),
            extra_worse=sum(r['after']['extra_fraction']>r['before']['extra_fraction']+1e-12 for r in group),
            means={phase:{k:float(np.mean([r[phase][k] for r in group])) for k in ('overlap_iou','soft_overlap_iou','missing_fraction','extra_fraction')} for phase in ('before','after')}))
    assert all(sha((root/p).read_bytes())==h for p,h in hashes.items())
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    ordered=sorted(rows,key=lambda r:r['after']['overlap_iou'])
    cards=''.join(f'<details><summary>{r["id"]}: IoU {r["before"]["overlap_iou"]:.3f} &#8594; {r["after"]["overlap_iou"]:.3f}</summary><img src="panels/{r["id"]}.png"></details>' for r in ordered)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Geometry refinement</title><style>body{max-width:1150px;margin:30px auto;font:18px/1.7 sans-serif}img{max-width:100%}</style><h1>Geometry refinement: all paired cases</h1><p>96 known regression conditions. Lowest final overlap first. Red: missing ink. Blue: extra ink. Fixed-width synthetic ink only; not a photo or machine validation.</p><p><a href="results.json">Full metrics</a> | <a href="FINDINGS.md">Findings and limitations</a></p>'+cards,encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
