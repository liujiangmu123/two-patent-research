# -*- coding: utf-8 -*-
"""环境激励响应与测量误差模型。

- ambient_response：towerkit.loads.buffeting_loads（Kaimal 谱 + Davenport 相干的脉动风）作用下，
  模态叠加计算测点三轴加速度。
- MemsNoise：MEMS 加速度计噪声谱（白噪声底 + 1/f 闪烁）、温漂（日变化正弦 + 随机游走零偏、标度因数温漂）、
  采样同步误差（每节点固定时钟偏移 + 漂移），默认参数取 KX134 / ADXL355 类数据手册量级。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from towerkit import loads as TL

G0 = 9.80665


def ambient_response(fem, sensor_dofs, U10=8.0, duration=600.0, dt=0.05, n_modes=14, zeta=0.015,
                     seed=0, direction=(0.6, 0.8, 0.0)):
    """返回 (t, acc (nt, nch))。direction 取斜风使两主轴方向均被激励。"""
    t, F = TL.buffeting_loads(fem, U10=U10, duration=duration, dt=dt, direction=direction, seed=seed)
    # 叠加微弱宽带竖向/扭转随机力（模拟导线传递与湍流非相干成分），避免个别模态完全不被激励
    rng = np.random.default_rng(seed + 991)
    F = F + rng.normal(0.0, 1.0, F.shape) * np.abs(F).std() * 0.05
    _, acc, freq, phi = fem.modal_response(F, dt, n_modes=n_modes, zeta=zeta, out_dofs=sensor_dofs)
    return t, acc, freq, phi


@dataclass
class MemsNoise:
    noise_density_ug: float = 25.0      # 白噪声底 µg/√Hz
    flicker_corner_hz: float = 0.5      # 1/f 拐点
    bias_temp_mg_per_K: float = 0.2     # 零偏温度系数 mg/K
    temp_amp_K: float = 12.0            # 日温度变化幅值 K（10 min 段内体现为缓变）
    scale_temp_ppm_per_K: float = 150.0
    bias_rw_ug: float = 30.0            # 零偏随机游走 µg/√s
    sync_std_ms: float = 0.5            # 节点间时钟偏移标准差（GNSS PPS 授时）
    sync_drift_ppm: float = 2.0         # 两次 PPS 之间晶振漂移
    seed: int = 0

    def apply(self, t, acc, n_axes=3):
        rng = np.random.default_rng(self.seed)
        nt, nch = acc.shape
        dt = t[1] - t[0]
        fs = 1.0 / dt
        y = acc.copy()
        # 同步误差：每节点共享一个时间偏移（频域分数延迟）
        nn = nch // n_axes
        tau = rng.normal(0.0, self.sync_std_ms * 1e-3, nn)
        drift = rng.normal(0.0, self.sync_drift_ppm * 1e-6, nn)
        f = np.fft.rfftfreq(nt, dt)
        Y = np.fft.rfft(y, axis=0)
        for k in range(nn):
            d = tau[k] + drift[k] * t.mean()
            Y[:, k * n_axes:(k + 1) * n_axes] *= np.exp(-2j * np.pi * f * d)[:, None]
        y = np.fft.irfft(Y, n=nt, axis=0)
        # 标度因数温漂 + 零偏温漂（温度在该时段内线性 + 正弦缓变）
        phase = rng.uniform(0, 2 * np.pi)
        dT = self.temp_amp_K * (np.sin(2 * np.pi * t / 86400.0 + phase) - np.sin(phase)) \
            + rng.normal(0, 0.3) * t / t[-1]
        for c in range(nch):
            y[:, c] *= 1.0 + self.scale_temp_ppm_per_K * 1e-6 * dT * rng.uniform(0.5, 1.5)
            y[:, c] += self.bias_temp_mg_per_K * 1e-3 * G0 * dT * rng.uniform(-1, 1)
            y[:, c] += np.cumsum(rng.normal(0, self.bias_rw_ug * 1e-6 * G0 * np.sqrt(dt), nt))
        # 噪声谱：白噪声底 + 1/f 成分（频域整形）
        sig_w = self.noise_density_ug * 1e-6 * G0 * np.sqrt(fs / 2)
        Wn = np.fft.rfft(rng.normal(0, 1, (nt, nch)), axis=0)
        shape = np.sqrt(1.0 + self.flicker_corner_hz / np.maximum(f, f[1]))[:, None]
        n = np.fft.irfft(Wn * shape, n=nt, axis=0) * sig_w
        return y + n, {"tau_s": tau.tolist(), "noise_rms": float(sig_w)}

    def psd_asd(self, f):
        """理论噪声幅值谱密度 m/s²/√Hz。"""
        return self.noise_density_ug * 1e-6 * G0 * np.sqrt(1.0 + self.flicker_corner_hz / np.maximum(f, 1e-3))
