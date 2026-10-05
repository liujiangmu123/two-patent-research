// -*- coding: utf-8 -*-
// 说明书计算算例：全部由 00_设计基准/设计基准参数.json 按式（1）～式（5）计算，check_patent.py 用同一公式独立复算。
// 仿真数值读取 03_仿真验证/数据/*.json、02_详细设计/数据/*.json；读不到时返回 'TODO(...)'，保持可替换。
'use strict';
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const B = JSON.parse(fs.readFileSync(path.join(ROOT, '00_设计基准', '设计基准参数.json'), 'utf8'));

const TC = B['尾座液压缸26'];
const D = TC['缸径'], d = TC['杆径'], S = TC['行程'];
const A1 = Math.PI / 4 * D * D;                 // mm2
const A2 = Math.PI / 4 * (D * D - d * d);
const beta = B['油液']['有效体积模量_锁闭腔_MPa'];     // MPa = N/mm2
const betaH = B['油液']['有效体积模量_含软管_MPa'];
const alpha = B['油液']['体膨胀系数_1_K'];
const km = B['尾座机械刚度']['k_m_N_um'];             // N/um
const V0b = B['锁闭容积']['阀块直装缸体_每腔死容积'] * 1000;   // mm3
const V0h = B['锁闭容积']['常规软管连接_每腔附加容积'] * 1000;
const F0 = B['尾座推力']['F0_额定'];
const ppre = B['预压']['有杆腔预压压力_p_pre'];

// x：活塞伸出量 mm；hose：是否计软管附加容积
function lock(x, opt = {}) {
  const Vd = opt.hose ? V0b + V0h : V0b;
  const b = opt.hose ? betaH : beta;
  const V1 = A1 * x + Vd, V2 = A2 * (S - x) + Vd;            // mm3
  const k1 = b * A1 * A1 / V1 / 1000, k2 = b * A2 * A2 / V2 / 1000;  // N/um
  const Ks = k1 * km / (k1 + km), Kd = (k1 + k2) * km / (k1 + k2 + km);
  const Ts = b * alpha * A1 * km / (k1 + km);                // N/K
  const Td = b * alpha * (A1 - A2) * km / (k1 + k2 + km);
  return { x, V1: V1 / 1000, V2: V2 / 1000, k1, k2, Ks, Kd, Ts, Td };
}
const p1set = (F, pp = ppre) => (F + pp * A2) / A1;

const f = (v, n = 1) => v.toFixed(n);
const fmt = { f };

// ---------------------------------------------------------------- 数据文件读取
function readJSON(rel) {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8').split('-Infinity').join('null').split('Infinity').join('null').split('NaN').join('null')); } catch (e) { console.error('读取失败', rel, e.message); return null; }
}
// get('03_仿真验证/数据/xxx.json', ['a','b'], digits) → 字符串；缺失时 TODO
function get(rel, keys, digits, tag) {
  const j = readJSON(rel);
  let v = j;
  for (const k of keys || []) { if (v == null) break; v = v[k]; }
  if (v == null) return `TODO(${tag || keys.join('.')})`;
  if (typeof v === 'number' && digits != null) return v.toFixed(digits);
  return String(v);
}

module.exports = { B, A1, A2, beta, alpha, km, F0, ppre, lock, p1set, fmt, get, readJSON, ROOT };
