// -*- coding: utf-8 -*-
// P5 说明书数值来源：00_设计基准/P5_设计基准.json、03_校核计算/校核计算.json、04_模型/_check_report.json、P1 设计基准（共用参数）。
// 说明书文本只通过本文件取数，不手填；读不到时返回 'TODO(...)'，由 check_patent.py 报错。
'use strict';
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const rj = (rel) => JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
const B = rj('00_设计基准/P5_设计基准.json');
const CJ = rj('03_校核计算/校核计算.json');
const CAD = rj('04_模型/_check_report.json');
const B1 = JSON.parse(fs.readFileSync(path.resolve(ROOT, B['P1基准']['文件']), 'utf8'));

// get(obj, ['a','b'], digits)
function get(obj, keys, digits) {
  let v = obj;
  for (const k of keys) { if (v == null) break; v = v[k]; }
  if (v == null) return `TODO(${keys.join('.')})`;
  if (typeof v === 'number' && digits != null) return v.toFixed(digits);
  return String(v);
}
const S = CJ['汇总'];
const TC = B1['尾座液压缸26'];
const V = {
  // P1 共用
  D: TC['缸径'], d: TC['杆径'], stroke: TC['行程'], A1: get(CJ, ['共用参数_P1', 'A1_mm2'], 1), A2: get(CJ, ['共用参数_P1', 'A2_mm2'], 1),
  beta: B1['油液']['有效体积模量_锁闭腔_MPa'], betaH: B1['油液']['有效体积模量_含软管_MPa'], km: B1['尾座机械刚度']['k_m_N_um'],
  vdP1: B1['锁闭容积']['阀块直装缸体_每腔死容积'], vhose: B1['锁闭容积']['常规软管连接_每腔附加容积'], x0: TC['顶紧位置_伸出量_额定'],
  // 结构
  blk: B['阀块本体']['外形_LxWxH'], zg: B['阀块本体']['锁闭油道高度ZG'],
  pd: B['设计工况']['设计压力_MPa'], pt: B['设计工况']['试验压力_MPa'], qc: B['设计工况']['校核流量_L_min'], qa: B['设计工况']['实际最大流量_L_min'],
  thermo: B['测压与测温']['油温传感器套管'], orifice: B['阻尼孔螺塞'], rv: B['安全阀孔']['溢流阀设定_MPa'],
  seal: B['安装与密封'],
  // 校核结果
  dvR: get(S, ['每腔死容积_有杆腔_cm3'], 2), dvC: get(S, ['每腔死容积_无杆腔_cm3'], 2),
  bvR: get(S, ['阀块侧_有杆腔_cm3'], 2), bvC: get(S, ['阀块侧_无杆腔_cm3'], 2),
  cadR: get(CAD, ['锁闭容积_CAD', '有杆腔', '扣除插入元件后_cm3'], 2), cadC: get(CAD, ['锁闭容积_CAD', '无杆腔', '扣除插入元件后_cm3'], 2),
  cylV: get(CAD, ['锁闭容积_CAD', '缸体油道_无杆腔_cm3'], 2),
  K5: get(S, ['x70双腔刚度_P5_N_um'], 1), K1: get(S, ['x70双腔刚度_P1基准_N_um'], 1), KH: get(S, ['x70双腔刚度_软管_N_um'], 1),
  Kgain: get(S, ['x70双腔刚度_P5相对软管_%'], 0), Ksens: get(S, ['x70每腔死容积加1cm3双腔刚度变化_N_um'], 3),
  dpBlk: get(S, ['阀块孔道压降_25Lmin_40C_MPa'], 3), dpCyl: get(S, ['缸体油道压降_25Lmin_40C_MPa'], 3), dpTot: get(S, ['合计压降含座阀_25Lmin_40C_MPa'], 2),
  dpAct: get(CJ, ['3_孔道压降', '结果', '40C_实际最大流量_0.94Lmin', '合计_MPa'], 3),
  tmin: get(S, ['最小壁厚_mm'], 1), sf: get(S, ['最小安全系数_设计压力'], 1), bolt: get(S, ['螺栓预紧对分离力倍数'], 1),
  torque: get(CJ, ['5_螺栓与密封', '拧紧力矩_Nm'], 1), squeeze: get(CJ, ['5_螺栓与密封', 'O形圈压缩率_%'], 1), fill: get(CJ, ['5_螺栓与密封', '槽填充率_%'], 1),
  tauS0: get(S, ['套管时间常数_停滞_s', 0], 0), tauS1: get(S, ['套管时间常数_停滞_s', 1], 0),
  tauF0: get(CJ, ['6_套管热响应', '情况', '流动_25Lmin', 'tau_s'], 1), tauF1: get(CJ, ['6_套管热响应', '情况', '流动_0.94Lmin', 'tau_s'], 1),
  dp1T: get(CJ, ['7_锁闭压力升高', '油温每升高1K_p1_MPa'], 3), dp2T: get(CJ, ['7_锁闭压力升高', '油温每升高1K_p2_MPa'], 3),
  p2max: get(CJ, ['7_锁闭压力升高', '有杆腔增压_工件推力消失且R1按最高6.81MPa补压时p2_MPa'], 2),
};
const LK = (case_, x) => CJ['2_锁闭刚度']['工况'][case_][String(x)];
module.exports = { B, CJ, CAD, B1, V, get, LK, ROOT };
