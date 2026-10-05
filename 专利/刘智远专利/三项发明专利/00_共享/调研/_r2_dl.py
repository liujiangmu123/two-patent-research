# -*- coding: utf-8 -*-
"""Download <=8 open-access PDFs/spec sheets and dump text for reading (temporary helper)."""
import sys
import time
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
DST = BASE / "文献_LiDAR与振动"
TXT = BASE / "_r2_txt"
DST.mkdir(exist_ok=True)
TXT.mkdir(exist_ok=True)

ITEMS = [
    ("RIEGL_VUX-120-23_Datasheet.pdf", "https://www.thefuture3d.com/spec-sheets/riegl/RIEGL_VUX-120-23__Datasheet_2026-08-20_EN.pdf"),
    ("RIEGL_miniVUX-3UAV_Datasheet.pdf", "https://ggs-solutions.eu/wp-content/uploads/2024/05/miniVUX-3UAV-Data-Sheet.pdf"),
    ("DJI_Zenmuse_L3_Datasheet.pdf", "https://optron.com/wp-content/uploads/2026/01/ds_ZENMUSE-L3.pdf"),
    ("EVACES2025_FMCW_laser_radar_SS01_1186.pdf", "https://www.fe.up.pt/evaces2025/ficheiros/papers_finais/SS01_paper_1186.pdf"),
    ("DTU_WindTurbine_Tower_Oscillation_Automotive_Lidar.pdf", "https://backend.orbit.dtu.dk/ws/files/457746835/Blade_Deflection_and_Tower_Oscillation_Sensing_of_Full-scale_Wind_Turbines_with_Automotive_Lidars.pdf"),
    ("Halkon_Rothberg_LDV_from_UAV.pdf", "https://opus.lib.uts.edu.au/bitstream/10453/127756/1/Towards%20laser%20Doppler%20vibrometry%20from%20unmanned%20aerial%20vehicles%20-%20full%20paper%2017-9-18.pdf"),
    ("Luzi2020_Telecom_Tower_GBRAR_Modal_rs12071211.pdf", "https://www.mdpi.com/2072-4292/12/7/1211/pdf"),
    ("TriasBlanco2023_Bridge_Vibration_LiDAR_rs15041003.pdf", "https://www.mdpi.com/2072-4292/15/4/1003/pdf"),
]

for name, url in ITEMS:
    out = DST / name
    try:
        if not out.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not data.startswith(b"%PDF"):
                print("NOT_PDF", name, len(data))
                continue
            out.write_bytes(data)
        doc = fitz.open(out)
        text = "\n".join(p.get_text() for p in doc)
        (TXT / (out.stem + ".txt")).write_text(text, encoding="utf-8")
        print("ok", name, doc.page_count, "pages", len(text), "chars")
    except Exception as e:  # noqa: BLE001
        print("FAIL", name, e)
    time.sleep(2)
