"""Load crop references for single-page and collection exports without Tk."""
import json
from pathlib import Path
from PIL import Image


def load_report_reference(folder,codepoint):
    folder=Path(folder);report=folder/'report.json'
    if not report.exists():return None
    data=json.loads(report.read_text(encoding='utf-8'))
    for row in data.get('rows',[]):
        for t in row.get('transforms',[]):
            if ord(t['key'])==codepoint:
                path=(folder/f"crop_{row['slot']}.png").resolve()
                if path.parent!=folder.resolve():raise ValueError('Invalid reference path')
                with Image.open(path) as im:image=im.convert('RGB')
                pad=0 if 'vision' in row else data['padding']
                sx,sy=t['scale_x'],t['scale_y'];ox,oy=t['offset']
                return image,sx,sy,ox+pad*sx,oy+pad*sy
    for page in data.get('pages',[]):
        index=page['page']
        if type(index) is not int or index<1:raise ValueError('Invalid page reference')
        child=folder/f'page_{index:03d}'
        if not child.exists():continue
        # Collections contain page reports, not arbitrary recursively nested projects.
        child_data=json.loads((child/'report.json').read_text(encoding='utf-8'))
        if 'pages' in child_data:raise ValueError('Nested collection reference unsupported')
        result=load_report_reference(child,codepoint)
        if result is not None:return result
    return None
