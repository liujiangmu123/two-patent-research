import FreeCAD as App
doc=App.getDocument(App._che_bench_doc)
path='H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/03_模型/精细液压试验台_V2.FCStd'
doc.saveAs(path)
_result_={'saved':path,'parts':len([o for o in doc.Objects if 'EngineeringPartNo' in o.PropertiesList])}
