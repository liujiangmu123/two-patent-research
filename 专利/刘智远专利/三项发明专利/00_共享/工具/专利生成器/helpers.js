// -*- coding: utf-8 -*-
// 说明书源公共助手：在 patent_desc.js 中  const { H, SH, EQ, TB, LABELS, n, pct, J } = require('<本文件>');
'use strict';
const fs = require('fs');
const H = (text) => ({ t: 'h', text });            // 说明书五个部分标题（不编段号）：技术领域/背景技术/发明内容/附图说明/具体实施方式
const SH = (text) => ({ t: 'sh', text });          // 小标题（编段号，加粗）
const EQ = (text, no) => ({ t: 'eq', text, no });  // 公式段（编段号，公式居中，式号右对齐）
const TB = (caption, head, rows, firstColRatio) => ({ t: 'table', caption, head, rows, firstColRatio });
const LABELS = { t: 'labels' };                    // 自动生成附图标记说明（放在具体实施方式末尾）
// 数值格式：负号用 U+2212；d 位小数
const n = (x, d = 1) => {
  if (x === null || x === undefined || Number.isNaN(Number(x))) throw new Error('数值缺失：' + x);
  const s = (Math.abs(x) < 0.5 * Math.pow(10, -d) ? 0 : Number(x)).toFixed(d);
  return s.replace('-', '−');
};
const pct = (x, d = 1) => n(100 * x, d);            // 比例 → 百分数字符串（不含 %）
const J = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));   // 读取仿真数据 JSON
module.exports = { H, SH, EQ, TB, LABELS, n, pct, J };
