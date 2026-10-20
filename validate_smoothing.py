"""Compare serialized font geometry against the frozen unsmoothed export."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from gfont_core import GFontV5Reader


def run():
    old=Path('artifacts/vision_v2_real_v3');new=Path('artifacts/vision_smoothing_v1')
    before=GFontV5Reader.read(old/'candidate.gfont');after=GFontV5Reader.read(new/'candidate.gfont')
    sheet=Image.new('RGB',(1200,400*len(after.glyphs)),'white');d=ImageDraw.Draw(sheet)
    label=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20);rows=[];index=0
    for report_path in sorted(new.glob('page_*/report.json')):
        report=json.loads(report_path.read_text(encoding='utf-8'))
        for row in report['rows']:
            slot=row['slot'];cp=ord(row['transforms'][0]['key'])
            im=Image.open(report_path.parent/f'crop_{slot}.png').convert('RGB')
            scale=row['vision']['transform']['scale'];ox,oy=row['vision']['transform']['offset']
            ds=min(380/im.width,350/im.height);y=index*400
            d.text((5,y),chr(cp)+' | source / previous / smoothed',font=label,fill='black')
            im=im.resize((round(im.width*ds),round(im.height*ds)));sheet.paste(im,(0,y+35))
            a=before.glyphs[cp];b=after.glyphs[cp]
            assert len(a.strokes)==len(b.strokes)
            for offset,glyph in [(400,a),(800,b)]:
                for stroke in glyph.strokes:
                    xy=[(offset+(p.x-ox)/scale*ds,y+35+(p.y-oy)/scale*ds) for p in stroke]
                    if len(xy)>1:d.line(xy,fill='black',width=2)
            endpoints=max(max(abs(sa[k].x-sb[k].x),abs(sa[k].y-sb[k].y)) for sa,sb in zip(a.strokes,b.strokes) for k in (0,-1))
            assert endpoints<1e-4
            rows.append(dict(character=chr(cp),paths=len(a.strokes),before_points=sum(map(len,a.strokes)),after_points=sum(map(len,b.strokes)),endpoint_max_error=endpoints))
            index+=1
    sheet.save(new/'before_after.png')
    (new/'smoothing_checks.json').write_text(json.dumps(dict(rows=rows,driver_verified=False,quality_verified=False),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':run()
