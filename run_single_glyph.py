"""Reproducible experimental single-glyph pipeline; never confirms candidates."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import stat

import numpy as np
import scipy
from PIL import Image, ImageDraw, ImageFont, ImageOps, __version__ as pillow_version

from gfont_core import GFont, GFontMetadata, Glyph, Point, GFontV5Reader, GFontV5Writer
from image_pipeline.core import preprocess, skeletonize, prune_spurs, graph_from_skeleton, candidate_strokes, simplify


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--codepoint', required=True, help='Explicit user binding, e.g. 6C38')
    parser.add_argument('--threshold', type=float, default=22)
    parser.add_argument('--blur', type=float, default=2)
    parser.add_argument('--closing', type=int, default=5)
    parser.add_argument('--min-area', type=int, default=250)
    parser.add_argument('--spur-length', type=float, default=20)
    args = parser.parse_args()
    cp = int(args.codepoint.removeprefix('U+'), 16)
    Glyph(cp, []).validate()
    dest = args.destination
    if dest.exists():
        raise FileExistsError('Choose a new output directory; existing/manual results are never overwritten')
    dest.mkdir(parents=True)
    original = args.source.read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    preserved = dest / ('source_original' + args.source.suffix)
    preserved.write_bytes(original)
    preserved.chmod(stat.S_IREAD)
    source = ImageOps.exif_transpose(Image.open(preserved)).convert('RGB')
    working = source.copy()
    working.thumbnail((700, 700), Image.Resampling.LANCZOS)
    # Padding retains image-edge ink during morphology; no missing ink is invented.
    padding = 24
    gray = np.asarray(working.convert('L'))
    gray_pad = np.pad(gray, padding, constant_values=float(np.median(gray)))
    recipe = dict(working_size=list(working.size), padding=padding, blur=args.blur,
                  threshold=args.threshold, closing=args.closing, min_area=args.min_area,
                  background_sigma=80, silhouette_sigma=1.5, fill_holes=True, spur_length=args.spur_length,
                  tangent_pair_min_angle=140, simplify_tolerance=1.5)
    mask = preprocess(gray_pad, args.blur, args.threshold, args.closing, args.min_area,
                      recipe['background_sigma'], recipe['silhouette_sigma'])
    raw_skeleton = skeletonize(mask)
    skeleton, removed = prune_spurs(raw_skeleton, recipe['spur_length'])
    graph = graph_from_skeleton(skeleton)
    candidates = candidate_strokes(graph)
    if not candidates:
        raise ValueError('No candidate strokes; inspect source and parameters')
    for s in candidates:
        s['points'] = simplify(s['points'], recipe['simplify_tolerance'])
    points = np.array([p for s in candidates for p in s['points']])
    low, high = points.min(axis=0), points.max(axis=0)
    scale = 800 / max(float(np.max(high - low)), 1)
    offset = np.array([500, 500]) - (low + high) * scale / 2
    strokes = [[Point(round(x * scale + offset[0], 4), round(y * scale + offset[1], 4))
                for x, y in s['points']] for s in candidates]
    name = 'Image2GFont_Yong_P1'
    metadata = GFontMetadata(name=name, font_id='Phase1Candidate', glyph_count=1,
                             description='Image-derived candidate; stroke order unconfirmed')
    font = GFont(metadata, {cp: Glyph(cp, strokes)}, [cp])
    GFontV5Writer.write(font, dest / 'yong_candidate.gfont')
    rebuilt = GFontV5Reader.read(dest / 'yong_candidate.gfont')
    if rebuilt.metadata != metadata or set(rebuilt.glyphs) != {cp}:
        raise RuntimeError('Font metadata roundtrip failed')
    # Compare against explicit float32 quantization, not arbitrary float64 equality.
    for expected, actual in zip(strokes, rebuilt.glyphs[cp].strokes):
        if len(expected) != len(actual):
            raise RuntimeError('Stroke point count changed')
        for a, b in zip(expected, actual):
            if float(np.float32(a.x)) != b.x or float(np.float32(a.y)) != b.y:
                raise RuntimeError('Point roundtrip failed')
    assert len(strokes) == len(rebuilt.glyphs[cp].strokes)
    save_json(dest / 'generated_graph.json', graph)
    save_json(dest / 'stroke_candidates.json', dict(schema_version=1, coordinate_space='padded_working_pixels',
                                                  strokes=candidates, confirmed_strokes=None))
    save_json(dest / 'glyph_candidate.json', dict(schema_version=1, codepoint=cp, status='candidate',
                                               strokes=[[asdict(p) for p in s] for s in strokes]))
    Image.fromarray(np.uint8(~mask) * 255).save(dest / 'binary.png')
    Image.fromarray(np.uint8(~raw_skeleton) * 255).save(dest / 'skeleton_raw.png')
    Image.fromarray(np.uint8(~skeleton) * 255).save(dest / 'skeleton_pruned.png')
    canvas = ImageOps.expand(working, padding, fill='white')
    overlay = canvas.copy()
    draw = ImageDraw.Draw(overlay)
    palette = ['#e63946', '#0077b6', '#2a9d8f', '#9b5de5', '#f77f00', '#8c564b', '#c0268c']
    for i, s in enumerate(candidates):
        xy = [tuple(p) for p in s['points']]
        color = palette[i % len(palette)]
        if len(xy) > 1:
            draw.line(xy, fill=color, width=3)
        x, y = xy[0]
        draw.ellipse((x-4,y-4,x+4,y+4),fill=color)
        draw.text((x+5,y-10), str(i+1), fill=color)
    overlay.save(dest / 'stroke_overlay.png')
    paths = Image.new('RGB', canvas.size, 'white')
    draw = ImageDraw.Draw(paths)
    for i, s in enumerate(candidates):
        xy = [tuple(p) for p in s['points']]
        if len(xy) > 1:
            draw.line(xy, fill=palette[i % len(palette)], width=3)
    w, h = canvas.size
    comparison = Image.new('RGB', (2*w, 2*(h+36)), '#f2f4f7')
    panels = [(canvas,'SOURCE'), (Image.fromarray(np.uint8(~mask)*255).convert('RGB'),'BINARY / HOLES FILLED'),
              (overlay,'CANDIDATE PATHS ON SOURCE'), (paths,'CANDIDATE PATHS / ORDER UNCONFIRMED')]
    for i, (panel, label) in enumerate(panels):
        x, y = (i%2)*w, (i//2)*(h+36)
        comparison.paste(panel,(x,y+36))
        ImageDraw.Draw(comparison).text((x+10,y+10),label,fill='#152238')
    comparison.save(dest / 'comparison.png')
    ys, xs = np.where(mask)
    warnings = ['Automatic candidates: stroke order/direction and junction pairing are not human-confirmed.',
                'Hole filling may change topology; review binary against source.',
                'Font coordinate Y direction and size require application preview.']
    if xs.min() <= padding+2 or xs.max() >= padding+working.width-3 or ys.min() <= padding+2 or ys.max() >= padding+working.height-3:
        warnings.append('Ink touches original image boundary; clipped ink cannot be recovered.')
    save_json(dest / 'project.json', dict(format='Image2GFontProject', schema_version=1,
              phase='single-glyph experiment', source=dict(path=str(args.source),sha256=source_hash,
              preserved=preserved.name,original_size=list(source.size)),
              binding=dict(codepoint=cp,character=chr(cp),locked=True,origin='user supplied Yong image in agreed single-glyph task'),
              recipe=recipe, versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pillow=pillow_version),
              generated_graph='generated_graph.json', candidates='stroke_candidates.json', confirmed_strokes=None,
              export=dict(path='yong_candidate.gfont',experimental=True,font_name=name,coordinate_scale=scale,coordinate_offset=offset.tolist()),
              qc=dict(stroke_count=len(strokes),point_count=sum(map(len,strokes)),graph_edges=len(graph['edges']),
                      graph_nodes=len(graph['nodes']),pruned_pixels=removed,warnings=warnings,
                      font_roundtrip=True,application_test='NOT RUN',machine_test='NOT RUN')))
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError('Original source changed')
    print(json.dumps(dict(strokes=len(strokes),points=sum(map(len,strokes)),edges=len(graph['edges']),warnings=warnings)))


if __name__ == '__main__':
    main()
