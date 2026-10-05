import FreeCAD as App
doc=App.getDocument('CheBlockDrawingV2')
# addView initially centres views, so position only after membership is established.
positions={'Front':(110,110),'Top':(110,195),'Right':(267,110),'DesignNotes':(301,223),'Title':(210,35),'DimFront250':(0,-41),'DimFront62':(-96,0),'DimTop90':(-96,0)}
for name,(x,y) in positions.items():
    o=doc.getObject(name);o.X=x;o.Y=y
doc.recompute()
_result_={'positions':positions,'dimensions':[(doc.getObject(n).Name,doc.getObject(n).getRawValue()) for n in ('DimFront250','DimFront62','DimTop90')]}
