# -*- coding: utf-8 -*-
"""autograd 高性能算子：行收集 take（反向传播用 numba 散射累加，替代 numpy 的 np.add.at）。"""
from __future__ import annotations

import numpy as np
from autograd.extend import defvjp, primitive
from numba import njit


@njit(cache=True)
def _scatter_rows(out, idx, g):
    for i in range(idx.shape[0]):
        r = idx[i]
        for j in range(g.shape[1]):
            out[r, j] += g[i, j]


@njit(cache=True)
def _scatter_1d(out, idx, g):
    for i in range(idx.shape[0]):
        out[idx[i]] += g[i]


@primitive
def take(A, idx):
    """A[idx]（idx 为一维整数数组）。"""
    return A[idx]


def _take_vjp(ans, A, idx):
    shape = A.shape

    def vjp(g):
        out = np.zeros(shape)
        g = np.asarray(g, float)
        if len(shape) == 1:
            _scatter_1d(out, idx, g)
        else:
            _scatter_rows(out.reshape(shape[0], -1), idx, np.ascontiguousarray(g.reshape(len(idx), -1)))
        return out
    return vjp


defvjp(take, _take_vjp, None)
