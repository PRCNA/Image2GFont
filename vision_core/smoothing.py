"""Bounded raster-centerline smoothing, in working-image pixels."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from image_pipeline.core import simplify


def smooth_path(points, mask=None, max_shift=1.0):
    """Preserve endpoints, short paths and coarse corners; never join paths.

    Input/output use the one-pixel-padded skeleton coordinate system.
    The displacement bound applies before final 0.15px simplification.
    """
    if not np.isfinite(max_shift) or max_shift < 0:
        raise ValueError('max_shift must be finite and nonnegative')
    p = np.asarray(points, dtype=float)
    if len(p) < 7 or max_shift == 0:
        return p.tolist()
    locked = {0, len(p)-1}
    # Coarse simplification distinguishes intentional bends from pixel stairs.
    coarse = np.asarray(simplify(p.tolist(), 1.5))
    for i in range(1, len(coarse)-1):
        a, b = coarse[i]-coarse[i-1], coarse[i+1]-coarse[i]
        denominator = np.linalg.norm(a)*np.linalg.norm(b)
        if denominator and np.dot(a,b)/denominator < np.cos(np.deg2rad(50)):
            locked.add(int(np.argmin(np.linalg.norm(p-coarse[i], axis=1))))
    q = p.copy()
    anchors = sorted(locked)
    for start, end in zip(anchors, anchors[1:]):
        if end-start < 6:
            continue
        part = p[start:end+1]
        proposal = gaussian_filter1d(part, 1.5, axis=0, mode='nearest')
        # Fade displacement near anchors to avoid an endpoint kink.
        taper = np.minimum(np.arange(len(part)), np.arange(len(part))[::-1])
        delta = (proposal-part)*np.minimum(taper/3, 1)[:,None]
        length = np.linalg.norm(delta, axis=1)
        delta *= np.minimum(1, max_shift/np.maximum(length,1e-12))[:,None]
        q[start:end+1] = part+delta
    if mask is not None:
        xy = np.rint(q-1).astype(int)
        inside = (xy[:,0]>=0)&(xy[:,0]<mask.shape[1])&(xy[:,1]>=0)&(xy[:,1]<mask.shape[0])
        valid = np.zeros(len(q),dtype=bool)
        valid[inside] = mask[xy[inside,1],xy[inside,0]]
        q[~valid] = p[~valid]
    # Simplify each anchor interval independently, retaining exact corners.
    result = []
    for start,end in zip(anchors, anchors[1:]):
        section = simplify(q[start:end+1].tolist(), .15)
        result.extend(section if not result else section[1:])
    return result
