import FreeCAD as App
import Part
import os
print(os.path.isfile('H:\\Axinjihua\\02动画项目\\05动画Harness工作台\\专利文档资料\\建模工程\\模型\\V1_LZT_CAL_20261003\\LZT_CAL_01.FCStd'),os.path.getsize('H:\\Axinjihua\\02动画项目\\05动画Harness工作台\\专利文档资料\\建模工程\\模型\\V1_LZT_CAL_20261003\\LZT_CAL_01.FCStd') if os.path.isfile('H:\\Axinjihua\\02动画项目\\05动画Harness工作台\\专利文档资料\\建模工程\\模型\\V1_LZT_CAL_20261003\\LZT_CAL_01.FCStd') else 0)
print(list(App.listDocuments()))
