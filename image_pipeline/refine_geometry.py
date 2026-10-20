"""Optional small geometry refinement against a clean, uniform-nib source.

Uses the raster only, never recorded strokes. Requires a known working-pixel
pen width; not a universal photo cleanup or pressure-varying nib model.
"""
import math
import numpy as np
from scipy import ndimage as ndi
from .appearance_metrics import render_ink,compare_ink


def topology(image):
    mask=np.asarray(image)<128
    return (int(ndi.label(mask,np.ones((3,3)))[1]),
            int(ndi.label(ndi.binary_fill_holes(mask)&~mask)[1]))


def refine_geometry(source,paths,pen_width,max_step=.75,rounds=2):
    """Preserve path count/order and shared nodes; cap total per-node motion.

    Junction/shared vertices and sharp corners are fixed. Smooth interior nodes
    move along normals toward ink centroids. Unique endpoints may move along
    their tangent toward a half-ink boundary minus the nib radius. Global steps
    require improved soft IoU, nondecreased binary IoU and unchanged raster
    component/hole counts. These are input-fitting constraints, not proof that
    each individual local change is correct.
    """
    source=np.asarray(source)
    if source.ndim!=2 or source.shape[0]!=source.shape[1]:
        raise ValueError('Expected a square grayscale working image')
    if type(rounds) is not int or not 0<=rounds<=10:
        raise ValueError('rounds must be an integer in 0..10')
    if not math.isfinite(max_step) or not 0<max_step<=2:
        raise ValueError('max_step must be in (0,2] pixels')
    current=[[list(map(float,p)) for p in s] for s in paths]
    original=[[p[:] for p in s] for s in current]
    before=render_ink(current,pen_width,size=source.shape[0])
    score=compare_ink(source,before);shape=topology(before)
    groups={}
    for i,s in enumerate(current):
        for j,p in enumerate(s):groups.setdefault(tuple(p),[]).append((i,j))
    fixed={index for members in groups.values() if len(members)>1 for index in members}
    ink=1-source.astype(float)/255
    def sample(points):
        return ndi.map_coordinates(ink,np.asarray(points).T[::-1],order=1,mode='constant',cval=0.)
    accepted=[];attempts=0;rejected_topology=0
    if not np.any(source<128):
        return current,dict(accepted=[],attempts=0,reason='no dark source pixels',changed_vertices=0)
    for iteration in range(rounds):
        for kind in ['normal','endpoint']:
            proposals=[]
            for i,s in enumerate(current):
                if len(s)<2:continue
                for j,p in enumerate(s):
                    if (i,j) in fixed:continue
                    p=np.asarray(p);endpoint=j in (0,len(s)-1)
                    if kind=='normal' and not endpoint:
                        left=p-np.asarray(s[j-1]);right=np.asarray(s[j+1])-p
                        a,b=np.linalg.norm(left),np.linalg.norm(right)
                        if min(a,b)<1e-9 or float(left@right/(a*b))<math.cos(math.pi/4):continue
                        tangent=left/a+right/b;tangent/=np.linalg.norm(tangent)
                        normal=np.array([-tangent[1],tangent[0]])
                        offsets=np.arange(-max(2.,pen_width*.9),max(2.,pen_width*.9)+.125,.25)
                        weights=sample(p+offsets[:,None]*normal)
                        if weights.sum()<1e-6:continue
                        displacement=float(offsets@weights/weights.sum())
                        delta=normal*np.clip(displacement,-max_step,max_step)
                    elif kind=='endpoint' and endpoint:
                        neighbour=np.asarray(s[1] if j==0 else s[-2]);tangent=p-neighbour
                        length=np.linalg.norm(tangent)
                        if length<1e-9:continue
                        tangent/=length
                        offsets=np.arange(-max_step,pen_width+max_step+.125,.25)
                        values=sample(p+offsets[:,None]*tangent)
                        crossings=np.where((values[:-1]>=.5)&(values[1:]<.5))[0]
                        if not len(crossings):continue
                        k=int(crossings[0]);fraction=(values[k]-.5)/(values[k]-values[k+1])
                        boundary=offsets[k]+fraction*.25
                        delta=tangent*np.clip(boundary-pen_width/2,-max_step,max_step)
                    else:continue
                    # Bound cumulative motion, not just the latest step.
                    target=p+delta;origin=np.asarray(original[i][j]);total=target-origin
                    distance=np.linalg.norm(total)
                    if distance>max_step:target=origin+total*max_step/distance
                    if np.linalg.norm(target-p)>1e-5:proposals.append((i,j,p,target-p))
            if not proposals:continue
            for factor in (1.,.5):
                trial=[[p[:] for p in s] for s in current]
                for i,j,p,delta in proposals:trial[i][j]=(p+delta*factor).tolist()
                rendered=render_ink(trial,pen_width,size=source.shape[0]);attempts+=1
                if topology(rendered)!=shape:
                    rejected_topology+=1;continue
                candidate=compare_ink(source,rendered)
                if (candidate['soft_overlap_iou'] is not None and score['soft_overlap_iou'] is not None
                    and candidate['soft_overlap_iou']>score['soft_overlap_iou']+1e-7
                    and candidate['overlap_iou']>=score['overlap_iou']-1e-12):
                    current=trial;score=candidate
                    accepted.append(dict(iteration=iteration,kind=kind,factor=factor));break
    changes=[float(np.linalg.norm(np.asarray(a)-b)) for s,t in zip(original,current) for a,b in zip(s,t)]
    return current,dict(accepted=accepted,attempts=attempts,rejected_topology=rejected_topology,
        changed_vertices=sum(v>1e-6 for v in changes),max_displacement=max(changes,default=0.),
        max_step=max_step,rounds=rounds,fixed_shared_vertices=len(fixed),
        limitation='Fit to input raster; topology counts do not prove per-location correctness')
