"""Spatially match shared test pages and make evidence sheets for visual audit."""
import json,math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from PIL import Image,ImageDraw,ImageFont

OUT=Path('artifacts/ocr_disagreement_audit')
def rect(c):
    p=c['box'];return [min(v[0] for v in p),min(v[1] for v in p),max(v[0] for v in p),max(v[1] for v in p)]
def overlap(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    aa=(a[2]-a[0])*(a[3]-a[1]);bb=(b[2]-b[0])*(b[3]-b[1])
    return inter/max(aa+bb-inter,1e-9),inter/max(min(aa,bb),1e-9)
def main():
    OUT.mkdir(exist_ok=True)
    base=json.loads(Path('artifacts/e2e_0928/ocr/results.json').read_text(encoding='utf-8'))
    qs=json.loads(Path('artifacts/qwen_page_validation_final/results.json').read_text(encoding='utf-8'))['images'][:2]
    qs+=json.loads(Path('artifacts/qwen_dense_validation_v2/results.json').read_text(encoding='utf-8'))['images']
    cases=[];stats=[];matches=[]
    for q in qs:
        r=next(v for v in base['images'] if v['sha256']==q['sha256']);rs=r['characters'];cs=q['characters']
        score=np.zeros((len(rs),len(cs)))
        for i,a in enumerate(rs):
            for j,b in enumerate(cs):
                iou,coverage=overlap(rect(a),rect(b))
                if iou>=.1 and coverage>=.5:score[i,j]=iou
        ri,qi=linear_sum_assignment(-score);pairs=[(int(i),int(j)) for i,j in zip(ri,qi) if score[i,j]>0]
        usedr={i for i,j in pairs};usedq={j for i,j in pairs}
        entries=[(i,j,'disagree' if rs[i]['text']!=cs[j]['text'] else 'agree') for i,j in pairs]+[(i,None,'rapid_only') for i in range(len(rs)) if i not in usedr]+[(None,j,'qwen_only') for j in range(len(cs)) if j not in usedq]
        stats.append(dict(page=r['id'],rapid=len(rs),qwen=len(cs),matched=len(pairs),disagree=sum(k=='disagree' for _,_,k in entries),rapid_only=len(rs)-len(pairs),qwen_only=len(cs)-len(pairs),rejected=q.get('rejected',[])))
        for i,j,kind in entries:
            row=dict(page=r['id'],image=str(Path('artifacts/e2e_0928/ocr')/r['image']),rapid_index=i,qwen_index=j,rapid=rs[i]['text'] if i is not None else None,qwen=cs[j]['text'] if j is not None else None,rapid_box=rect(rs[i]) if i is not None else None,qwen_box=rect(cs[j]) if j is not None else None,kind=kind,iou=float(score[i,j]) if i is not None and j is not None else None)
            matches.append(row)
            if kind!='agree':cases.append(row)
    for n,c in enumerate(cases,1):c['id']=n
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    for offset in range(0,len(cases),12):
        sheet=Image.new('RGB',(1200,1200),'white');d=ImageDraw.Draw(sheet)
        for index,c in enumerate(cases[offset:offset+12]):
            x=index%4*300;y=index//4*400
            boxes=[v for v in (c['rapid_box'],c['qwen_box']) if v]
            b=[min(v[0] for v in boxes),min(v[1] for v in boxes),max(v[2] for v in boxes),max(v[3] for v in boxes)]
            im=Image.open(c['image']).convert('RGB');margin=max(8,min(b[2]-b[0],b[3]-b[1])*.25)
            bounds=(max(0,math.floor(b[0]-margin)),max(0,math.floor(b[1]-margin)),min(im.width,math.ceil(b[2]+margin)),min(im.height,math.ceil(b[3]+margin)))
            crop=im.crop(bounds);scale=min(290/crop.width,310/crop.height);crop=crop.resize((round(crop.width*scale),round(crop.height*scale)));sheet.paste(crop,(x,y+70))
            d.text((x+3,y+3),f"#{c['id']} {c['page']} {c['kind']}",font=font,fill='black')
            d.text((x+3,y+30),f"R: {c['rapid']}   Q: {c['qwen']}",font=font,fill='black')
        sheet.save(OUT/f'sheet_{offset//12+1:02d}.png')
    (OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'matching.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=True));print('cases',len(cases))
if __name__=='__main__':main()
