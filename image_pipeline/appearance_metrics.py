"""Pen-down appearance and travel diagnostics, independent of normative order."""
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree
from .trajectory_metrics import resample


def render_ink(paths,width,size=200,supersample=4):
    """Union of round capsules, independent of direction and pen-up order.

    Uniform circular nib, no pressure/velocity model. Pixel-center distance
    tests at supersampled resolution, then box averaging. Integer coordinates
    are pixel CENTERS, matching skeleton/graph image-index coordinates.
    Coordinates are not
    aligned or rescaled. Content outside the canvas is clipped.
    """
    if not np.isfinite(width) or width<=0 or width>size*2:
        raise ValueError('Invalid width')
    if type(size) is not int or not 1<=size<=2048 or type(supersample) is not int or not 1<=supersample<=8:
        raise ValueError('Invalid render dimensions')
    coverage=np.zeros((size*supersample,size*supersample),bool);radius=width/2
    for stroke in paths:
        p=np.asarray(stroke,dtype=float)
        # Validate using the common path sampler, retaining original vertices.
        resample(p)
        segments=list(zip(p,p[1:])) if len(p)>1 else [(p[0],p[0])]
        for a,b in segments:
            low=np.floor((np.minimum(a,b)-radius+.5)*supersample).astype(int)
            high=np.ceil((np.maximum(a,b)+radius+.5)*supersample).astype(int)
            x0,y0=np.clip(low,0,size*supersample);x1,y1=np.clip(high,0,size*supersample)
            if x1<=x0 or y1<=y0:continue
            xx,yy=np.meshgrid((np.arange(x0,x1)+.5)/supersample-.5,(np.arange(y0,y1)+.5)/supersample-.5)
            delta=b-a;den=float(delta@delta)
            t=np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/den,0,1) if den else 0.
            distance=(xx-a[0]-t*delta[0])**2+(yy-a[1]-t*delta[1])**2
            coverage[y0:y1,x0:x1]|=distance<=radius*radius+1e-10
    ink=coverage.reshape(size,supersample,size,supersample).mean(axis=(1,3))
    return np.rint(255*(1-ink)).astype('uint8')


def compare_ink(reference,predicted):
    """Compare identical-size black-on-white rasters without registration.

    Empty-union overlap is undefined (None), not a perfect glyph score.
    Binary metrics use gray<128; soft metrics use ink=1-gray/255.
    """
    a=np.asarray(reference,dtype=float);b=np.asarray(predicted,dtype=float)
    if a.ndim!=2 or a.shape!=b.shape or not a.size:
        raise ValueError('Expected matching nonempty grayscale images')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or min(a.min(),b.min())<0 or max(a.max(),b.max())>255:
        raise ValueError('Grayscale values must be finite in 0..255')
    am=a<128;bm=b<128;intersection=int((am&bm).sum());union=int((am|bm).sum())
    missing=int((am&~bm).sum());extra=int((bm&~am).sum())
    ai=1-a/255;bi=1-b/255;soft_union=float(np.maximum(ai,bi).sum())
    return dict(reference_pixels=int(am.sum()),predicted_pixels=int(bm.sum()),
        overlap_iou=intersection/union if union else None,
        missing_fraction=missing/int(am.sum()) if am.any() else None,
        extra_fraction=extra/int(bm.sum()) if bm.any() else None,
        missing_pixels=missing,extra_pixels=extra,
        soft_overlap_iou=float(np.minimum(ai,bi).sum())/soft_union if soft_union else None)


def geometry(reference,predicted):
    """Union-of-centerlines comparison: ignores grouping, direction and order."""
    def points(paths):
        arrays=[resample(s,spacing=.5) for s in paths]
        return np.unique(np.concatenate(arrays),axis=0) if arrays else np.empty((0,2))
    a,b=points(reference),points(predicted)
    if not len(a) or not len(b):
        return dict(reference_to_predicted_mean=None,reference_to_predicted_p95=None,
                    predicted_to_reference_mean=None,predicted_to_reference_p95=None,
                    undefined_reason='one or both centerline sets are empty')
    ab=cKDTree(b).query(a)[0];ba=cKDTree(a).query(b)[0]
    return dict(reference_to_predicted_mean=float(ab.mean()),reference_to_predicted_p95=float(np.percentile(ab,95)),
                predicted_to_reference_mean=float(ba.mean()),predicted_to_reference_p95=float(np.percentile(ba,95)),undefined_reason=None)


def travel(paths):
    """Lengths in working pixels. Retracing uses undirected 1px grid edges.

    It is a repeat-travel proxy, NOT a physical ink-darkness or time estimate.
    Crossing at a point alone is not a repeated edge. No pen-up connector is ink.
    """
    clean=[np.asarray(s,dtype=float) for s in paths]
    edges=Counter();length=0.;dots=0
    for s in clean:
        sampled=resample(s,spacing=.5)  # also validates all points
        length+=float(np.linalg.norm(np.diff(s,axis=0),axis=1).sum())
        grid=np.rint(sampled).astype(int)
        grid=grid[np.r_[True,np.any(np.diff(grid,axis=0)!=0,axis=1)]]
        if len(grid)==1:dots+=1
        for a,b in zip(grid,grid[1:]):
            edges[tuple(sorted((tuple(a),tuple(b))))]+=1
    total=sum(np.linalg.norm(np.asarray(a)-b)*count for (a,b),count in edges.items())
    repeated=sum(np.linalg.norm(np.asarray(a)-b)*(count-1) for (a,b),count in edges.items())
    air=sum(float(np.linalg.norm(a[-1]-b[0])) for a,b in zip(clean,clean[1:]))
    return dict(paths=len(clean),pen_lift_transitions=max(0,len(clean)-1),
        pen_down_length=length,pen_up_length=air,
        retraced_grid_length=float(repeated),retraced_grid_fraction=float(repeated/total) if total else 0.,
        subpixel_or_point_paths=dots)
