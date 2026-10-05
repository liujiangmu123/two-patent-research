import FreeCAD as App
doc=App.getDocument('CheBlockDrawingV2')
v=doc.Front
methods={n:getattr(getattr(v,n),'__doc__','') for n in dir(v) if 'Edge' in n or 'Geom' in n or 'Vertices' in n}
_result_={'methods':methods,'state':v.State,'scale':v.Scale,'direction':str(v.Direction)}
