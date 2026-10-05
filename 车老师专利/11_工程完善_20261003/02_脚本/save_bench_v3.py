import FreeCAD as App
doc=App.getDocument('CheBenchV2')
doc.Label='精细液压试验台_V3_卡盘100_25_20'
path='H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/03_模型/精细液压试验台_V3.FCStd'
doc.saveAs(path)
_result_={'saved':path,'parts':len(App._che_bench_parts),'previous':'V2 retained as389-part engineering snapshot'}
