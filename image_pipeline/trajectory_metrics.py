"""Compare candidates to recorded strokes; this is not a normative stroke oracle."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import linear_sum_assignment


def _path(points):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or not len(p) or not np.isfinite(p).all():
        raise ValueError('Expected a nonempty finite Nx2 path')
    return p[np.r_[True,np.any(np.diff(p,axis=0)!=0,axis=1)]]


def resample(points,spacing=1.0,count=None):
    """Arc-length sampling, including endpoints; duplicate points are harmless."""
    p=_path(points)
    if not np.isfinite(spacing) or spacing<=0:raise ValueError('Invalid spacing')
    if count is not None and (type(count) is not int or not 2<=count<=100000):
        raise ValueError('Invalid sample count')
    if len(p)==1:return np.repeat(p,count or 1,axis=0)
    cumulative=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    if cumulative[-1]/spacing>100000:raise ValueError('Path too long for metric')
    t=np.linspace(0,cumulative[-1],count) if count else np.r_[np.arange(0,cumulative[-1],spacing),cumulative[-1]]
    return np.column_stack([np.interp(t,cumulative,p[:,i]) for i in range(2)])


def match_strokes(reference,predicted,geometry_tolerance=3.,endpoint_tolerance=5.,progress_tolerance=5.):
    """One-to-one geometry/endpoint/progress matching in working-image pixels.

    Pair acceptance: both directional nearest-distance p95 <=3 px; endpoints
    <=5 px; 64-point normalized arc-length progress p95 <=5 px, in a consistent
    forward OR reverse direction. Thresholds are configurable but must be fixed
    before evaluating. Assignment maximizes accepted pairs, then minimizes cost.
    Recorded order and direction are a separate all-strokes-match criterion.
    These tolerance-based metrics do not prove exact traversal or standard order.
    """
    if any(not np.isfinite(v) or v<=0 for v in (geometry_tolerance,endpoint_tolerance,progress_tolerance)):
        raise ValueError('Tolerances must be positive finite numbers')
    truth=[resample(p) for p in reference];guess=[resample(p) for p in predicted]
    ta=[cKDTree(p) for p in truth];tb=[cKDTree(p) for p in guess]
    pa=[resample(p,count=64) for p in reference];pb=[resample(p,count=64) for p in predicted]
    m,n=len(truth),len(guess);details={};cost=np.zeros((m,n))
    for i,a in enumerate(truth):
        for j,b in enumerate(guess):
            distance=max(float(np.percentile(ta[i].query(b)[0],95)),float(np.percentile(tb[j].query(a)[0],95)))
            forward=max(float(np.linalg.norm(a[0]-b[0])),float(np.linalg.norm(a[-1]-b[-1])))
            reverse=max(float(np.linalg.norm(a[0]-b[-1])),float(np.linalg.norm(a[-1]-b[0])))
            fp=float(np.percentile(np.linalg.norm(pa[i]-pb[j],axis=1),95))
            rp=float(np.percentile(np.linalg.norm(pa[i]-pb[j][::-1],axis=1),95))
            direct=distance<=geometry_tolerance and forward<=endpoint_tolerance and fp<=progress_tolerance
            reversed_ok=distance<=geometry_tolerance and reverse<=endpoint_tolerance and rp<=progress_tolerance
            valid=direct or reversed_ok
            details[i,j]=dict(reference_index=i,predicted_index=j,p95_distance=distance,
                forward_endpoint_error=forward,reverse_endpoint_error=reverse,
                forward_progress_p95=fp,reverse_progress_p95=rp,
                direct_valid=bool(direct),reverse_valid=bool(reversed_ok),valid=bool(valid))
            secondary=distance+min(forward+fp,reverse+rp)
            cost[i,j]=(0 if valid else min(m,n)+1)+secondary/(1+secondary)
    assignments=[]
    if m and n:
        a,b=linear_sum_assignment(cost)
        assignments=[details[int(i),int(j)] for i,j in zip(a,b)]
    matched=sum(p['valid'] for p in assignments)
    full=bool(m and m==n and matched==m)
    return dict(reference_count=m,predicted_count=n,count_equal=m==n,matched=matched,
        stroke_precision=matched/n if n else 0.,stroke_recall=matched/m if m else 0.,
        full_unordered_match=full,
        full_ordered_directed_match=full and all(p['reference_index']==p['predicted_index'] and p['direct_valid'] for p in assignments),
        assignments=assignments,geometry_tolerance=geometry_tolerance,
        endpoint_tolerance=endpoint_tolerance,progress_tolerance=progress_tolerance)
