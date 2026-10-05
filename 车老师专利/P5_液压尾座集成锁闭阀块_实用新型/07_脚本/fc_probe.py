# -*- coding: utf-8 -*-
"""FreeCAD 空探针：只打印版本和已打开文档，不做任何写入。用法：powershell -File 07_脚本\\run_fc.ps1 fc_probe.py"""
import FreeCAD as App

print("VERSION", App.Version()[:4])
print("DOCS", list(App.listDocuments().keys()))
