'''
==============================================
Introduction part 3 : the famous scatter image
==============================================
'''

import glob
from pymt import *

w = MTWindow(fullscreen=False)

piclist = glob.glob('./pictures/*.jpg')

k = MTKinetic()
w.add_widget(k)

p = MTScatterPlane()
k.add_widget(p)

for pic in piclist:
    p.add_widget(MTScatterImage(filename=pic))

runTouchApp()
