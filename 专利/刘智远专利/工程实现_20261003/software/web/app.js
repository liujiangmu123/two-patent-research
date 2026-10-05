import * as THREE from 'three';
import { OrbitControls } from '/vendor/three/OrbitControls.js';

const $ = id => document.getElementById(id);
let project, selected, view = 'solid', showLabels = true, busy = false;
const color = { good: '#408d85', unknown: '#d49737', fail: '#c55757' };
const viewport = $('viewport');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 10000);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0, 0);
viewport.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
scene.add(new THREE.HemisphereLight(0xf7fbff, 0x73879a, 2.3));
const sun = new THREE.DirectionalLight(0xffffff, 2.1);
sun.position.set(8, -10, 15); scene.add(sun);
const model = new THREE.Group(); scene.add(model);
const splatGroup = new THREE.Group(); scene.add(splatGroup);
const grid = new THREE.GridHelper(12, 24, 0xc0ccd8, 0xd9e2eb);
grid.rotation.x = Math.PI / 2; scene.add(grid);
const ray = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let meshes = [], labels = [], bounds = new THREE.Box3(), centers = [], splatMesh;

function escapeHTML(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function fmt(x, n = 2) { return Number.isFinite(Number(x)) ? Number(x).toFixed(n) : '—'; }
function mm(x) { return fmt(Number(x) * 1000, 2); }
function toast(msg) { $('toast').textContent = msg; $('toast').style.display = 'block'; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').style.display = 'none', 5500); }
function listMembers() { const m = project?.result?.members || []; return Array.isArray(m) ? m : Object.entries(m).map(([id, v]) => ({ id, ...v })); }
function rawMember(m) { return project.case.members.find(x => x.id === m.id) || m; }
function endpoints(m) {
  if (Array.isArray(m.endpoints) && Array.isArray(m.endpoints[0])) return m.endpoints;
  const raw = rawMember(m), nodes = project.case.nodes;
  const ids = raw.nodes || raw.node_ids;
  if (ids) return ids.map(id => Array.isArray(nodes) ? nodes.find(n => n.id === id).position_m : nodes[id]);
  return m.endpoints_m || raw.endpoints;
}
function candidates(m) {
  let c = m.candidates || m.thickness_candidates || [];
  if (c.length && typeof c[0] === 'number') c = c.map((t, i) => ({ thickness_m: t, posterior: m.posterior?.[i] ?? 1 / c.length, utilization: m.utilization?.[i] }));
  return c;
}
function status(m) {
  const s = String(m.status || '');
  if (/ambig|disagree|unresolved|uncertain|unknown|inconsistent|unsupported|invalid|undetermined|unverified|outside|mismatch|insufficient|warning/.test(s)) return 'unknown';
  if (/exceed|fail|mechanism|unstable/.test(s)) return 'fail';
  const kept = candidates(m).filter(c => c.retained !== false);
  const u = kept.flatMap(c => [c.utilization_min, c.utilization_max, c.utilization ?? c.mechanics?.utilization]).map(Number).filter(Number.isFinite);
  if (u.length && Math.min(...u) <= 1 && Math.max(...u) > 1) return 'unknown';
  if (u.length && Math.min(...u) > 1) return 'fail';
  return 'good';
}
function statusText(m) { return ({ outside_candidate_library: '观测厚度超出候选库，需复测或扩库', inconsistent_observations: '测厚记录互相冲突，需复核来源', observation_model_mismatch: '候选均与观测不符，需复核模型', unverified_single_section_input: '只有输入规格，缺少验证证据', local_identifiability_warning: '拟合参数在当前观测下不可辨识', insufficient_fit_degrees_of_freedom: '有效观测不足，不能确认规格', parameter_bound_warning: '拟合触及参数边界，需复核', screening_disagreement: '保留候选导致筛查分歧', input_fixed_section: '按声明来源固定规格，条件筛查', measurement_supported_candidate: '当前观测支持一个候选，条件筛查', geometric_ambiguity_same_screening_decision: '规格仍有歧义，当前条件筛查一致' }[m.status]) || { good: '候选条件判定一致', unknown: '规格或判断待核实', fail: '演示验算超限或结构不稳定' }[status(m)]; }
function disposeGroup(group) { while (group.children.length) { const obj = group.children[0]; group.remove(obj); obj.traverse(c => { c.geometry?.dispose(); if (Array.isArray(c.material)) c.material.forEach(m => m.dispose()); else c.material?.dispose(); }); } }

// Exact non-overlapping L prism. Backend-exported vertices are preferred.
function memberGeometry(m) {
  const geos = project.result.geometry?.members || project.result.geometry || {};
  const entry = m.geometry || (Array.isArray(geos) ? geos.find(g => g.member_id === m.id || g.id === m.id) : geos[m.id]);
  const supplied = entry?.mesh || entry;
  if (supplied?.vertices_m && supplied?.triangles) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(supplied.vertices_m.flat(), 3));
    g.setIndex(supplied.triangles.flat()); g.computeVertexNormals(); return g;
  }
  const raw = rawMember(m), [a, z] = endpoints(m).map(p => new THREE.Vector3(...p));
  const axis = z.clone().sub(a), L = axis.length(); axis.normalize();
  const cs = candidates(m).slice().sort((x, y) => (y.posterior || 0) - (x.posterior || 0));
  const b = cs[0]?.width_m ?? m.width_m ?? m.width ?? raw.width_m;
  const t = cs[0]?.thickness_m ?? raw.thickness_candidates_m[0];
  const c = (b * b * t + t * t * (b - t)) / (2 * (2 * b * t - t * t));
  const points = [[0, 0], [b, 0], [b, t], [t, t], [t, b], [0, b]];
  const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x - c, y - c)));
  const g = new THREE.ExtrudeGeometry(shape, { depth: L, bevelEnabled: false, steps: 1 });
  const ref = new THREE.Vector3(...[0, 1, 2].map(i => i === [0, 1, 2].sort((i, j) => Math.abs(axis.getComponent(i)) - Math.abs(axis.getComponent(j)))[0] ? 1 : 0));
  const x = new THREE.Vector3().crossVectors(ref, axis).normalize();
  const y = new THREE.Vector3().crossVectors(axis, x);
  const ang = cs[0]?.orientation_rad ?? raw.orientation_rad ?? 0;
  const xx = x.clone().multiplyScalar(Math.cos(ang)).addScaledVector(y, Math.sin(ang));
  const yy = y.clone().multiplyScalar(Math.cos(ang)).addScaledVector(x, -Math.sin(ang));
  const matrix = new THREE.Matrix4().makeBasis(xx, yy, axis); matrix.setPosition(a);
  g.applyMatrix4(matrix); return g;
}

function buildModel() {
  disposeGroup(model); meshes = []; labels = []; centers = []; $('canvasLabels').replaceChildren();
  for (const m of listMembers()) {
    const raw = rawMember(m);
    if (raw.exists === false) continue;
    const geometry = memberGeometry(m);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: color[status(m)], roughness: 0.63, metalness: 0.23, side: THREE.DoubleSide }));
    mesh.userData.member = m; model.add(mesh); meshes.push(mesh);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), new THREE.LineBasicMaterial({ color: 0x46627d, transparent: true, opacity: 0.42 }));
    edge.userData.edge = true; model.add(edge);
    const [a, b] = endpoints(m); const center = new THREE.Vector3(...a).add(new THREE.Vector3(...b)).multiplyScalar(0.5);
    const el = document.createElement('span'); el.className = 'canvas-label'; el.textContent = m.id; $('canvasLabels').append(el);
    labels.push({ el, center, id: m.id }); centers.push(center);
  }
  bounds.setFromObject(model); setView(view); updateSelectedMeshes();
}

function resetCamera() {
  if (bounds.isEmpty()) return;
  const c = bounds.getCenter(new THREE.Vector3()), s = bounds.getSize(new THREE.Vector3());
  const radius = Math.max(s.length(), 1);
  camera.position.copy(c).add(new THREE.Vector3(1.1, -1.7, 0.85).multiplyScalar(radius * 0.70));
  controls.target.copy(c); camera.near = Math.max(radius / 1000, 0.001); camera.far = radius * 1000; camera.updateProjectionMatrix(); controls.update();
  grid.scale.setScalar(Math.max(s.x, s.y, 1) / 5); grid.position.z = bounds.min.z - radius * 0.015;
}

async function buildSplats() {
  disposeGroup(splatGroup); splatMesh = null;
  const text = await (await fetch('/export/surface_gaussians.ply')).text();
  const split = text.indexOf('end_header'); if (split < 0 || !text.includes('format ascii')) throw new Error('当前预览接受 ASCII 标准高斯 PLY');
  const head = text.slice(0, split), props = head.split(/\r?\n/).filter(l => l.startsWith('property ')).map(l => l.split(/\s+/).at(-1));
  const rows = text.slice(split + 'end_header'.length).trim().split(/\r?\n/).filter(Boolean);
  if (rows.length > 300000) throw new Error('表面高斯预览上限 30 万个；大场景需分块加载');
  const at = (row, name, fallback = 0) => props.includes(name) ? row[props.indexOf(name)] : fallback;
  const points = rows.map(l => {
    const r = l.trim().split(/\s+/).map(Number);
    return { center: new THREE.Vector3(at(r, 'x'), at(r, 'y'), at(r, 'z')),
      scales: [Math.exp(at(r, 'scale_0', -4)), Math.exp(at(r, 'scale_1', -4))],
      rotation: [at(r, 'rot_1'), at(r, 'rot_2'), at(r, 'rot_3'), at(r, 'rot_0', 1)],
      rgba: [0, 1, 2].map(i => Math.min(1, Math.max(0, 0.5 + 0.2820947918 * at(r, 'f_dc_' + i)))).concat(1 / (1 + Math.exp(-at(r, 'opacity', 2)))) };
  });
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute([-3,-3,0, 3,-3,0, 3,3,0, -3,3,0], 3));
  g.setIndex([0,1,2,0,2,3]);
  g.setAttribute('center', new THREE.InstancedBufferAttribute(new Float32Array(points.length * 3), 3));
  g.setAttribute('size', new THREE.InstancedBufferAttribute(new Float32Array(points.length * 2), 2));
  g.setAttribute('rotation', new THREE.InstancedBufferAttribute(new Float32Array(points.length * 4), 4));
  g.setAttribute('rgba', new THREE.InstancedBufferAttribute(new Float32Array(points.length * 4), 4));
  g.instanceCount = points.length;
  const material = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide,
    vertexShader: `attribute vec3 center; attribute vec2 size; attribute vec4 rotation; attribute vec4 rgba; varying vec2 gaussianXY; varying vec4 splatColor;
    vec3 qrot(vec4 q, vec3 v){return v+2.0*cross(q.xyz,cross(q.xyz,v)+q.w*v);} void main(){gaussianXY=position.xy;splatColor=rgba;vec3 p=center+qrot(rotation,vec3(position.xy*size,0.0));gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);}`,
    fragmentShader: `varying vec2 gaussianXY; varying vec4 splatColor; void main(){float alpha=splatColor.a*exp(-0.5*dot(gaussianXY,gaussianXY));if(alpha<0.015)discard;gl_FragColor=vec4(splatColor.rgb,alpha);}` });
  splatMesh = new THREE.Mesh(g, material); splatMesh.frustumCulled = false; splatMesh.userData.points = points; splatGroup.add(splatMesh);
  sortSplats(); setView(view);
}
let lastSortPosition = new THREE.Vector3(Infinity, Infinity, Infinity), lastSortDirection = new THREE.Vector3();
function sortSplats() {
  if (!splatMesh) return;
  const dir = camera.getWorldDirection(new THREE.Vector3());
  if (camera.position.distanceToSquared(lastSortPosition) < 0.00001 && dir.distanceToSquared(lastSortDirection) < 0.00001) return;
  lastSortPosition.copy(camera.position); lastSortDirection.copy(dir);
  const points = splatMesh.userData.points.slice().sort((a, b) => b.center.clone().sub(camera.position).dot(dir) - a.center.clone().sub(camera.position).dot(dir));
  const g = splatMesh.geometry;
  points.forEach((p, i) => { g.attributes.center.setXYZ(i, ...p.center.toArray()); g.attributes.size.setXY(i, ...p.scales); g.attributes.rotation.setXYZW(i, ...p.rotation); g.attributes.rgba.setXYZW(i, ...p.rgba); });
  Object.values(g.attributes).forEach(a => { a.needsUpdate = true; });
}

function setView(next) {
  view = next; document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === next));
  splatGroup.visible = next === 'gaussian';
  for (const mesh of meshes) { mesh.material.visible = next === 'solid'; }
  model.children.filter(c => c.userData.edge).forEach(e => { e.visible = next !== 'gaussian'; e.material.opacity = next === 'wire' ? 0.85 : 0.36; });
  $('viewTitle').textContent = next === 'gaussian' ? '参数化表面高斯' : next === 'wire' ? '共享节点与角钢边界' : '共享节点角钢模型';
  $('viewSubtitle').textContent = next === 'gaussian' ? '工程参数生成的有限厚度表面 · 尚未训练真实照片外观' : '拖动旋转 · 滚轮缩放 · 点击杆件查看依据';
}
function updateSelectedMeshes() { meshes.forEach(mesh => { mesh.material.emissive.set(mesh.userData.member.id === selected ? '#365a70' : '#000000'); mesh.material.emissiveIntensity = 0.3; }); labels.forEach(l => l.el.classList.toggle('selected', l.id === selected)); }

function renderList() {
  const query = $('memberSearch').value.toLowerCase();
  const members = listMembers().filter(m => m.id.toLowerCase().includes(query));
  $('listCount').textContent = members.length + ' 项';
  $('memberList').innerHTML = members.map(m => `<button class="member-row ${m.id === selected ? 'active' : ''}" data-member="${escapeHTML(m.id)}"><span class="name"><i class="dot" style="background:${color[status(m)]}"></i>${escapeHTML(m.id)}</span><span class="status-label">${status(m) === 'unknown' ? '待核实' : status(m) === 'fail' ? '超限/异常' : '一致'}</span></button>`).join('');
  $('memberList').querySelectorAll('[data-member]').forEach(b => b.onclick = () => select(b.dataset.member));
}
function select(id) {
  selected = id; renderList(); updateSelectedMeshes();
  const m = listMembers().find(m => m.id === id); if (!m) return;
  const raw = rawMember(m), [a, b] = endpoints(m);
  $('selectedId').textContent = id; $('selectedStatus').textContent = statusText(m);
  const cands = candidates(m);
  $('memberDetails').innerHTML = `<div class="detail-grid"><div class="detail-cell"><span>肢宽</span><strong>${mm(m.width_m ?? m.width ?? raw.width_m)} mm</strong></div><div class="detail-cell"><span>杆长</span><strong>${fmt(new THREE.Vector3(...a).distanceTo(new THREE.Vector3(...b)), 3)} m</strong></div><div class="detail-cell"><span>保留规格</span><strong>${cands.filter(c => c.retained !== false).length}</strong></div><div class="detail-cell"><span>存在状态</span><strong>${raw.exists === false ? '缺材记录' : '输入存在'}</strong></div></div><h3>截面候选与演示验算</h3>` + cands.map(c => {
    const p = c.likelihood_probability ?? c.posterior ?? c.probability ?? 0, post = c.probability ?? c.posterior ?? p, prior = c.prior_probability ?? 0, u = c.utilization_max ?? c.utilization ?? c.mechanics?.utilization;
    const range = c.utilization_min !== undefined && c.utilization_max !== undefined && Math.abs(c.utilization_min - c.utilization_max) > 0.0001 ? `${fmt(c.utilization_min,3)}—${fmt(c.utilization_max,3)}` : fmt(u,3);
    return `<div class="candidate"><div class="candidate-top"><strong>${mm(c.width_m ?? raw.width_m)} × ${mm(c.thickness_m)} mm</strong><span>观测权重 ${fmt(p * 100, 1)}%</span></div><div class="bar"><i style="width:${Math.max(0, Math.min(100, p * 100))}%"></i></div><p>演示利用率 ${range} ${Number(u) > 1 ? '· 超过阈值' : Number.isFinite(Number(u)) ? '· 未超过阈值' : '· 无可用结果'}</p><p>${c.absolute_fit_consistent === false ? '绝对拟合未通过 · ' : ''}${c.retained === false ? '当前候选未保留' : '当前候选保留'} · χ² ${fmt(c.chi_square,2)}</p><p>先验 ${fmt(prior * 100,1)}% · 合并权重 ${fmt(post * 100,1)}%<br>权重仅用于条件比较，不是安全概率</p></div>`;
  }).join('');
  $('thicknessForm').querySelector('button').disabled = busy || raw.exists === false;
  renderActions();
}
function renderActions() {
  const actions = (project.result.actions || []).filter(a => a.member_id === selected || !a.member_id);
  const name = kind => ({ thickness: '现场测厚', direct_thickness: '现场测厚', remote: '远程视点', image: '补拍影像', image_edge_gap: '补拍截面边缘', lidar: '补扫激光', lidar_edge_gap: '补扫截面边缘', optical_lidar: '影像 / 激光补测', verify_section_assumption: '核实输入规格来源', expand_candidate_library_and_review_measurement: '复测与扩展候选库', review_observation_model_and_repeat_measurement: '复核模型与测量来源' }[kind] || kind);
  $('actionList').innerHTML = actions.length ? actions.map(a => {
    const noDisagreement = String(a.reason).startsWith('No retained');
    const d = a.separation_sigma ?? a.separation_score ?? 0;
    const review = a.required_separation_sigma === undefined;
    const coverage = a.unseparated_pair_count > 0 ? `仍有 ${a.unseparated_pair_count} 个联合候选分歧对未分离，需要后续动作。` : a.resolves_all_current_pairs ? '可分离当前全部分歧对。' : '';
    const reason = review ? '现有观测或规格来源不足以确认结果。请核实标定、杆件关联、噪声与候选范围，冲突测量需复测。' : noDisagreement ? '保留候选的演示判定一致，无需为该分歧增加测量。' : `预测差异 ${fmt(d,2)} σ，区分阈值 ${fmt(a.required_separation_sigma ?? 3,1)} σ。${a.effective ? '可分离部分或全部当前分歧对。' : '分辨率或噪声不足，需要其他测量方式。'}${coverage}`;
    return `<div class="action-card ${a.effective ? 'valid' : 'invalid'}"><strong>${escapeHTML(name(a.kind))} · ${escapeHTML(a.member_id || a.member || '')}</strong><p>${escapeHTML(reason)}</p><span class="tag">${review ? '需要人工复核' : noDisagreement ? '当前无此分歧' : a.effective ? '有区分能力' : '当前条件无效'}${review ? '' : ' · 分离度 ' + fmt(d, 2)}</span></div>`;
  }).join('') : '<div class="action-card"><strong>当前没有补测动作</strong><p>请查看候选结果和计算范围。无补测动作不代表已经完成全部工程验算。</p></div>';
}
async function accept(data, reset = false) {
  project = data;
  const members = listMembers();
  if (!members.some(m => m.id === selected)) selected = members.find(m => status(m) === 'unknown')?.id || members[0]?.id;
  $('projectName').textContent = project.case.synthetic ? '角钢截面与测厚演示' : project.case.name || project.case.project_name || '角钢桁架项目';
  $('projectNote').textContent = project.case.description || '输入标定观测，保留规格歧义，选择有效补测。';
  $('modeBadge').textContent = project.case.synthetic === true ? '工程原型 · 合成演示' : '工程原型 · 导入数据';
  const decision = project.result.engineering_decision, pairs = project.result.unresolved_joint_pair_count || 0;
  $('decisionBanner').innerHTML = `<strong>${decision === 'report_conditionally' ? '可输出条件筛查报告' : '工程结论未决'}</strong><p>${pairs ? `存在 ${pairs} 个联合候选分歧对。` : ''}${decision === 'report_conditionally' ? '仅适用于声明的几何、材料、荷载与简化桁架模型。' : '查看候选证据与复核任务，不能据此确认工程结论。'}完整规范验算尚未实现。</p>`;
  $('memberCount').textContent = members.length; $('ambiguousCount').textContent = members.filter(m => status(m) === 'unknown').length; $('measurementCount').textContent = project.case.measurements?.length || 0;
  $('solverInfo').textContent = typeof project.result.solver === 'string' ? project.result.solver : JSON.stringify(project.result.solver || {}, null, 2);
  buildModel(); renderList(); select(selected); renderActions(); if (reset) resetCamera();
  $('loading').style.display = 'none';
  try { lastSortPosition.set(Infinity, Infinity, Infinity); await buildSplats(); } catch (e) { toast('高斯预览：' + e.message); }
}
async function request(path, body) {
  busy = true; document.querySelectorAll('button.primary').forEach(b => b.disabled = true);
  try { const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || '计算失败'); return data; }
  finally { busy = false; document.querySelectorAll('button.primary').forEach(b => b.disabled = false); }
}
function resize() { const w = viewport.clientWidth, h = viewport.clientHeight; camera.aspect = w / Math.max(h, 1); camera.updateProjectionMatrix(); renderer.setSize(w, h); }
new ResizeObserver(resize).observe(viewport);
function animate() { requestAnimationFrame(animate); controls.update(); if (view === 'gaussian') sortSplats(); renderer.render(scene, camera); for (const l of labels) { const p = l.center.clone().project(camera); l.el.style.display = showLabels && p.z < 1 && p.z > -1 && Math.abs(p.x) < 1 && Math.abs(p.y) < 1 ? '' : 'none'; l.el.style.left = `${(p.x + 1) / 2 * viewport.clientWidth}px`; l.el.style.top = `${(1 - p.y) / 2 * viewport.clientHeight}px`; } }
animate();
let down;
renderer.domElement.addEventListener('pointerdown', e => down = [e.clientX, e.clientY]);
renderer.domElement.addEventListener('pointerup', e => { if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return; const r = renderer.domElement.getBoundingClientRect(); pointer.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1); ray.setFromCamera(pointer, camera); const hit = ray.intersectObjects(meshes).find(x => x.object.userData.member); if (hit) select(hit.object.userData.member.id); });
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => setView(b.dataset.view));
$('resetView').onclick = resetCamera;
$('showLabels').onclick = () => { showLabels = !showLabels; $('showLabels').setAttribute('aria-pressed', String(showLabels)); };
$('memberSearch').oninput = renderList;
$('resetDemo').onclick = async () => { try { await accept(await request('/api/demo', {}), true); toast('已恢复远程观测演示，尚未输入测厚'); } catch (e) { toast(e.message); } };
$('thicknessForm').onsubmit = async e => { e.preventDefault(); if (!selected) return; try { await accept(await request('/api/measurement', { measurement: { measurement_id: $('measurementId').value.trim(), kind: 'thickness', member_id: selected, value_m: Number($('thicknessValue').value) / 1000, sigma_m: Number($('thicknessSigma').value) / 1000 } })); toast('测厚记录已回灌，候选与验算已更新'); } catch (e) { toast(e.message); } };
$('exportButton').onclick = () => { const a = document.createElement('a'); a.href = '/export/result.json'; a.download = 'TrussTwin_result.json'; a.click(); };
$('importButton').onclick = () => { $('jsonInput').value = JSON.stringify(project.case, null, 2); $('importError').textContent = ''; $('importDialog').showModal(); };
$('closeDialog').onclick = () => $('importDialog').close();
$('chooseFile').onclick = () => $('fileInput').click();
$('fileInput').onchange = async () => { const f = $('fileInput').files[0]; if (!f) return; if (f.size > 4 * 1024 * 1024) { $('importError').textContent = '文件超过 4 MiB'; return; } $('jsonInput').value = await f.text(); };
$('runImport').onclick = async () => { try { const input = JSON.parse($('jsonInput').value); await accept(await request('/api/run', { case: input }), true); $('importDialog').close(); toast('项目已导入并完成原型计算'); } catch (e) { $('importError').textContent = e.message; } };
try { const response = await fetch('/api/project'); if (!response.ok) throw new Error('服务未返回项目'); await accept(await response.json(), true); } catch (e) { $('loading').textContent = '载入失败：' + e.message; toast(e.message); }
