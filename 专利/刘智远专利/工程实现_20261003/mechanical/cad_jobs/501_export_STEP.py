import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
Part.export([obj for obj in doc.Objects if hasattr(obj,'Shape')],'H:\\Axinjihua\\02动画项目\\05动画Harness工作台\\专利文档资料\\建模工程\\模型\\V1_LZT_CAL_20261003\\LZT_CAL_01.step')
