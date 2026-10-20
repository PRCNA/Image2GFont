from dataclasses import dataclass, asdict, replace
import hashlib
import json
import math
from pathlib import Path
import struct

from gfont_core import GFont, Glyph, Point, GFontV5Reader, GFontV5Writer


@dataclass(frozen=True)
class Transform:
    dx: float = 0
    dy: float = 0
    scale: float = 1
    angle: float = 0
    pivot_x: float = 0
    pivot_y: float = 0
    flip_x: bool = False
    flip_y: bool = False

    def validate(self):
        for key in ('dx','dy','scale','angle','pivot_x','pivot_y'):
            value = getattr(self,key)
            if type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError('变换参数必须是有限数字')
        if not 0 < self.scale <= 100:
            raise ValueError('缩放比例必须大于0且不超过100')
        if type(self.flip_x) is not bool or type(self.flip_y) is not bool:
            raise ValueError('翻转参数必须为布尔值')

    def apply(self, point):
        self.validate()
        x=(point.x-self.pivot_x)*self.scale*(-1 if self.flip_x else 1)
        y=(point.y-self.pivot_y)*self.scale*(-1 if self.flip_y else 1)
        a=math.radians(self.angle);c=math.cos(a);s=math.sin(a)
        return Point(c*x-s*y+self.pivot_x+self.dx,s*x+c*y+self.pivot_y+self.dy)


def bounds(glyph):
    points=[p for s in glyph.strokes for p in s]
    if not points:return None
    return (min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points))


def transformed(font, transform, name=None):
    transform.validate()
    glyphs={cp:Glyph(cp,[[transform.apply(p) for p in s] for s in g.strokes]) for cp,g in font.glyphs.items()}
    result=GFont(replace(font.metadata,name=name or font.metadata.name),glyphs,list(font.inline_codepoints))
    result.validate()
    return result


class EditorSession:
    def __init__(self,path):
        self.source=Path(path).resolve()
        self.source_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.font=GFontV5Reader.read(self.source)
        self.history=[Transform()];self.index=0

    @property
    def transform(self):return self.history[self.index]

    def commit(self,value):
        value.validate()
        if value!=self.transform:
            self.history=self.history[:self.index+1]+[value];self.index+=1

    def undo(self):self.index=max(0,self.index-1)
    def redo(self):self.index=min(len(self.history)-1,self.index+1)

    def check_source(self):
        if hashlib.sha256(self.source.read_bytes()).hexdigest()!=self.source_hash:
            raise ValueError('原始文件在打开后发生变化，请重新打开')

    def save_profile(self,path):
        self.check_source()
        with Path(path).open('x',encoding='utf-8') as f:
            json.dump(dict(format='Image2GFontCoordinateProfile',schema_version=1,
                           transform=asdict(self.transform),scope='whole_font',
                           source=str(self.source),source_sha256=self.source_hash,
                           driver_verified=False),f,ensure_ascii=False,indent=2)

    def load_profile(self,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('format')!='Image2GFontCoordinateProfile' or data.get('schema_version')!=1:
            raise ValueError('不支持的坐标配置版本')
        self.commit(Transform(**data['transform']))

    def export(self,path,name):
        self.check_source()
        if not name.strip():raise ValueError('请填写导出字体名')
        result=transformed(self.font,self.transform,name.strip())
        data=GFontV5Writer.dumps(result)
        rebuilt=GFontV5Reader.loads(data)
        if rebuilt.metadata!=result.metadata or rebuilt.inline_codepoints!=result.inline_codepoints or set(rebuilt.glyphs)!=set(result.glyphs):
            raise ValueError('导出后字体结构校验失败')
        for cp,g in result.glyphs.items():
            other=rebuilt.glyphs[cp]
            if len(g.strokes)!=len(other.strokes):raise ValueError('笔画数不一致')
            for a,b in zip(g.strokes,other.strokes):
                if len(a)!=len(b):raise ValueError('点数不一致')
                for p,q in zip(a,b):
                    if struct.unpack('>ff',struct.pack('>ff',p.x,p.y))!=(q.x,q.y):
                        raise ValueError('导出坐标校验失败')
        self.check_source()
        with Path(path).open('xb') as f:f.write(data)
        return len(result.glyphs)
