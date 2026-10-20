"""Frozen external image evaluation, with no per-image parameter search."""
import json
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image,ImageDraw
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes
from image_pipeline.junction_candidates import junction_candidates
from image_pipeline.appearance_metrics import render_ink,compare_ink,travel
from validate_public_handwriting import RECIPE,save_json,sha,component_relations
from validate_junction_candidates import segments
from validate_appearance import difference,export_roundtrip


def main():
    project=Path(__file__).parent;out=project/'artifacts/new_web_handwriting_v1'
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    for folder in ('normalized','panels','cases'):(out/folder).mkdir(exist_ok=False)
    prior=set()
    for p in (project/'artifacts').glob('*/originals/*'):
        if out not in p.parents and p.is_file() and p.suffix.lower() in ('.png','.jpg','.bmp'):prior.add(sha(p.read_bytes()))
    save_json(out/'plan.json',dict(recipe=RECIPE,normalization='Grayscale; longest side 160px; centered in white 200px canvas; no crop, inversion or denoising beyond frozen recipe',
        width='2 * median foreground distance transform along unpruned reference-mask skeleton; estimate only',
        reference_threshold=128,prune_length=3,hashes={n:sha((project/n).read_bytes()) for n in ('image_pipeline/core.py','image_pipeline/junction_candidates.py','validate_new_web_handwriting.py')},
        limitations=['No true stroke or pen-width annotations','Directory labels unverified','IoU measures approximate constant-width reconstruction, not recognition accuracy','New images at first evaluation, now regression samples']))
    rows=[];seen=set()
    for i,e in enumerate(manifest['samples']):
        key=e['id'];data=(out/e['file']).read_bytes();assert sha(data)==e['sha256']
        row=dict(id=key,duplicate_prior=e['sha256'] in prior,duplicate_in_cohort=e['sha256'] in seen);seen.add(e['sha256'])
        try:
            original=Image.open(out/e['file']).convert('L');w,h=original.size
            factor=160/max(w,h);resized=original.resize((max(1,round(w*factor)),max(1,round(h*factor))),Image.Resampling.LANCZOS)
            canvas=Image.new('L',(200,200),255);canvas.paste(resized,((200-resized.width)//2,(200-resized.height)//2))
            canvas.save(out/f'normalized/{key}.png');source=np.asarray(canvas);ref=source<128
            reference_skeleton=skeletonize(ref);radii=ndi.distance_transform_edt(ref)[reference_skeleton]
            if not len(radii):raise ValueError('No foreground under frozen threshold')
            width=float(2*np.median(radii))
            mask=preprocess(np.pad(source,16,constant_values=255),**RECIPE)
            mask[:16]=False;mask[-16:]=False;mask[:,:16]=False;mask[:,-16:]=False
            thin,removed=prune_spurs(skeletonize(mask),3);graph=graph_from_skeleton(thin)
            for n in graph['nodes']:n['point']=[v-16 for v in n['point']]
            for edge in graph['edges']:edge['points']=[[x-16,y-16] for x,y in edge['points']]
            baseline=candidate_strokes(graph);candidate,reports=junction_candidates(graph,width)
            a=[s['points'] for s in baseline];b=[s['points'] for s in candidate]
            assert segments(a)==segments(b)
            before=render_ink(a,width);after=render_ink(b,width);assert np.array_equal(before,after)
            if not b:raise ValueError('No extracted paths')
            export_roundtrip(b,0xE000) # Serialization probe only; no guessed character binding.
            relation=component_relations(ref,mask[16:-16,16:-16])
            labels,_=ndi.label(ref,np.ones((3,3)));areas=np.bincount(labels.ravel())
            relation['merged_groups_with_two_regions_at_least_12px']=[g for g in relation['merged_reference_groups'] if sum(areas[j]>=12 for j in g)>=2]
            relation['removed_regions_at_least_12px']=[j for j in relation['removed_reference_components'] if areas[j]>=12]
            row.update(status='ok',original_size=[w,h],estimated_width=width,**compare_ink(source,after),
                **relation,pruned_pixels=removed,junctions=len(reports),accepted=sum(r['status']=='accepted' for r in reports),
                review=sum(r['status']=='review' for r in reports),changed=sum(r['changed_from_legacy'] for r in reports),
                baseline_paths=len(a),candidate_paths=len(b),before_travel=travel(a),after_travel=travel(b),
                ink_identical=True,gfont_roundtrip=True)
            save_json(out/f'cases/{key}.json',dict(summary=row,junctions=reports,graph=graph,baseline=baseline,candidate=candidate))
            overlay=canvas.convert('RGB');draw=ImageDraw.Draw(overlay)
            for s in b:
                if len(s)>1:draw.line([tuple(p) for p in s],fill='#006acb',width=1)
            nodes={n['id']:n for n in graph['nodes']}
            for r in reports:
                x,y=nodes[r['node']]['point'];color='#de7800' if r['status']=='review' else '#008040'
                draw.ellipse((x-3,y-3,x+3,y+3),outline=color,width=1)
            panel=Image.new('RGB',(1100,255),'white');d=ImageDraw.Draw(panel)
            images=[canvas,Image.fromarray(np.where(mask[16:-16,16:-16],0,255).astype('uint8')),overlay,Image.fromarray(after),difference(source,after)]
            for col,(label,img) in enumerate(zip(('Input','Processed mask','Paths + junctions','Estimated-width redraw','Red missing / blue extra'),images)):
                d.text((col*220+5,5),label,fill='black');panel.paste(img,(col*220+5,30))
            panel.save(out/f'panels/{key}.png')
        except Exception as error:
            row.update(status='failed',error=repr(error))
        rows.append(row)
        assert sha((out/e['file']).read_bytes())==e['sha256']
        if (i+1)%10==0:print(f'Checked {i+1}/{len(manifest["samples"])}',flush=True)
    ok=[r for r in rows if r['status']=='ok']
    summary=dict(total=len(rows),completed=len(ok),failed=len(rows)-len(ok),duplicate_prior=sum(r['duplicate_prior'] for r in rows),duplicate_in_cohort=sum(r['duplicate_in_cohort'] for r in rows),
        **{k:sum(r[k] for r in ok) for k in ('junctions','accepted','review','changed')},
        means={k:float(np.mean([r[k] for r in ok])) for k in ('overlap_iou','missing_fraction','extra_fraction')},
        cases_with_merges=sum(bool(r['merged_reference_groups']) for r in ok),cases_with_removed_components=sum(bool(r['removed_reference_components']) for r in ok))
    summary['cases_with_substantial_region_merges']=sum(bool(r['merged_groups_with_two_regions_at_least_12px']) for r in ok)
    summary['cases_with_substantial_region_removal']=sum(bool(r['removed_regions_at_least_12px']) for r in ok)
    summary['iou_range']=[min(r['overlap_iou'] for r in ok),max(r['overlap_iou'] for r in ok)] if ok else []
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    cards=''.join(f'<details><summary>{r["id"]}: IoU {r["overlap_iou"]:.1%}; review {r["review"]}; changed {r["changed"]}</summary><img src="panels/{r["id"]}.png"><p><a href="cases/{r["id"]}.json">All diagnostics and candidate pairings</a></p></details>' for r in sorted(ok,key=lambda r:r['overlap_iou']))
    failures=''.join(f'<p>{r["id"]}: failed (see results.json)</p>' for r in rows if r['status']!='ok')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>New handwriting evaluation</title><style>body{max-width:1150px;margin:30px auto;font:17px/1.7 sans-serif}img{max-width:100%}details{padding:10px;border-bottom:1px solid #ddd}</style><h1>New web handwriting: all results</h1><p>Frozen parameters; lowest overlap first. Orange junctions require review. Stroke width is estimated, so overlap is a diagnostic, not accuracy. Pairing preserves ink exactly. Source labels are unverified; no usable font is exported.</p><p><a href="FINDINGS.md">Findings</a> | <a href="results.json">Metrics including failures</a> | <a href="manifest.json">Sources</a></p>'+failures+cards,encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
