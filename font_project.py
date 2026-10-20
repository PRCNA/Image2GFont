"""A font collection of reviewed page projects; sources remain local and immutable."""
import argparse
import copy
import json
from pathlib import Path
from page_import import PageProject
from gfont_core import GFont, GFontMetadata, GFontV5Reader, GFontV5Writer


class FontProject:
    @classmethod
    def create(cls, destination, name):
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Font name is required')
        obj = cls()
        obj.root = Path(destination)
        obj.root.mkdir(parents=True, exist_ok=False)
        obj.data = dict(format='Image2GFontCollection', schema_version=1, name=name, pages=[])
        obj.save()
        return obj

    @classmethod
    def load(cls, path):
        obj = cls()
        obj.root = Path(path).parent
        obj.data = json.loads(Path(path).read_text(encoding='utf-8'))
        if obj.data.get('format') != 'Image2GFontCollection' or obj.data.get('schema_version') != 1:
            raise ValueError('Unsupported font project')
        obj.pages()
        return obj

    def pages(self):
        result = []
        for entry in self.data['pages']:
            path = (self.root / entry).resolve()
            if self.root.resolve() not in path.parents:
                raise ValueError('Page must be inside font project')
            result.append(PageProject.load(path))
        return result

    def save(self):
        temp = self.root / 'font_project.json.tmp'
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.root / 'font_project.json')

    def add_page(self, path):
        source = PageProject.load(path)
        source.validate()
        existing = self.pages()
        known = {r['character'] for p in existing for r in p.data['regions']}
        duplicates = known.intersection(r['character'] for r in source.data['regions'])
        if duplicates:
            raise ValueError('Duplicate character bindings: ' + ', '.join(sorted(duplicates)))
        if any(p.data['source_sha256'] == source.data['source_sha256'] for p in existing):
            raise ValueError('This source image already exists in the project')
        target = self.root / ('page_%03d' % (len(existing) + 1))
        page = PageProject.create(source.root / source.data['source'], target)
        page.data['regions'] = copy.deepcopy(source.data['regions'])
        page.save()
        self.data['pages'].append(str((target / 'page.json').relative_to(self.root)))
        self.save()

    def generate(self, destination, vision_mode=None):
        if vision_mode is None:vision_mode=self.data.get('vision_mode')
        from vision_core.segmentation import MODES
        if vision_mode is not None and vision_mode not in MODES:raise ValueError('Unknown vision mode')
        pages = self.pages()
        if not pages:
            raise ValueError('Add at least one reviewed page project')
        seen = set()
        for page in pages:
            page.validate()
            for region in page.data['regions']:
                char = region['character']
                if char in seen:
                    raise ValueError('Duplicate character binding: ' + char)
                seen.add(char)
        out = Path(destination)
        out.mkdir(parents=True, exist_ok=False)
        glyphs, rows = {}, []
        for index, page in enumerate(pages, 1):
            result = page.generate(out / ('page_%03d' % index),vision_mode=vision_mode)
            font = GFontV5Reader.read(result)
            glyphs.update(font.glyphs)
            rows.append(dict(page=index, source_sha256=page.data['source_sha256'], regions=page.data['regions']))
        merged = GFont(GFontMetadata(name=self.data['name'], glyph_count=len(glyphs)), glyphs, list(glyphs))
        encoded = GFontV5Writer.dumps(merged)
        decoded = GFontV5Reader.loads(encoded)
        if set(decoded.glyphs) != set(glyphs):
            raise ValueError('Export verification failed')
        (out / 'report.json').write_text(json.dumps(dict(status='candidate', driver_verified=False, pages=rows), ensure_ascii=False, indent=2), encoding='utf-8')
        (out / 'candidate.gfont').write_bytes(encoded)
        return out / 'candidate.gfont'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create'); create.add_argument('directory'); create.add_argument('--name', required=True)
    add = commands.add_parser('add'); add.add_argument('project'); add.add_argument('page')
    export = commands.add_parser('export'); export.add_argument('project'); export.add_argument('directory'); export.add_argument('--vision-mode',choices=['auto','dark','light','cyan','dark_red_grid'])
    args = parser.parse_args()
    if args.command == 'create': FontProject.create(args.directory, args.name)
    elif args.command == 'add': FontProject.load(args.project).add_page(args.page)
    else: print(FontProject.load(args.project).generate(args.directory,vision_mode=args.vision_mode))


if __name__ == '__main__': main()
