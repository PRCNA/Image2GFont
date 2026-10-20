from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from gfont_core import GFont, Glyph, Point
from coordinate_editor.model import EditorSession, Transform


class StrokeSession(EditorSession):
    def __init__(self,path):
        super().__init__(path)
        self.paths={cp:tuple(tuple(s) for s in g.strokes) for cp,g in self.font.glyphs.items()}
        self.confirmed={cp:False for cp in self.paths}
        self.changes=[];self.position=0;self.saved_signature=self.signature()

    def signature(self):
        return hashlib.sha256(json.dumps(self.payload(),sort_keys=True).encode()).hexdigest()

    @property
    def dirty(self):return self.signature()!=self.saved_signature

    def glyph(self,cp):return Glyph(cp,[list(s) for s in self.paths[cp]])

    def change(self,cp,paths,confirmed=False):
        value=tuple(tuple(s) for s in paths)
        Glyph(cp,[list(s) for s in value]).validate()
        before=(self.paths[cp],self.confirmed[cp]);after=(value,confirmed)
        if before!=after:
            self.changes=self.changes[:self.position]+[(cp,before,after)]
            self.position+=1;self.paths[cp],self.confirmed[cp]=after

    def undo(self):
        if self.position:
            self.position-=1;cp,before,after=self.changes[self.position]
            self.paths[cp],self.confirmed[cp]=before
            return cp

    def redo(self):
        if self.position<len(self.changes):
            cp,before,after=self.changes[self.position];self.position+=1
            self.paths[cp],self.confirmed[cp]=after
            return cp

    def delete(self,cp,indices):
        selected=set(indices)
        if not selected or not selected<=set(range(len(self.paths[cp]))):raise ValueError('请选择有效路径')
        self.change(cp,[s for i,s in enumerate(self.paths[cp]) if i not in selected])

    def reverse(self,cp,index):
        paths=list(self.paths[cp]);paths[index]=tuple(reversed(paths[index]));self.change(cp,paths)

    def move(self,cp,index,delta):
        target=index+delta
        if not 0<=target<len(self.paths[cp]):return index
        paths=list(self.paths[cp]);paths[index],paths[target]=paths[target],paths[index];self.change(cp,paths)
        return target

    def split(self,cp,index,point_index):
        paths=list(self.paths[cp]);s=paths[index]
        if not 0<point_index<len(s)-1:raise ValueError('请点选路径内部节点；端点不能拆分')
        paths[index:index+1]=[s[:point_index+1],s[point_index:]];self.change(cp,paths)

    def move_point(self,cp,index,point_index,point):
        paths=[list(s) for s in self.paths[cp]];stroke=paths[index]
        closed=len(stroke)>2 and stroke[0]==stroke[-1]
        stroke[point_index]=point
        if closed and point_index in (0,len(stroke)-1):stroke[0]=stroke[-1]=point
        self.change(cp,paths)

    def insert_point(self,cp,index,segment_index,point):
        paths=[list(s) for s in self.paths[cp]];stroke=paths[index]
        if not 0<=segment_index<len(stroke)-1:raise ValueError('无效线段')
        stroke.insert(segment_index+1,point);self.change(cp,paths)
        return segment_index+1

    def delete_point(self,cp,index,point_index):
        paths=[list(s) for s in self.paths[cp]];stroke=paths[index]
        if not 0<=point_index<len(stroke):raise ValueError('无效节点')
        if len(stroke)>2 and stroke[0]==stroke[-1]:
            if len(stroke)<=4:raise ValueError('闭环至少保留三个节点；如需删除整笔，请使用删除路径')
            logical=stroke[:-1];del logical[point_index%len(logical)];paths[index]=logical+[logical[0]]
        else:
            if len(stroke)<=2:raise ValueError('路径至少保留两个节点；如需删除整笔，请使用删除路径')
            del stroke[point_index]
        self.change(cp,paths)

    def add_path(self,cp,points):
        clean=[]
        for p in points:
            if not clean or p!=clean[-1]:clean.append(p)
        if len(clean)<2:raise ValueError('补画至少需要两个不同的连续节点')
        paths=list(self.paths[cp]);paths.append(clean);self.change(cp,paths)
        return len(paths)-1

    def join(self,cp,first,second,reverse_first=False,reverse_second=False):
        if first==second:raise ValueError('需要两条不同路径')
        paths=list(self.paths[cp]);a=paths[first][::-1] if reverse_first else paths[first]
        b=paths[second][::-1] if reverse_second else paths[second]
        joined=a+b[1:] if a[-1]==b[0] else a+b
        at=min(first,second)
        paths=[s for i,s in enumerate(paths) if i not in (first,second)]
        paths.insert(at,joined);self.change(cp,paths)
        return at

    def set_confirmed(self,cp,value):self.change(cp,self.paths[cp],bool(value))

    def reset_glyph(self,cp):self.change(cp,self.font.glyphs[cp].strokes)

    def payload(self):
        return {str(cp):dict(strokes=[[[p.x,p.y] for p in s] for s in self.paths[cp]],
                             confirmed=self.confirmed[cp]) for cp in self.paths}

    def save_project(self,path):
        self.check_source()
        data=dict(format='Image2GFontStrokeEdits',schema_version=1,source=str(self.source),
                  source_sha256=self.source_hash,glyphs=self.payload())
        with Path(path).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
        self.saved_signature=self.signature()

    def load_project(self,path):
        self.check_source();data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('format')!='Image2GFontStrokeEdits' or data.get('schema_version')!=1:
            raise ValueError('不是支持的笔画修正记录')
        if data.get('source_sha256')!=self.source_hash:raise ValueError('修正记录不属于当前原始字体，请先打开对应字体')
        if set(data['glyphs'])!={str(cp) for cp in self.paths}:raise ValueError('字形集合不一致')
        values={}
        for key,item in data['glyphs'].items():
            cp=int(key);paths=[[Point(*p) for p in s] for s in item['strokes']]
            Glyph(cp,paths).validate()
            if type(item['confirmed']) is not bool:raise ValueError('确认状态无效')
            values[cp]=(tuple(tuple(s) for s in paths),item['confirmed'])
        self.paths={cp:v[0] for cp,v in values.items()};self.confirmed={cp:v[1] for cp,v in values.items()}
        self.changes=[];self.position=0;self.saved_signature=self.signature()

    def export(self,path,name):
        # Reuse the coordinate export verifier with an identity transform.
        # Keep original font immutable even if writing fails.
        original=self.font
        try:
            self.font=GFont(replace(original.metadata,glyph_count=len(self.paths)),
                            {cp:self.glyph(cp) for cp in self.paths},list(original.inline_codepoints))
            return super().export(path,name)
        finally:self.font=original
