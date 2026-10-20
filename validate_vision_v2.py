"""Compare vision v2 to the frozen real-photo baseline; no OCR labels changed."""
import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from font_project import FontProject
from gfont_core import GFontV5Reader

def run(project_path,destination):
    project=FontProject.load(project_path);out=Path(destination)
    fontpath=project.generate(out,vision_mode='auto');font=GFontV5Reader.read(fontpath)
    rows=[]
    for pi,p in enumerate(project.pages(),1):
        report=json.loads((out/f'page_{pi:03d}/report.json').read_text(encoding='utf-8'))
        for ri,r in enumerate(p.data['regions'],1):rows.append((pi,ri,r,report['rows'][ri-1]))
    sheet=Image.new('RGB',(1000,250*len(rows)),'white');draw=ImageDraw.Draw(sheet);label=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    for j,(pi,ri,r,detail) in enumerate(rows):
        y=j*250;im=Image.open(out/f'page_{pi:03d}/crop_{ri}.png');mask=Image.open(out/f'page_{pi:03d}/mask_{ri}.png')
        draw.text((5,y),r['character']+' | original / mask / exported trajectory | '+detail['vision']['resolved_mode'],font=label,fill='black')
        for x,photo in [(0,im),(330,mask)]:
            photo=photo.copy();photo.thumbnail((300,210));sheet.paste(photo,(x,y+30))
        scale=detail['vision']['transform']['scale'];ox,oy=detail['vision']['transform']['offset'];display=min(300/im.width,210/im.height)
        for stroke in font.glyphs[ord(r['character'])].strokes:
            pts=[(660+(p.x-ox)/scale*display,y+30+(p.y-oy)/scale*display) for p in stroke]
            if len(pts)>1:draw.line(pts,fill='black',width=1)
    sheet.save(out/'comparison.png')
    summary=dict(glyphs=len(font.glyphs),driver_verified=False,quality_verified=False,rows=[dict(character=r['character'],**d['vision']) for _,_,r,d in rows])
    (out/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('output');a=p.parse_args();print(run(a.project,a.output))
