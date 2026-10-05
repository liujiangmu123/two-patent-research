import FreeCAD as App
import Part
assert 'LZT_CAL_01' not in App.listDocuments(), 'Existing document: inspect before continuing'
doc=App.newDocument('LZT_CAL_01')
doc.Label='LZT CAL 01 nominal ground calibration rig'
