# -*- coding: utf-8 -*-
"""R2 quantitative checks v2 (temporary helper, deleted after report)."""
import math
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 1. footprint (mm) & fill fraction for angle legs ----------
sensors = {  # name: (div_a mrad, div_b mrad, aperture mm)
    "VUX-120-23": (0.4, 0.4, 0), "miniVUX-3": (1.6, 0.5, 0), "Zenmuse L2": (0.4, 1.2, 0),
    "Zenmuse L3": (0.25, 0.25, 11), "Avia/HAP": (4.89, 0.52, 0), "Avia 2": (0.25, 0.25, 0),
}
legs = [40, 50, 63, 90, 140, 220]
print("== footprint mm (long axis) and fill fraction b/D (long axis) ==")
for R in (40, 60, 100):
    for k, (a, b, ap) in sensors.items():
        D = max(a, b) * R + ap
        fills = [round(min(1.0, bb * 4 / math.pi / D), 2) for bb in legs]
        print(R, k, round(D, 1), fills)

# ---------- 2. expected hits per member ----------
def hits(rho_perp, b_mm, L, sin_g, vis, D_mm, kappa=0.5, pd=1.0):
    w = (b_mm * 4 / math.pi + kappa * D_mm) / 1000.0
    return rho_perp * w * L * sin_g * vis * pd

print("== expected hits ==")
cases = [
    # name, rho_perp, b, L, sin_g, vis, D, pd
    ("X3 nadir main L220 6m", 152.6 * 0.35, 220, 6, 0.95, 0.6, 290, 1.0),
    ("X3 nadir diag L140 3m", 152.6 * 0.35, 140, 3, 0.9, 0.7, 290, 0.9),
    ("X3 nadir aux L63 1.5m", 152.6 * 0.35, 63, 1.5, 0.9, 0.5, 290, 0.6),
    ("X3 nadir aux L50 1.2m", 152.6 * 0.35, 50, 1.2, 0.9, 0.5, 290, 0.5),
    ("VUX NFB 2strips main", 450 * 2 * 0.5, 220, 6, 0.95, 0.7, 24, 1.0),
    ("VUX NFB 2strips aux L50", 450 * 2 * 0.5, 50, 1.2, 0.9, 0.6, 24, 1.0),
    ("Tilt45x2 L3 600 main", 600, 220, 6, 0.95, 0.85, 15, 1.0),
    ("Tilt45x2 L3 600 aux L50", 600, 50, 1.2, 0.9, 0.8, 15, 1.0),
]
for c in cases:
    print(c[0], round(hits(*c[1:]), 1))

# ---------- 3. FMCW velocity: required points per node per frame ----------
print("== FMCW required Np for PSD SNR 10 dB ==")
for sig_v in (0.003, 0.01, 0.03):
    for v_rms in (0.0005, 0.0015, 0.004):
        zeta, fn, fs = 0.02, 1.5, 10
        snr = 10.0
        Np = snr * 2 * math.pi * zeta * fn * sig_v ** 2 / (v_rms ** 2 * fs)
        print("sig_v", sig_v, "v_rms", v_rms, "Np", round(Np, 1))

# ---------- 4. ToF geometric displacement noise from hovering UAV ----------
print("== ToF per-frame node displacement noise (mm) ==")
for R in (40, 60):
    for att in (0.005, 0.01):
        for pos in (5, 10):
            for Np in (50, 200):
                s = math.sqrt((20 / math.sqrt(Np)) ** 2 + (R * 1000 * math.radians(att)) ** 2 + pos ** 2)
                print(R, att, pos, Np, round(s, 1))

# ---------- 5. ego velocity from static points ----------
print("== ego velocity sigma (mm/s) ==")
for sig_v in (0.003, 0.03):
    for Ns in (500, 2000, 10000):
        print(sig_v, Ns, round(sig_v / math.sqrt(Ns) * 3 * 1000, 3))

# ---------- 6. section-scale identifiability from frequency ----------
print("== d ln f / d ln s for uniform section scale s, nonstructural mass ratio r ==")
for r in (0.05, 0.1, 0.2, 0.3, 0.5):
    print(r, round(0.5 * r / (1 + r), 3), "-> freq change % for 10% scale:", round(100 * (math.sqrt(1.1 / (1.1 + r) * (1 + r)) - 1), 2))
print("stiffness-only 10% loss freq change %", round(100 * (math.sqrt(0.9) - 1), 2))

# ---------- 7. deflection margin ----------
for ratio in (0.71, 0.76, 0.82):
    print("ratio", ratio, "K loss to reach limit %", round(100 * (1 - ratio), 1))

# ---------- 8. tower response amplitudes ----------
print("== ambient response ==")
for f in (1.0, 1.5, 3.0):
    for a_mg in (0.5, 2, 5):
        a = a_mg * 9.81e-3
        print(f, a_mg, "v mm/s", round(a / (2 * math.pi * f) * 1e3, 2), "d mm", round(a / (2 * math.pi * f) ** 2 * 1e3, 3))

# ---------- 9. tower silhouette points per frame (Aeva-like) ----------
pts_s = 4e6 * 0.5   # assume half of raw points valid
fr = 10
fov_h, fov_v = 120, 30
tower_h_deg, tower_w_deg = 30, 10   # 30 m high section, ~10 m wide at 60 m
frac = (tower_h_deg * tower_w_deg) / (fov_h * fov_v)
fill = 0.15
per_frame = pts_s / fr * frac * fill
print("points on steel per frame", round(per_frame), "per node (40 nodes)", round(per_frame / 40))
