import FreeCAD as App
import FreeCADGui as Gui
App.setActiveDocument('CheTailstockV2')
view=Gui.activeDocument().activeView()
view.viewAxonometric();view.fitAll()
path='H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/04_检查/精细核心视图.png'
view.saveImage(path,1600,1000,'White')
_result_={'image':path}
