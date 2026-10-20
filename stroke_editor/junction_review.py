"""Review exact shared vertices without replacing unrelated user edits."""
from collections import Counter
from copy import deepcopy
from gfont_core import Point
from image_pipeline.junction_candidates import junction_candidates,_trace


class JunctionReview:
    def __init__(self,session,cp):
        self.session=session;self.cp=cp;self.snapshot=session.paths[cp]
        paths=[[(p.x,p.y) for p in s] for s in self.snapshot]
        counts=Counter(p for s in paths for p in s)
        nodes={};edges=[];self.pairs={}
        def node(p):
            if p not in nodes:nodes[p]=len(nodes)
            return nodes[p]
        for path in paths:
            cuts=sorted({0,len(path)-1}|{i for i,p in enumerate(path) if counts[p]>1})
            chunks=[path[a:b+1] for a,b in zip(cuts,cuts[1:])] if len(path)>1 else [path]
            ids=[]
            for points in chunks:
                idx=len(edges);ids.append(idx)
                edges.append(dict(id=idx,start=node(points[0]),end=node(points[-1]),points=[list(p) for p in points]))
            for a,b in zip(ids,ids[1:]):self.pairs[a,1]=(b,0);self.pairs[b,0]=(a,1)
        degree=Counter(n for e in edges for n in (e['start'],e['end']))
        self.graph=dict(nodes=[dict(id=i,point=list(p),degree=degree[i]) for p,i in nodes.items()],edges=edges)
        # Heuristic length scales are converted from nominal 200px space.
        scale=max(float(session.font.metadata.font_size)/200,1e-6)
        normalized=deepcopy(self.graph)
        for n in normalized['nodes']:n['point']=[v/scale for v in n['point']]
        for e in normalized['edges']:e['points']=[[x/scale,y/scale] for x,y in e['points']]
        _,self.reports=junction_candidates(normalized,3)

    def check(self):
        if self.session.paths[self.cp]!=self.snapshot:raise ValueError('Paths changed; analyze again before accepting')

    def preview(self,report_index,candidate_index):
        self.check();report=self.reports[report_index];candidate=report['candidates'][candidate_index]
        pairs=dict(self.pairs);node=report['node']
        ends={(e['id'],s) for e in self.graph['edges'] for s,n in enumerate((e['start'],e['end'])) if n==node}
        for end in ends:
            other=pairs.pop(end,None)
            if other is not None:pairs.pop(other,None)
        for a,b in candidate['pairs']:pairs[a]=b;pairs[b]=a
        return [[Point(*p) for p in s['points']] for s in _trace(self.graph['edges'],pairs)]

    def accept(self,report_index,candidate_index):
        paths=self.preview(report_index,candidate_index)
        self.session.change(self.cp,paths,confirmed=False)

    def width_graph(self,reference):
        image,sx,sy,ox,oy=reference
        if not sx or not sy:raise ValueError('Invalid source registration')
        graph=deepcopy(self.graph)
        for n in graph['nodes']:n['point']=[(n['point'][0]-ox)/sx,(n['point'][1]-oy)/sy]
        for e in graph['edges']:e['points']=[[(x-ox)/sx,(y-oy)/sy] for x,y in e['points']]
        return graph
