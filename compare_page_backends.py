"""Visual comparison only: candidate counts are not detection accuracy."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def run(qwen_dir,rapid_dir):
    out=Path(qwen_dir);q=json.loads((out/'results.json').read_text(encoding='utf-8'))
    baseline=json.loads((Path(rapid_dir)/'results.json').read_text(encoding='utf-8'))
    by_hash={r['sha256']:r for r in baseline['images']}
    sheet=Image.new('RGB',(1200,850*len(q['images'])),'white');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20);summary=[]
    for row_index,row in enumerate(q['images']):
        old=by_hash[row['sha256']];image=Image.open(out/row['image']).convert('RGB')
        for x,data,label in [(0,old,'RapidOCR'),(600,row,'Qwen NF4')]:
            photo=image.copy();p=ImageDraw.Draw(photo)
            for i,c in enumerate(data['characters'],1):
                box=c['box'];p.line([tuple(v) for v in box]+[tuple(box[0])],fill='red',width=2)
            photo.thumbnail((580,780));sheet.paste(photo,(x,row_index*850+50))
            draw.text((x+5,row_index*850+5),f'{label}: {len(data["characters"])} candidates / {data["status"]}',font=font,fill='black')
        summary.append(dict(source=row['source'],qwen_status=row['status'],qwen_candidates=len(row['characters']),rapid_candidates=len(old['characters']),qwen_seconds=row['seconds'],qwen_metrics=row.get('metrics'),rejected=len(row.get('rejected',[])),error=row.get('error')))
    sheet.save(out/'backend_comparison.png')
    (out/'comparison_summary.json').write_text(json.dumps(dict(quality_verified=False,independent_holdout=False,rows=summary),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('qwen_dir');p.add_argument('rapid_dir');a=p.parse_args();run(a.qwen_dir,a.rapid_dir)
