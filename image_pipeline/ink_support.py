"""Optional bright-bridge guard and source-profile width diagnostics.

For normalized black ink on a light background only. Widths are metadata for
review, not GFont commands or machine pressure instructions.
"""
import numpy as np
from scipy import ndimage as ndi


def supported_mask(gray,candidate,seed_threshold=128,bridge_threshold=192):
    gray=np.asarray(gray);candidate=np.asarray(candidate)
    if gray.ndim!=2 or not gray.size or candidate.shape!=gray.shape or candidate.dtype!=np.bool_:
        raise ValueError('Expected grayscale and same-shaped boolean mask')
    if not np.isfinite(gray).all() or gray.min()<0 or gray.max()>255:
        raise ValueError('Invalid grayscale values')
    if not 0<seed_threshold<bridge_threshold<256:raise ValueError('Invalid thresholds')
    seed=gray<seed_threshold
    result=(candidate & (gray<bridge_threshold)) | seed
    return result,dict(removed_bright_pixels=int((candidate & ~result).sum()),
        restored_dark_pixels=int((seed & ~candidate).sum()),
        limitation='May split genuine light strokes; does not certify true topology')


def local_widths(gray,graph,threshold=128,max_radius=32.,step=.25):
    """Normal-profile half-intensity crossings at graph vertices.

    Junction endpoints and points within 1.5 estimated local EDT diameters of
    a junction are excluded. Missing crossings and non-ink centers are flagged.
    Values describe source ink, not the necessarily narrower skeleton path.
    """
    gray=np.asarray(gray,dtype=float)
    if gray.ndim!=2 or not gray.size or not np.isfinite(gray).all() or gray.min()<0 or gray.max()>255:
        raise ValueError('Invalid grayscale image')
    if not np.isfinite(max_radius) or not np.isfinite(step) or not 0<step<=max_radius<=128 or not 0<threshold<256:
        raise ValueError('Invalid profile parameters')
    radii=ndi.distance_transform_edt(gray<threshold)
    junctions=[np.array(n['point']) for n in graph['nodes'] if n['degree']>=3]
    def sample(array,points,cval):return ndi.map_coordinates(array,np.asarray(points).T[::-1],order=1,mode='constant',cval=cval)
    rows=[]
    for edge in graph['edges']:
        points=np.array(edge['points'],dtype=float)
        for i,p in enumerate(points):
            entry=dict(edge=edge['id'],vertex=i,point=p.tolist(),width=None)
            radius=float(sample(radii,[p],0)[0])
            if len(points)<2:entry['reason']='isolated point'
            elif any(np.linalg.norm(p-j)<=max(3.,3*radius) for j in junctions):entry['reason']='junction vicinity'
            else:
                delta=points[min(i+2,len(points)-1)]-points[max(0,i-2)]
                length=np.linalg.norm(delta)
                if length<1e-9:entry['reason']='undefined tangent'
                elif sample(gray,[p],255)[0]>=threshold:entry['reason']='center outside dark ink'
                else:
                    normal=np.array([-delta[1],delta[0]])/length
                    offsets=np.arange(0,max_radius+step/2,step);distances=[]
                    for sign in (-1,1):
                        values=sample(gray,p+sign*offsets[:,None]*normal,255)
                        hits=np.flatnonzero(values>=threshold)
                        if not len(hits):break
                        k=int(hits[0])
                        if k==0:break
                        fraction=(threshold-values[k-1])/(values[k]-values[k-1])
                        distances.append(float(offsets[k-1]+step*fraction))
                    if len(distances)==2:entry.update(width=sum(distances),reason='measured')
                    else:entry['reason']='boundary not found'
            rows.append(entry)
    return rows
