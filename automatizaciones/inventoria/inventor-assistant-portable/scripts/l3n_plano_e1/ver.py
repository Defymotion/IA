import sys, ezdxf, matplotlib
from ezdxf import recover
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, ColorPolicy
matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig=plt.figure(figsize=(24,20)); ax=fig.add_axes([0,0,1,1])
d,_=recover.readfile('/tmp/claude-0/dxfpl/zona.dxf')
cfg=Configuration(color_policy=ColorPolicy.MONOCHROME_LIGHT_BG, custom_fg_color='#9a9a9a')
Frontend(RenderContext(d),MatplotlibBackend(ax),config=cfg).draw_layout(d.modelspace(),finalize=False)
o=ezdxf.readfile(sys.argv[1])
Frontend(RenderContext(o),MatplotlibBackend(ax)).draw_layout(o.modelspace(),finalize=False)
x0,x1,y0,y1=[float(v) for v in sys.argv[3].split(',')]
ax.set_xlim(x0,x1); ax.set_ylim(y0,y1); ax.set_aspect('equal'); ax.set_facecolor('white'); fig.patch.set_facecolor('white')
fig.savefig(sys.argv[2],dpi=int(sys.argv[4]) if len(sys.argv)>4 else 60)
