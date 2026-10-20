"""Optional component-preserving growth from an explicitly trusted seed mask.

This protects seed connectivity, NOT true handwriting topology. A fragmented
seed remains fragmented; light strokes absent from the seed may be omitted.
"""
import heapq
import numpy as np
from scipy import ndimage as ndi
from .core import preprocess


def preserve_components(reference, candidate, preserve_holes=False):
    """Retain all seed pixels; admit candidate pixels without merging seeds.

    Both masks must be 2-D bool arrays. Connectivity is 8-neighbour. Growth is
    deterministic, ordered by distance from seeds, then row/column. Unseeded
    candidate regions are excluded. With preserve_holes=True, additions must
    also preserve 4-connected background topology (including the exterior).
    This conservative local test can refuse geometrically harmless additions.
    Returns (new mask, diagnostics), leaving both inputs unchanged.
    """
    reference=np.asarray(reference);candidate=np.asarray(candidate)
    if type(preserve_holes) is not bool:
        raise ValueError('preserve_holes must be bool')
    if reference.dtype!=np.bool_ or candidate.dtype!=np.bool_:
        raise ValueError('Masks must have bool dtype')
    if reference.ndim!=2 or candidate.shape!=reference.shape or not reference.size:
        raise ValueError('Masks must be nonempty 2-D arrays of the same shape')
    owners,count=ndi.label(reference,np.ones((3,3)))
    distance=ndi.distance_transform_edt(~reference)
    queued=reference.copy();queue=[];rejected=0;hole_rejected=0
    height,width=reference.shape
    def neighbours(y,x):
        for yy in range(max(0,y-1),min(height,y+2)):
            for xx in range(max(0,x-1),min(width,x+2)):
                if (yy,xx)!=(y,x):yield yy,xx
    def schedule(y,x):
        if candidate[y,x] and not queued[y,x]:
            queued[y,x]=True
            heapq.heappush(queue,(float(distance[y,x]),y,x))
    def background_stays_connected(y,x):
        # Outside the image belongs to background. Only cardinal neighbours
        # touch the removed background pixel under 4-connectivity.
        patch=np.zeros((3,3),bool)
        for yy in range(max(0,y-1),min(height,y+2)):
            for xx in range(max(0,x-1),min(width,x+2)):
                patch[yy-y+1,xx-x+1]=bool(owners[yy,xx])
        patch[1,1]=True
        labels,_=ndi.label(~patch)
        adjacent={int(labels[yy,xx]) for yy,xx in [(0,1),(1,0),(1,2),(2,1)] if labels[yy,xx]}
        return len(adjacent)==1
    border=ndi.binary_dilation(reference,structure=np.ones((3,3))) & candidate & ~reference
    for y,x in zip(*np.where(border)):schedule(int(y),int(x))
    while queue:
        _,y,x=heapq.heappop(queue)
        adjacent={int(owners[yy,xx]) for yy,xx in neighbours(y,x) if owners[yy,xx]}
        if len(adjacent)!=1:
            rejected+=1
            continue
        if preserve_holes and not background_stays_connected(y,x):
            hole_rejected+=1
            continue
        owners[y,x]=adjacent.pop()
        for yy,xx in neighbours(y,x):schedule(yy,xx)
    result=owners!=0
    result_count=ndi.label(result,np.ones((3,3)))[1]
    if result_count!=count or np.any(reference & ~result):
        raise RuntimeError('Component preservation invariant failed')
    def holes(mask):return int(ndi.label(ndi.binary_fill_holes(mask)&~mask)[1])
    before_holes,after_holes=holes(reference),holes(result)
    if preserve_holes and before_holes!=after_holes:
        raise RuntimeError('Hole preservation invariant failed')
    return result,dict(seed_components=int(count),result_components=int(result_count),
                       seed_pixels_restored=int((reference & ~candidate).sum()),
                       candidate_pixels_excluded=int((candidate & ~result).sum()),
                       conflict_pixels_rejected=int(rejected),
                       unvisited_candidate_pixels=int((candidate & ~queued).sum()),
                       added_pixels=int((result & ~reference).sum()),
                       no_seeds=not bool(count),
                       preserve_holes=preserve_holes,hole_pixels_rejected=int(hole_rejected),
                       seed_holes=before_holes,result_holes=after_holes,
                       guarantee='seed connectivity only; not true stroke correctness')


def preprocess_preserving_components(gray, reference_mask, preserve_holes=False, **parameters):
    """Explicit opt-in wrapper; no universal reference threshold is assumed."""
    if np.asarray(gray).shape!=np.asarray(reference_mask).shape:
        raise ValueError('Image and reference mask shapes differ')
    return preserve_components(reference_mask,preprocess(gray,**parameters),preserve_holes=preserve_holes)
