"""Optional bounded junction pairing with explicit ambiguity diagnostics.

This changes traversal only: it never adds, removes or moves graph segments.
Scores are geometric heuristics, not probabilities or recovered stroke order.
"""
import math
import numpy as np


def _direction(points, distance):
    origin=np.asarray(points[0],float)
    target=origin
    for point in points[1:]:
        target=np.asarray(point,float)
        if np.linalg.norm(target-origin)>=distance:break
    delta=target-origin;length=np.linalg.norm(delta)
    return delta/length if length>1e-9 else None


def _angle(a,b):
    if a is None or b is None:return 0.
    return math.degrees(math.acos(float(np.clip(a@b,-1,1))))


def _matchings(ends):
    if not ends:
        yield [],[];return
    a,*rest=ends
    for pairs,loose in _matchings(rest):yield pairs,[a]+loose
    for i,b in enumerate(rest):
        if a[0]==b[0]:continue
        for pairs,loose in _matchings(rest[:i]+rest[i+1:]):yield [(a,b)]+pairs,loose


def _trace(edges,pairs):
    used=set();strokes=[]
    ends=[(e['id'],s) for e in edges for s in (0,1)]
    for start in sorted(ends,key=lambda e:(e in pairs,e)):
        if start[0] in used:continue
        current=start;points=[];ids=[]
        while current[0] not in used:
            idx,side=current;used.add(idx);ids.append(idx)
            chain=edges[idx]['points'][::1 if side==0 else -1]
            points.extend([list(p) for p in (chain if not points else chain[1:])])
            end=(idx,1-side)
            if end not in pairs:break
            current=pairs[end]
        strokes.append(dict(edge_ids=ids,points=points,status='candidate'))
    return strokes


def junction_candidates(graph,pen_width=3.,margin_threshold=15.,max_degree=6):
    """Enumerate partial matchings up to degree six; uncertain nodes keep legacy.

    Default score = sum(turn angles) + 40 degrees per unpaired end.
    Reject pair angles <120 degrees. Accept only a >=15 score margin and
    near/far tangent angle agreement within 20 degrees. These are experimental
    fixed thresholds. Input graph edges must be indexed by their contiguous id.
    """
    if not math.isfinite(pen_width) or pen_width<=0:raise ValueError('Invalid width')
    if not math.isfinite(margin_threshold) or margin_threshold<0:raise ValueError('Invalid margin')
    if type(max_degree) is not int or not 2<=max_degree<=6:raise ValueError('Degree cap must be 2..6')
    edges=graph['edges'];incident={}
    for idx,e in enumerate(edges):
        if e['id']!=idx:raise ValueError('Edges require contiguous ids')
        points=np.asarray(e['points'],float)
        if points.ndim!=2 or points.shape[1]!=2 or not len(points) or not np.isfinite(points).all():raise ValueError('Invalid points')
        for side,node in enumerate((e['start'],e['end'])):incident.setdefault(node,[]).append((idx,side))
    chosen={};reports=[]
    for node,ends in sorted(incident.items()):
        if len(ends)<2:continue
        vectors={end:[_direction(edges[end[0]]['points'][::1 if end[1]==0 else -1],d)
            for d in (max(2.,pen_width),max(4.,pen_width*2),12.)] for end in ends}
        # Reproduce the existing greedy fallback exactly; never silently discard
        # a branch when the new heuristic is unsure.
        legacy={};options=[]
        for i,a in enumerate(ends):
            for b in ends[i+1:]:
                if a[0]!=b[0]:
                    angle=_angle(vectors[a][2],vectors[b][2])
                    if angle>=140:options.append((-angle,a,b))
        for _,a,b in sorted(options):
            if a not in legacy and b not in legacy:legacy[a]=b;legacy[b]=a
        ranked=[]
        if len(ends)<=max_degree:
            for pairs,loose in _matchings(ends):
                angles=[[_angle(vectors[a][i],vectors[b][i]) for i in (0,1)] for a,b in pairs]
                if any(min(v)<120-1e-9 for v in angles):continue
                ranked.append(dict(pairs=pairs,unpaired=loose,
                    score=sum(180-sum(v)/2 for v in angles)+40*len(loose),
                    max_turn=max((180-min(v) for v in angles),default=0.),
                    tangent_disagreement=max((abs(v[0]-v[1]) for v in angles),default=0.)))
            ranked.sort(key=lambda c:(c['score'],c['pairs']))
        gap=ranked[1]['score']-ranked[0]['score'] if len(ranked)>1 else None
        accept=bool(len(ends)>=3 and ranked and ranked[0]['pairs'] and gap is not None and gap>=margin_threshold and ranked[0]['tangent_disagreement']<=20)
        local=legacy
        if accept:
            local={}
            for a,b in ranked[0]['pairs']:local[a]=b;local[b]=a
        chosen.update(local)
        if len(ends)>=3:
            reports.append(dict(node=node,degree=len(ends),status='accepted' if accept else 'review',
                reason='clear geometric margin' if accept else ('degree cap' if len(ends)>max_degree else 'ambiguous or unstable tangents'),
                score_margin=gap,candidate_count=len(ranked),candidates=ranked,
                selected_pairs=[(a,b) for a,b in sorted(local.items()) if a<b],
                changed_from_legacy=local!=legacy,
                appearance_discriminates=False))
    strokes=_trace(edges,chosen)
    assert sorted(i for s in strokes for i in s['edge_ids'])==list(range(len(edges)))
    return strokes,reports
