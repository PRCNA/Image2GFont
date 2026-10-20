"""One-photo diagnostic, with explicit positional test keys, no OCR binding."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import struct
import numpy as np
import scipy
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version
from image_pipeline.core import preprocess, skeletonize, prune_spurs, graph_from_skeleton, candidate_strokes, simplify
from gfont_core import GFont, GFontMetadata, Glyph, Point, GFontV5Reader, GFontV5Writer

BOXES = [(305,470,500,680),(730,510,880,655),(1060,500,1205,655),(1220,500,1360,655)]
PALETTE = ['#d33c44','#0878b8','#169777','#874bbe','#da7900','#bb3a94']


def save(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    out=args.destination
    out.mkdir(parents=True,exist_ok=False)
    original=args.source.read_bytes()
    (out/'source_original.jpg').write_bytes(original)
    (out/'source_original.jpg').chmod(stat.S_IREAD)
    source=Image.open(io.BytesIO(original)).convert('RGB')
    if source.size != (1820,1024):
        raise ValueError('Crop coordinates are only valid for the supplied 1820x1024 image')
    label_font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    small_font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    annotated=source.copy();ad=ImageDraw.Draw(annotated)
    recipe=dict(blur=0.8,threshold=7,closing=2,min_area=12,background_sigma=18,silhouette_sigma=0.4,max_hole_area=3)
    legacy=dict(blur=4,threshold=8,closing=5,min_area=350,background_sigma=80,silhouette_sigma=1.5,max_hole_area=None)
    panel=Image.new('RGB',(5*270,4*290),'#f4f6fa')
    chart=Image.new('RGB',(4*330,4*360),'white')
    glyphs={};rows=[];data=[]
    for index,box in enumerate(BOXES):
        tag=chr(65+index)
        ad.rectangle(box,outline=PALETTE[index],width=3);ad.text((box[0],box[1]-22),tag,fill=PALETTE[index],font=label_font)
        crop=source.crop(box);crop.save(out/f'crop_{tag}.png')
        gray=np.asarray(crop.convert('L'));pad=16
        padded=np.pad(gray,pad,mode='reflect')
        mask=preprocess(padded,**recipe)
        old=preprocess(padded,**legacy)
        # Padding supplies filter context, never glyph geometry.
        for m in (mask,old):
            m[:pad,:]=False;m[-pad:,:]=False;m[:,:pad]=False;m[:,-pad:]=False
        # These manually selected regions have visible paper margins. Reject
        # components reaching the eight-pixel margin; record this photo-specific QC.
        labels,_=ndi.label(mask,np.ones((3,3)))
        margin=np.ones_like(mask,bool)
        margin[pad+8:-pad-8,pad+8:-pad-8]=False
        reject=set(int(v) for v in np.unique(labels[margin]) if v)
        border_removed=int(np.isin(labels,list(reject)).sum())
        mask[np.isin(labels,list(reject))]=False
        thin=skeletonize(mask);thin,removed=prune_spurs(thin,3)
        graph=graph_from_skeleton(thin);strokes=candidate_strokes(graph)
        assert sorted(e for s in strokes for e in s['edge_ids'])==list(range(len(graph['edges'])))
        paths=[simplify(s['points'],0.65) for s in strokes]
        if not paths:raise ValueError('No paths in '+tag)
        allpts=np.array([p for s in paths for p in s]);low=allpts.min(0);high=allpts.max(0)
        transforms=[]
        for variant in range(4):
            cp=65+variant*4+index
            if variant==0:
                scale=800/max(high-low);offset=np.array([500,500])-(low+high)*scale/2;sy=scale
            else:
                scale=800/240;sy=scale
                offset=np.array([500-(low[0]+high[0])*scale/2,100+(box[1]-460-pad)*scale])
                if variant>=2:offset-=np.array([500,800])
                if variant==3:sy=-scale;offset[1]=-600-offset[1]
            coords=[[(float(x*scale+offset[0]),float(y*sy+offset[1])) for x,y in s] for s in paths]
            glyphs[cp]=Glyph(cp,[[Point(x,y) for x,y in s] for s in coords])
            transforms.append(dict(key=chr(cp),scale_x=float(scale),scale_y=float(sy),offset=offset.tolist()))
            # Fixed 1200-unit view; marks make translations/flips inspectable.
            dr=ImageDraw.Draw(chart);cx=index*330;cy=variant*360
            limits=(-100,1100,-100,1100) if variant<2 else (-600,600,-900,300)
            xmin,xmax,ymin,ymax=limits
            def xy(x,y):return (cx+42+(x-xmin)*.22,cy+50+(y-ymin)*.22)
            title=['INDIVIDUAL FIT','SHARED SCALE','SHARED + BASELINE','BASELINE + Y FLIP'][variant]
            dr.text((cx+10,cy+8),f'{chr(cp)} / {tag} : {title}',fill='#172b40',font=small_font)
            for v in range(-1000,1201,200):
                if xmin<=v<=xmax:
                    dr.line([xy(v,ymin),xy(v,ymax)],fill='#dce2e9',width=1)
                    dr.text((xy(v,ymax)[0]-8,cy+320),str(v),fill='#52606d',font=small_font)
                if ymin<=v<=ymax:
                    dr.line([xy(xmin,v),xy(xmax,v)],fill='#dce2e9',width=1)
            dr.rectangle([xy(xmin,ymin),xy(xmax,ymax)],outline='#75849a',width=1)
            dr.line([xy(0,ymin),xy(0,ymax)],fill='#333333',width=2)
            dr.line([xy(xmin,0),xy(xmax,0)],fill='#333333',width=2)
            dr.text(xy(0,0),'O',fill='#222222',font=small_font)
            dr.text((cx+8,cy+38),f'Y {ymin}',fill='#52606d',font=small_font)
            dr.text((cx+8,cy+296),f'Y {ymax}',fill='#52606d',font=small_font)
            for j,s in enumerate(coords):
                p=[xy(x,y) for x,y in s]
                if len(p)>1:dr.line(p,fill=PALETTE[j%len(PALETTE)],width=2)
                else:dr.ellipse((p[0][0]-1,p[0][1]-1,p[0][0]+1,p[0][1]+1),fill=PALETTE[j%len(PALETTE)])
        overlay=crop.copy();d=ImageDraw.Draw(overlay)
        for j,path in enumerate(paths):
            p=[(x-pad,y-pad) for x,y in path]
            if len(p)>1:d.line(p,fill=PALETTE[j%len(PALETTE)],width=1)
            else:d.ellipse((p[0][0]-1,p[0][1]-1,p[0][0]+1,p[0][1]+1),fill=PALETTE[j%len(PALETTE)])
        overlay.save(out/f'overlay_{tag}.png')
        binary=Image.fromarray(np.uint8(~mask[pad:-pad,pad:-pad])*255).convert('RGB')
        old_image=Image.fromarray(np.uint8(~old[pad:-pad,pad:-pad])*255).convert('RGB')
        skel=Image.fromarray(np.uint8(~thin[pad:-pad,pad:-pad])*255).convert('RGB')
        for col,(im,title) in enumerate([(crop,'SOURCE'),(old_image,'OLD YONG PARAMETERS'),(binary,'SMALL-STROKE PARAMETERS'),(skel,'SKELETON'),(overlay,'PATH OVERLAY')]):
            x=col*270;y=index*290
            panel.paste(im,(x+(270-im.width)//2,y+36))
            ImageDraw.Draw(panel).text((x+6,y+8),f'{tag}: {title}',fill='#17324d',font=small_font)
        binary.save(out/f'binary_{tag}.png');skel.save(out/f'skeleton_{tag}.png')
        row=dict(slot=tag,crop=list(box),candidate_count=len(paths),graph_edges=len(graph['edges']),
                 point_count=sum(map(len,paths)),old_foreground_pixels=int(old.sum()),new_foreground_pixels=int(mask.sum()),
                 new_components=int(ndi.label(mask,np.ones((3,3)))[1]),pruned_pixels=removed,border_removed_pixels=border_removed,
                 bbox_working_pixels=[low.tolist(),high.tolist()],transforms=transforms)
        rows.append(row)
        data.append(dict(slot=tag,character=None,binding_confirmed=False,graph=graph,candidates=paths,
                         status='candidate',confirmed_strokes=None))
    annotated.save(out/'regions.png');panel.save(out/'comparison.png');chart.save(out/'coordinate_comparison.png')
    # Asymmetric F-shaped guide, with a detached dot near its upper right.
    guide=[[(150,850),(150,150),(750,150)],[(150,430),(550,430)],[(850,220),(880,220)]]
    for cp,dx,dy in [(48,0,0),(49,-500,-800)]:
        glyphs[cp]=Glyph(cp,[[Point(x+dx,y+dy) for x,y in s] for s in guide])
    font=GFont(GFontMetadata(name='Image2GFont_CoordTest_0923',font_id='Coord0923',glyph_count=len(glyphs),
                           description='A-D fit; E-H shared; I-L baseline; M-P flip; 0-1 guides'),glyphs,list(glyphs))
    target=out/'coordinate_test.gfont';GFontV5Writer.write(font,target)
    rebuilt=GFontV5Reader.read(target)
    assert font.metadata==rebuilt.metadata and font.inline_codepoints==rebuilt.inline_codepoints
    assert set(font.glyphs)==set(rebuilt.glyphs)
    for cp,g in font.glyphs.items():
        after=rebuilt.glyphs[cp]
        assert len(g.strokes)==len(after.strokes)
        for a,b in zip(g.strokes,after.strokes):
            assert len(a)==len(b)
            assert all((float(np.float32(p.x)),float(np.float32(p.y)))==(q.x,q.y) for p,q in zip(a,b))
    packed=target.read_bytes();start=packed.index(b'PK\x03\x04');end=packed.rindex(b'PK\x05\x06')
    offset=struct.unpack_from('<I',packed,end+16)[0];assert packed[start+offset:start+offset+4]==b'PK\x01\x02'
    save(out/'candidates.json',data)
    report=dict(schema_version=1,source_path=str(args.source),source_sha256=hashlib.sha256(original).hexdigest(),
                source_size=list(source.size),crop_method='assistant-selected rectangles from photo; not automatic detection',
                identity='A-D positional diagnostic slots; Chinese binding not confirmed',recipe=recipe,legacy_recipe=legacy,
                spur_length=3,simplify_tolerance=.65,padding=16,padding_mode='reflect; masked out',
                reject_components_touching_crop_margin=8,rows=rows,
                versions=dict(numpy=np.__version__,scipy=scipy.__version__,pillow=pillow_version),
                font_name=font.metadata.name,glyph_count=len(glyphs),font_sha256=hashlib.sha256(packed).hexdigest(),
                font_roundtrip=True,zip_offsets=True,application_test='NOT RUN',machine_test='NOT RUN')
    assert hashlib.sha256(args.source.read_bytes()).hexdigest()==report['source_sha256']
    save(out/'report.json',report)
    print(json.dumps(rows))


if __name__=='__main__':main()
