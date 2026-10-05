# -*- coding: utf-8 -*-
"""下载开放获取文献 PDF 到 ../文献/（单文件 < 30 MB），并抽取文本到 _txt/ 便于检索核对。
失败记录写入 ../文献/_下载记录.json。用法：.venv\\Scripts\\python.exe download_lit.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
LIT = HERE.parent / "文献"
TXT = HERE / "_txt"
LIT.mkdir(exist_ok=True)
TXT.mkdir(exist_ok=True)
LOG = LIT / "_下载记录.json"
MAX = 30 * 1024 * 1024

ITEMS = [
    ("L01_AppSci2026_PointCloud2FEM_TransmissionTower.pdf", "https://www.mdpi.com/2076-3417/16/13/6640/pdf?version=1782999154"),
    ("L02_AppSci2026_DigitalTwin_SHM_TransmissionTower_BIM_IoT_FEM.pdf", "https://www.mdpi.com/2076-3417/16/8/3620/pdf"),
    ("L03_Buildings2024_CrossBracing_DLT5486_ASCE10_GB50017.pdf", "https://www.mdpi.com/2075-5309/14/6/1784/pdf"),
    ("L04_Buildings2026_BayesianOMA_Review.pdf", "https://www.mdpi.com/2075-5309/16/9/1807/pdf?version=1778492256"),
    ("L05_Sensors2020_VibrationAnatomy_TransmissionTower_LimitedSensors.pdf", "https://www.mdpi.com/1424-8220/20/6/1731/pdf"),
    ("L06_AppSci2019_Kriging_ModalFrequencySensor_TowerSettlement.pdf", "https://res.mdpi.com/d_attachment/applsci/applsci-09-03343/article_deploy/applsci-09-03343-v2.pdf"),
    ("L07_EVACES2025_DigitalTwin_OMA_100mSteelTrussTower.pdf", "https://fe.up.pt/evaces2025/ficheiros/papers_finais/SS13_paper_1196.pdf"),
    ("L08_Frontiers2015_SensorPlacement_TransmissionTower_Entropy.pdf", "https://www.frontiersin.org/articles/10.3389/fbuil.2015.00024/pdf"),
    ("L09_Buildings2026_SensorPlacement_MPA_FIM_TransmissionTower.pdf", "https://www.mdpi.com/2075-5309/16/10/2018/pdf"),
    ("L10_Buildings2025_MultiObjective_OSP_BayesianModalID_Entropy.pdf", "https://www.mdpi.com/2075-5309/15/5/821/pdf?version=1741243185"),
    ("L11_Sensors2024_GPS_PPS_Sync_WirelessSensors.pdf", "https://www.mdpi.com/1424-8220/24/1/199/pdf"),
    ("L12_Sensors2020_Synchronized_HighSensitivity_WirelessAccelerometer.pdf", "https://www.mdpi.com/1424-8220/20/15/4169/pdf"),
    ("L13_IWSHM2025_Accelerometer_PPS.pdf", "https://flore.unifi.it/retrieve/3b0239fc-af1f-4a19-aa64-1a3dd45fbb37/2025___IWSHM___Accelerometer_PPS-2.pdf"),
    ("L14_Liverpool_BayesianModelUpdating_BoltedJoints_MCMC.pdf", "https://livrepository.liverpool.ac.uk/3017833/1/STC-17-0017%20revised.pdf"),
    ("L15_TMCMC_Ching_Chen_NCREE.pdf", "https://www.ncree.org/GetFile.ashx?id=10000647"),
    ("L16_TMCMC_Observations_Improvements_TUM.pdf", "http://mediatum.ub.tum.de/doc/1451922/document.pdf"),
    ("L17_Algorithms2026_ISSA_TransmissionTower_SizingOptimization.pdf", "https://www.mdpi.com/1999-4893/19/7/513/pdf"),
    ("L18_Designs2023_TrihedralLatticeTower_Optimization_Slenderness.pdf", "https://www.mdpi.com/2411-9660/7/1/10/pdf"),
    ("L19_ADXL354_ADXL355_Datasheet_RevC.pdf", "https://www.mouser.com/datasheet/2/609/adxl354_adxl355-3122364.pdf"),
    ("L20_Epson_M-A352AD10_Datasheet.pdf", "https://www.epsondevice.com/sensing/en/pdf/m-a352_datasheet_e_rev20220401.pdf"),
    ("L21_Kionix_KX134-1211_Specifications.pdf", "https://cdn.sparkfun.com/assets/b/2/6/2/e/KX134-1211_Datasheet.pdf"),
    ("L22_Sensors2026_QMEMS_Accelerometer_SHM_Evaluation.pdf", "https://www.mdpi.com/1424-8220/26/17/5528/pdf?version=1788179975"),
    ("L23_Buildings2022_TransmissionTower_FullScaleTest_BoltSlip.pdf", "https://www.mdpi.com/2075-5309/12/4/389/pdf"),
    ("L24_Sustainability2022_LongSpanTower_Aeroelastic_WindTunnel.pdf", "https://www.mdpi.com/2071-1050/14/18/11613/pdf"),
    ("L25_RemoteSens2024_GNSS_Accelerometer_Integrated_Sensor.pdf", "https://www.mdpi.com/2072-4292/16/4/607/pdf"),
    ("L26_Polimi2025_FEModelUpdating_DigitalTwin_OMA_Thesis.pdf", "https://www.politesi.polimi.it/retrieve/9d472077-43cd-417e-b57d-9132effdebec/2025_04_Ali.pdf"),
    ("L27_Epson_M-A352AD10_BriefSheet.pdf", "https://www.epsondevice.com/sensing/en/pdf/m-a352ad10_briefsheet_e_rev20220401.pdf"),
]

HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def extract_text(pdf_path, txt_path):
    try:
        import fitz  # PyMuPDF
        with fitz.open(pdf_path) as doc:
            txt_path.write_text("\n".join(p.get_text() for p in doc), encoding="utf-8")
        return True
    except Exception as e:  # 非 PDF 或损坏
        return str(e)


def main(only=None):
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    for name, url in ITEMS:
        if only and not any(name.startswith(o) for o in only):
            continue
        dst = LIT / name
        if dst.exists() and dst.stat().st_size > 10_000 and log.get(name, {}).get("ok"):
            continue
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=60) as r:
                clen = int(r.headers.get("Content-Length") or 0)
                if clen > MAX:
                    raise RuntimeError(f"too large {clen}")
                data = r.read(MAX + 1)
            if len(data) > MAX:
                raise RuntimeError("too large (>30MB)")
            if not data[:5].startswith(b"%PDF"):
                raise RuntimeError("not a PDF (likely HTML/landing page)")
            dst.write_bytes(data)
            ok = extract_text(dst, TXT / (dst.stem + ".txt"))
            log[name] = {"url": url, "ok": True, "bytes": len(data), "text": ok is True}
            print("ok  ", name, len(data))
        except Exception as e:
            log[name] = {"url": url, "ok": False, "error": str(e)}
            print("FAIL", name, e)
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(1.0)


if __name__ == "__main__":
    main(sys.argv[1:] or None)
