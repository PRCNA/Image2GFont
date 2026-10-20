"""Mask-to-centerline geometry; independent from all OCR backends."""
import numpy as np
from image_pipeline.core import skeletonize,graph_from_skeleton,candidate_strokes,simplify
from gfont_core import Glyph,Point
from .segmentation import segment,SegmentationConfig
from .smoothing import smooth_path


def extract(image,codepoint,config=SegmentationConfig(),smooth=True):
    working,mask,report=segment(image,config)
    thin=skeletonize(np.pad(mask,1))
    raw=[s['points'] for s in candidate_strokes(graph_from_skeleton(thin))]
    paths=[smooth_path(p,mask) if smooth else simplify(p,.5) for p in raw]
    # No automatic spur pruning: short marks can be real handwriting details.
    scale=800/max(working.size);ox=-working.width*scale/2;oy=-900
    strokes=[[Point((x-1)*scale+ox,(y-1)*scale+oy) for x,y in path] for path in paths]
    if not strokes:raise ValueError('No ink trajectories; inspect segmentation mode/mask')
    glyph=Glyph(codepoint,strokes);glyph.validate()
    report.update(status='candidate',paths=len(strokes),transform=dict(scale=scale,offset=[ox,oy]),driver_verified=False)
    report['smoothing']=dict(enabled=smooth,method='bounded_gaussian_v1',sigma=1.5,max_shift_working_px=1.0,simplify_tolerance_px=.15,corner_turn_degrees=50) if smooth else dict(enabled=False)
    return glyph,working,mask,report
