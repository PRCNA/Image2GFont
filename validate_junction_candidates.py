"""Known-sample junction regression. No ground-truth order optimization."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes
from image_pipeline.junction_candidates import junction_candidates
from image_pipeline.appearance_metrics import render_ink,compare_ink,travel
from validate_appearance import export_roundtrip
from validate_public_handwriting import RECIPE,save_json,sha


def segments(paths):
    return Counter(tuple(sorted((tuple(a),tuple(b)))) for p in paths for a,b in zip(p,p[1:]))


def main():
    root=Path(__file__).parent;out=root/'artifacts/junction_candidates_v1'
    out.mkdir(exist_ok=False)
    for name in ('cases','panels'):(out/name).mkdir()
    base=root/'artifacts/appearance_v2';inputs=sorted((base/'inputs').glob('*.png'))
    photos=root/'artifacts/photo_0923_hanzi/candidates.json'
    hashes={str(p.relative_to(root)):sha(p.read_bytes()) for p in inputs+[photos]}
    save_json(out/'plan.json',dict(inputs=hashes,recipe=RECIPE,min_angle=120,unpaired_cost=40,
        margin_threshold=15,tangent_disagreement_limit=20,max_degree=6,
        scope='96 known synthetic conditions plus four existing photo graphs. Not held-out accuracy.',
        implementation_sha256=sha((root/'image_pipeline/junction_candidates.py').read_bytes())))
    cases=[]
    for p in inputs:
        source=np.asarray(Image.open(p).convert('L'));mask=preprocess(np.pad(source,16,constant_values=255),**RECIPE)
        mask[:16]=False;mask[-16:]=False;mask[:,:16]=False;mask[:,-16:]=False
        thin,_=prune_spurs(skeletonize(mask),3);graph=graph_from_skeleton(thin)
        for node in graph['nodes']:node['point']=[v-16 for v in node['point']]
        for edge in graph['edges']:edge['points']=[[x-16,y-16] for x,y in edge['points']]
        cases.append((p.stem,graph,int(p.stem.rsplit('w',1)[1]),source,'synthetic'))
    for record in json.loads(photos.read_text(encoding='utf-8')):
        # Photo width is only a diagnostic tangent scale, not a calibrated nib.
        graph=record['graph'];size=int(max(max(p) for e in graph['edges'] for p in e['points']))+20
        cases.append(('photo_'+record['slot'],graph,3,np.full((size,size),255,np.uint8),'photo graph'))
    rows=[];cards=[]
    for n,(key,graph,width,source,kind) in enumerate(cases):
        old=candidate_strokes(graph);new,reports=junction_candidates(graph,width)
        a=[s['points'] for s in old];b=[s['points'] for s in new]
        assert segments(a)==segments(b)
        assert sorted(i for s in new for i in s['edge_ids'])==list(range(len(graph['edges'])))
        export_roundtrip(b,0x6C38)
        scores=None
        if kind=='synthetic':
            old_ink=render_ink(a,width);new_ink=render_ink(b,width)
            assert np.array_equal(old_ink,new_ink)
            scores=compare_ink(source,new_ink)
        row=dict(id=key,kind=kind,junctions=len(reports),accepted=sum(r['status']=='accepted' for r in reports),
            review=sum(r['status']=='review' for r in reports),changed=sum(r['changed_from_legacy'] for r in reports),
            before_travel=travel(a),after_travel=travel(b),appearance=scores,
            segment_multiset_preserved=True,gfont_roundtrip=True)
        rows.append(row)
        save_json(out/f'cases/{key}.json',dict(summary=row,graph=graph,junctions=reports,baseline=old,candidate=new))
        panel=Image.new('RGB',(700,360),'white');draw=ImageDraw.Draw(panel)
        palette=['#1665bd','#a42f2f','#278242','#9747aa','#b27b00']
        size=source.shape[0];scale=300/size
        for col,strokes in enumerate((old,new)):
            draw.text((col*350+10,5),'Baseline' if col==0 else 'Candidate / orange = review',fill='black')
            for i,s in enumerate(strokes):
                xy=[(col*350+10+x*scale,30+y*scale) for x,y in s['points']]
                if len(xy)>1:draw.line(xy,fill=palette[i%len(palette)],width=2)
                else:draw.ellipse((xy[0][0]-1,xy[0][1]-1,xy[0][0]+1,xy[0][1]+1),fill=palette[i%len(palette)])
            if col:
                nodes={v['id']:v for v in graph['nodes']}
                for r in reports:
                    x,y=nodes[r['node']]['point'];x=360+x*scale;y=30+y*scale
                    color='#d87700' if r['status']=='review' else '#008455'
                    draw.ellipse((x-5,y-5,x+5,y+5),outline=color,width=2);draw.text((x+5,y),str(r['node']),fill=color)
        panel.save(out/f'panels/{key}.png')
        details=''.join(f'<li>Node {r["node"]}: {r["status"]}; {r["reason"]}; alternatives {r["candidate_count"]}; margin {r["score_margin"]}</li>' for r in reports)
        cards.append(f'<details><summary>{key}: changed {row["changed"]}, review {row["review"]}</summary><img src="panels/{key}.png"><ul>{details}</ul><a href="cases/{key}.json">All pairings, scores and paths</a></details>')
        if (n+1)%16==0:print(f'Checked {n+1}/{len(cases)}',flush=True)
    summary={kind:{k:sum(r[k] for r in rows if r['kind']==kind) for k in ('junctions','accepted','review','changed')} for kind in ('synthetic','photo graph')}
    save_json(out/'results.json',dict(summary=summary,rows=rows))
    assert all(sha((root/p).read_bytes())==h for p,h in hashes.items())
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Junction review</title><style>body{max-width:1000px;margin:30px auto;font:17px/1.6 sans-serif}img{max-width:100%}details{padding:10px;border-bottom:1px solid #ddd}</style><h1>Junction candidate review</h1><p>Green: heuristic accepted. Orange: review required; legacy pairing retained. Colors distinguish paths, not true stroke order. Every graph segment is preserved exactly. Appearance cannot select among geometrically identical traversals.</p><p>Known regression only; photo graphs use an uncalibrated 3px tangent scale. No claim of connection accuracy or machine improvement.</p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
