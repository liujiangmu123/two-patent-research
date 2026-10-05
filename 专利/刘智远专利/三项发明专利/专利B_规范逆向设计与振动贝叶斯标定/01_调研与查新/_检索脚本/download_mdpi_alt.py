# -*- coding: utf-8 -*-
"""MDPI 主站对脚本返回 403，改走 res.mdpi.com / mdpi-res.com 的 d_attachment 直链重试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import download_lit as D  # noqa: E402

# (文件名, journal, vol, art)
MDPI = [
    ("L01_AppSci2026_PointCloud2FEM_TransmissionTower.pdf", "applsci", 16, 6640),
    ("L02_AppSci2026_DigitalTwin_SHM_TransmissionTower_BIM_IoT_FEM.pdf", "applsci", 16, 3620),
    ("L03_Buildings2024_CrossBracing_DLT5486_ASCE10_GB50017.pdf", "buildings", 14, 1784),
    ("L04_Buildings2026_BayesianOMA_Review.pdf", "buildings", 16, 1807),
    ("L05_Sensors2020_VibrationAnatomy_TransmissionTower_LimitedSensors.pdf", "sensors", 20, 1731),
    ("L09_Buildings2026_SensorPlacement_MPA_FIM_TransmissionTower.pdf", "buildings", 16, 2018),
    ("L10_Buildings2025_MultiObjective_OSP_BayesianModalID_Entropy.pdf", "buildings", 15, 821),
    ("L11_Sensors2024_GPS_PPS_Sync_WirelessSensors.pdf", "sensors", 24, 199),
    ("L12_Sensors2020_Synchronized_HighSensitivity_WirelessAccelerometer.pdf", "sensors", 20, 4169),
    ("L17_Algorithms2026_ISSA_TransmissionTower_SizingOptimization.pdf", "algorithms", 19, 513),
    ("L18_Designs2023_TrihedralLatticeTower_Optimization_Slenderness.pdf", "designs", 7, 10),
    ("L22_Sensors2026_QMEMS_Accelerometer_SHM_Evaluation.pdf", "sensors", 26, 5528),
    ("L23_Buildings2022_TransmissionTower_FullScaleTest_BoltSlip.pdf", "buildings", 12, 389),
    ("L24_Sustainability2022_LongSpanTower_Aeroelastic_WindTunnel.pdf", "sustainability", 14, 11613),
    ("L25_RemoteSens2024_GNSS_Accelerometer_Integrated_Sensor.pdf", "remotesensing", 16, 607),
]


def urls(j, v, a):
    stem = f"{j}-{v:02d}-{a:05d}"
    for host in ("https://mdpi-res.com", "https://res.mdpi.com"):
        for suf in ("", "-v2", "-v3"):
            yield f"{host}/d_attachment/{j}/{stem}/article_deploy/{stem}{suf}.pdf"


def main():
    import json
    import time
    import urllib.request
    log = json.loads(D.LOG.read_text(encoding="utf-8")) if D.LOG.exists() else {}
    for name, j, v, a in MDPI:
        if log.get(name, {}).get("ok"):
            continue
        tried = []
        for u in urls(j, v, a):
            try:
                req = urllib.request.Request(u, headers=D.HDR)
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read(D.MAX + 1)
                if len(data) > D.MAX or not data[:5].startswith(b"%PDF"):
                    raise RuntimeError("not pdf / too large")
                dst = D.LIT / name
                dst.write_bytes(data)
                D.extract_text(dst, D.TXT / (dst.stem + ".txt"))
                log[name] = {"url": u, "ok": True, "bytes": len(data)}
                print("ok  ", name, u)
                break
            except Exception as e:
                tried.append(f"{u} -> {e}")
            time.sleep(0.8)
        else:
            prev = log.get(name, {})
            log[name] = {"url": prev.get("url", ""), "ok": False, "error": prev.get("error", ""), "alt_tried": tried}
            print("FAIL", name)
        D.LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
