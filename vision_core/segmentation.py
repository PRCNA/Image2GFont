"""Deterministic ink segmentation. Never reconstruct strokes from recognized text."""
from dataclasses import dataclass,asdict
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

MODES=('auto','dark','light','cyan','dark_red_grid')

@dataclass(frozen=True)
class SegmentationConfig:
    mode: str = 'auto'
    working_side: int = 384
    min_component: int = 3
    contrast: float = 10.0

    def validate(self):
        if self.mode not in MODES:raise ValueError('Unknown segmentation mode')
        if type(self.working_side) is not int or not 128<=self.working_side<=1024:raise ValueError('working_side must be 128..1024')
        if type(self.min_component) is not int or not 0<=self.min_component<=100:raise ValueError('Invalid component threshold')
        if not np.isfinite(self.contrast) or not 0<self.contrast<128:raise ValueError('Invalid contrast')


def otsu(values):
    hist,_=np.histogram(values,bins=256,range=(0,256));p=hist.astype(float)/max(hist.sum(),1)
    w=np.cumsum(p);m=np.cumsum(p*np.arange(256));v=(m[-1]*w-m)**2/np.maximum(w*(1-w),1e-12)
    return int(np.argmax(v))


def segment(image,config=SegmentationConfig()):
    config.validate();rgb=image.convert('RGB');original=rgb.size
    scale=config.working_side/max(original);size=tuple(max(1,round(v*scale)) for v in original)
    rgb=rgb.resize(size,Image.Resampling.BICUBIC)
    a=np.asarray(rgb,dtype=float);r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
    gray=.299*r+.587*g+.114*b
    cyan=(np.minimum(g,b)-r>22)&(g>95)&(b>95)
    red=(r-np.maximum(g,b)>16)
    mode=config.mode
    if mode=='auto':
        if cyan.mean()>.01:mode='cyan'
        elif np.median(gray)<115:mode='light'
        elif red.mean()>.008:mode='dark_red_grid'
        else:mode='dark'
    if mode=='cyan':
        # Bridge only very short color dropouts; keep large gaps for review.
        mask=ndi.binary_closing(cyan,structure=np.ones((3,3)))
    else:
        # Red-channel dropout suppresses red paper lines without erasing neutral black ink.
        channel=gray
        smooth=ndi.gaussian_filter(channel,.6)
        background=ndi.gaussian_filter(channel,config.working_side/12)
        t=otsu(smooth)
        if mode=='light':mask=(smooth>t)&(smooth-background>config.contrast)
        else:mask=(smooth<=t)&(background-smooth>config.contrast)
    if mode=='dark_red_grid':
        colored_grid=(r-g>8)&(r-b>8)
        mask &= ~ndi.binary_dilation(colored_grid,iterations=1)
    labels,n=ndi.label(mask,np.ones((3,3)))
    areas=np.bincount(labels.ravel());keep=areas>=config.min_component;keep[0]=False;mask=keep[labels]
    warnings=[]
    if mode=='cyan':warnings.append('color_dropout_bridging_requires_review')
    if mode=='dark_red_grid':warnings.append('red_ink_overlap_may_be_lost')
    if min(original)<80:warnings.append('low_source_resolution_no_detail_recovery')
    if mode in ('dark','light'):warnings.append('same_color_grid_not_removed')
    coverage=float(mask.mean())
    if coverage<.003 or coverage>.6:warnings.append('suspicious_foreground_coverage')
    return rgb,mask,dict(config=asdict(config),resolved_mode=mode,source_size=list(original),working_size=list(size),source_to_working=[size[0]/original[0],size[1]/original[1]],foreground_fraction=coverage,warnings=warnings,mask_confirmed=False)
