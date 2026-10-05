# -*- coding: utf-8 -*-
"""Quick quantitative checks for the R2 report (temporary)."""
import math
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 1) footprint (full width, mrad * R) ; aperture ignored except where spec gives value
div = {  # (axis1 mrad, axis2 mrad)
    "VUX-120-23": (0.4, 0.4), "miniVUX-3": (1.6, 0.5), "ZenmuseL2(4x12cm@100m)": (0.4, 1.2),
    "ZenmuseL3": (0.25, 0.25), "LivoxAvia": (0.28 * math.pi / 180 * 1e3, 0.03 * math.pi / 180 * 1e3),
    "LivoxAvia2": (0.25, 0.25),
}
print("footprint mm at R")
for k, (a, b) in div.items():
    print(k, [(R, round(a * R, 1), round(b * R, 1)) for R in (40, 60, 100, 120)])

# 2) point spacing from density
for rho in (100, 152.6, 500, 1000, 2000):
    print("rho", rho, "spacing m", round(1 / math.sqrt(rho), 3))


# 3) expected points per member
def n_hits(rho, b, L, sin_g, vis, D=0.0, kappa=0.5, shape=1.2):
    return rho * (b * shape + kappa * D) * L * sin_g * vis


cases = [
    ("PTM-LiAirX3 main leg L220 6m", 152.6, 0.22, 6, 0.34, 0.6, 0.03),
    ("PTM-LiAirX3 diagonal L140 3m", 152.6, 0.14, 3, 0.71, 0.7, 0.03),
    ("PTM-LiAirX3 aux L90 1.5m", 152.6, 0.09, 1.5, 0.71, 0.5, 0.03),
    ("PTM-LiAirX3 aux L50 1.2m", 152.6, 0.05, 1.2, 0.71, 0.5, 0.03),
    ("VUX NFB 2 strips main leg", 2000, 0.22, 6, 0.34, 0.6, 0.03),
    ("VUX NFB 2 strips aux L50", 2000, 0.05, 1.2, 0.71, 0.5, 0.03),
    ("Tilt45 x2 heads main leg (rho_perp=600)", 600, 0.22, 6, 0.71, 0.8, 0.015),
    ("Tilt45 x2 heads aux L50", 600, 0.05, 1.2, 0.71, 0.75, 0.015),
]
for c in cases:
    print(c[0], round(n_hits(*c[1:]), 1))

# 4) Doppler CRLB velocity precision
lam = 1.55e-6
for T in (5e-6, 10e-6, 20e-6):
    for snr_db in (10, 20, 30):
        snr = 10 ** (snr_db / 10)
        sf = math.sqrt(6) / (2 * math.pi * T * math.sqrt(snr))
        print("T", T, "SNRdB", snr_db, "sigma_v mm/s", round(lam / 2 * sf * 1e3, 2), "Dv_res mm/s", round(lam / (2 * T) * 1e3, 1))

# 5) tower response amplitudes
for f in (1.0, 1.5, 3.0):
    for a_mg in (0.5, 2, 5):
        a = a_mg * 9.81e-3
        print("f", f, "a mg", a_mg, "v mm/s", round(a / (2 * math.pi * f) * 1e3, 3), "d mm", round(a / (2 * math.pi * f) ** 2 * 1e3, 4))


# 6) PSD SNR at node
def psd_snr(sig_s, zeta, fn, sig_pt, npts, fframe, nnodes=1):
    peak = sig_s ** 2 / (math.pi * zeta * fn)
    sig_eff = sig_pt / math.sqrt(npts)
    noise = sig_eff ** 2 / (fframe / 2)
    return 10 * math.log10(peak / noise) + 10 * math.log10(nnodes)


for sig_s in (0.5e-3, 1e-3, 3e-3):
    for npts in (50, 100, 400):
        print("sig_s", sig_s, "npts", npts, "SNR dB single", round(psd_snr(sig_s, 0.02, 1.5, 0.03, npts, 10), 1),
              "30nodes", round(psd_snr(sig_s, 0.02, 1.5, 0.03, npts, 10, 30), 1))

# 7) ego-velocity residual from static points
for nst in (1000, 5000, 20000):
    print("static pts", nst, "ego sigma mm/s (cond 3)", round(0.03 / math.sqrt(nst) * 3 * 1e3, 3))

# 8) ToF displacement error from attitude error
for R in (40, 60, 100):
    for att in (0.005, 0.01, 0.02):
        print("R", R, "att deg", att, "lateral err mm", round(R * math.radians(att) * 1e3, 1))
