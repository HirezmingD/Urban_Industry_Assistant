/**
 * Urban_Industry_Assistant — 前端交互逻辑 (V1.2)
 * 纯 vanilla JS，Leaflet 地图 + Chart.js 雷达图 + 对话/企业/自进化面板
 * V1.2: 九宫格预加载 + 点选 sticky note
 */

// ===== 1. 全局配置 =====
const API_BASE = '';
let TIANDITU_KEY = '';
const TONGLU_BBOX = [119.16, 29.58, 119.80, 30.12];

// 用地类型 → 颜色映射
const LAND_COLORS = {
  '商业用地': '#f0883e', '商业服务业设施用地': '#f0883e',
  '工业用地': '#f0883e', '物流仓储用地': '#f0883e', '产业用地': '#f0883e',
  '城镇住宅用地': '#ffdd57', '农村宅基地': '#ffdd57', '居住用地': '#ffdd57',
  '水田': '#7ecb76', '旱地': '#7ecb76', '果园': '#7ecb76', '茶园': '#7ecb76', '农用地': '#7ecb76',
  '乔木林地': '#2d8a4e', '竹林地': '#2d8a4e', '灌木林地': '#2d8a4e', '林地': '#2d8a4e',
  '河流水面': '#58a6ff', '水库水面': '#58a6ff', '坑塘水面': '#58a6ff', '水域': '#58a6ff',
  '公路用地': '#8b949e', '铁路用地': '#8b949e', '交通用地': '#8b949e',
  '机关团体新闻出版用地': '#bc8cff', '科教文卫用地': '#bc8cff', '公服用地': '#bc8cff',
};
function getLandColor(lt) { return LAND_COLORS[lt] || '#6e7681'; }

// ===== 2. 状态管理 =====
const state = {
  role: 'government',
  currentBbox: null,
  selectedEnterpriseIds: [],
  candidateGrids: [],
  chatHistory: [],
  gridLightLayer: null,
  highlightLayer: null,
  candidateLayer: null,
  drawControl: null,
  drawnRect: null,
  evolutionTimer: null,
  radarChart: null,
};
let map, stickyNote;
let _lastQueryTs = 0;

// ===== 3. Config 加载 =====
async function loadConfig() {
  try {
    const r = await fetch(API_BASE + '/api/config');
    const data = await r.json();
    TIANDITU_KEY = data.tianditu_key || '';
  } catch {}
}

// ===== 4. 地图初始化 =====
function initMap() {
  map = L.map('map', {
    center: [29.795, 119.685], zoom: 12, minZoom: 11, maxZoom: 18,
    zoomControl: true,
    maxBounds: [[TONGLU_BBOX[1], TONGLU_BBOX[0]], [TONGLU_BBOX[3], TONGLU_BBOX[2]]],
  });
  if (TIANDITU_KEY) {
    const tileUrl = `http://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_KEY}`;
    L.tileLayer(tileUrl, { subdomains: ['0','1','2','3','4','5','6','7'], minZoom: 10, maxZoom: 18, errorTileUrl: '/data/tiles/{z}/{x}/{y}.png' }).addTo(map);
    const lblUrl = `http://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_KEY}`;
    L.tileLayer(lblUrl, { subdomains: ['0','1','2','3','4','5','6','7'], minZoom: 10, maxZoom: 18 }).addTo(map);
  }
  setupDrawControl();
  setupMouseInteraction();
}

// ---- Box Selection ----
function setupDrawControl() {
  state.drawControl = new L.Control.Draw({ draw: { rectangle: { shapeOptions: { color: '#f0883e', weight: 2 } }, polygon: false, polyline: false, circle: false, marker: false, circlemarker: false }, edit: false });
  map.addControl(state.drawControl);
  map.on('draw:drawstart', () => {
    if (state.drawnRect) { map.removeLayer(state.drawnRect); state.drawnRect = null; state.currentBbox = null; }
    if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; }
    state.candidateGrids = []; document.getElementById('chat-info-bar').classList.add('hidden');
  });
  map.on(L.Draw.Event.CREATED, (e) => {
    if (state.drawnRect) map.removeLayer(state.drawnRect);
    state.drawnRect = e.layer; map.addLayer(e.layer);
    const b = e.layer.getBounds();
    state.currentBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    handleBboxQuery(state.currentBbox);
  });
}

async function handleBboxQuery(bbox) {
  const infoBar = document.getElementById('chat-info-bar'), infoText = document.getElementById('chat-info-text');
  infoBar.classList.remove('hidden'); infoText.textContent = '正在查询...';
  try {
    const z = map.getZoom();
    const r = await fetch(`${API_BASE}/api/map/query?bbox=${bbox}&zoom=${z}&role=${state.role}`);
    if (!r.ok) { infoText.textContent = '查询失败'; return; }
    const data = await r.json();
    infoText.textContent = `已选择 ${data.grid_count} 个网格，总面积 ${data.total_area_mu} 亩`;
    if (data.geojson && data.geojson.features) {
      renderBboxHighlight(data.geojson);
      state.candidateGrids = data.features.map(f => f.grid_id).filter(Boolean);
    } else { infoText.textContent += '（渔网数据未就绪）'; }
    switchTab('chat');
  } catch { infoText.textContent = '查询异常'; }
}
function renderBboxHighlight(geojson) {
  if (state.candidateLayer) map.removeLayer(state.candidateLayer);
  state.candidateLayer = L.geoJSON(geojson, { style: { color: '#f0883e', weight: 1, fillOpacity: 0.3, fillColor: '#f0883e' } }).addTo(map);
}

// ---- Mouse Interaction (V1.2: preload + HTTP fallback) ----
function setupMouseInteraction() {
  map.on('mousemove', (e) => {
    if (state.role !== 'government') return;
    const now = Date.now();
    if (now - _lastQueryTs < 200) return;
    _lastQueryTs = now;
    const { lat, lng } = e.latlng;
    const zoom = map.getZoom();
    fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
      .then(r => r.json())
      .then(cells => {
        if (!cells || cells.length === 0) return;
        renderSingleGrid(cells[0]);
      })
      .catch(() => {});
  });

  map.on('mouseout', () => {
    if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; }
  });

  map.on('click', async (e) => {
    if (state.role !== 'government') return;
    const { lat, lng } = e.latlng;
    const zoom = map.getZoom();
    let gridId;
    try {
      const cells = await (await fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)).json();
      gridId = cells[0]?.grid_id;
    } catch {}
    if (!gridId) { stickyNote.hide(); return; }
    try {
      const r = await fetch(`${API_BASE}/api/map/grid/${gridId}?role=government`);
      if (!r.ok) return;
      const data = await r.json();
      data.level = [11,12,13,14,15].reduce((a,z,i) => zoom<=z?i+1:a, 0);
      const point = map.latLngToContainerPoint(e.latlng);
      stickyNote.toggle(data, point);
    } catch {}
  });
}

function renderSingleGrid(cell) {
  if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; }
  if (!cell || !cell.coords) return;
  state.highlightLayer = L.geoJSON({
    type: 'Feature',
    properties: { grid_id: cell.grid_id },
    geometry: { type: 'Polygon', coordinates: cell.coords },
  }, {
    style: {
      fillOpacity: 0.45,
      fillColor: getLandColor(cell.land_type || ''),
      color: getLandColor(cell.land_type || ''),
      weight: 2,
    },
  }).addTo(map);
}

// ===== 5. 渔网精简 =====
async function loadGridLight() {
  try {
    const r = await fetch('/static/grid_light.geojson');
    if (!r.ok) throw new Error();
    const data = await r.json();
    if (!data.features || data.features.length === 0) {
      document.getElementById('health-badge').textContent = '●  渔网未就绪';
      document.getElementById('health-badge').className = 'health-badge degraded';
      return;
    }
    state.gridLightLayer = L.geoJSON(data, { style: (f) => ({ color: getLandColor(f.properties.land_type), weight: 0.5, fillOpacity: 0.25, fillColor: getLandColor(f.properties.land_type) }) });
    map.on('zoomend', () => { const z = map.getZoom(); if (z >= 13 && !map.hasLayer(state.gridLightLayer)) map.addLayer(state.gridLightLayer); else if (z < 13 && map.hasLayer(state.gridLightLayer)) map.removeLayer(state.gridLightLayer); });
    if (map.getZoom() >= 13) map.addLayer(state.gridLightLayer);
  } catch { document.getElementById('health-badge').textContent = '●  渔网未就绪'; document.getElementById('health-badge').className = 'health-badge degraded'; }
}

// ===== 6. Tab 切换 =====
function setupTabs() { document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab))); }
function switchTab(name) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tabs button[data-tab="${name}"]`).classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
  if (name === 'evolution') { loadEvolutionStats(); startEvolutionPolling(); } else { stopEvolutionPolling(); }
}

// ===== 7. 角色切换 =====
function setupRoleSwitch() {
  document.getElementById('btn-gov').addEventListener('click', () => setRole('government'));
  document.getElementById('btn-ent').addEventListener('click', () => setRole('enterprise'));
}
function setRole(role) {
  state.role = role; document.getElementById('btn-gov').classList.toggle('active', role === 'government'); document.getElementById('btn-ent').classList.toggle('active', role === 'enterprise');
  if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; } state.candidateGrids = []; state.currentBbox = null;
  document.getElementById('ent-match-btn').disabled = role === 'enterprise'; updateMatchButton();
  loadEvolutionStats();
}

// ===== 8. 对话 =====
function setupChat() { document.getElementById('chat-send').addEventListener('click', sendChat); document.getElementById('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); }); }
async function sendChat() {
  const input = document.getElementById('chat-input'); const msg = input.value.trim(); if (!msg) return; input.value = '';
  appendChatMessage('user', msg); state.chatHistory.push({ role: 'user', content: msg });
  const loadingId = appendChatMessage('assistant', '<span class="loading">评估中...</span>');
  try {
    const r = await fetch(`${API_BASE}/api/agent/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg, role: state.role, bbox: state.currentBbox || null, context: state.chatHistory.slice(-10) }) });
    const data = await r.json();
    const md = document.getElementById(loadingId); if (md) md.remove();
    renderAgentReply(data); state.chatHistory.push({ role: 'assistant', content: JSON.stringify(data) });
    if (data.candidate_grids && data.candidate_grids.length > 0) highlightCandidates(data.candidate_grids);
  } catch { const md = document.getElementById(loadingId); if (md) md.innerHTML = '⚠️ 请求失败，请重试'; }
}
function appendChatMessage(role, content) { const d = document.createElement('div'); d.className = `chat-msg ${role}`; d.id = 'msg-' + Date.now(); d.innerHTML = typeof content === 'string' ? content : ''; document.getElementById('chat-messages').appendChild(d); d.scrollIntoView({ behavior: 'smooth' }); return d.id; }
function renderAgentReply(data) {
  const d = document.createElement('div'); d.className = 'chat-msg assistant agent-reply';
  let h = '';
  if (typeof data.summary === 'string') h += `<p>${escapeHtml(data.summary)}</p>`;
  if (data.items) data.items.forEach(item => { h += `<div class="item"><span class="rank">#${item.rank}</span> <b>${escapeHtml(item.industry||'')}</b> <span class="score">${item.score||0}/10</span><p>${escapeHtml(item.reason||'')}</p>`;
    if (item.policy_refs && item.policy_refs.length) h += `<div class="policy-cite">📜 ${item.policy_refs.map(escapeHtml).join('；')}</div>`;
    if (item.risk) h += `<div class="risk">⚠️ ${escapeHtml(item.risk)}</div>`; h += '</div>'; });
  if (data.risks && data.risks.length) h += '<div class="risks-block">⚠️ 风险提示：' + data.risks.map(escapeHtml).join('；') + '</div>';
  d.innerHTML = h; document.getElementById('chat-messages').appendChild(d); d.scrollIntoView({ behavior: 'smooth' });
}
function escapeHtml(str) { if (!str) return ''; const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
function highlightCandidates(gridIds) { if (!gridIds || gridIds.length === 0) return; /* TODO: backend-side geojson */ }

// ===== 9. 企业列表 =====
async function loadEnterprises(search = '') {
  const list = document.getElementById('ent-list'); list.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const url = search ? `${API_BASE}/api/enterprise/list?search=${encodeURIComponent(search)}` : `${API_BASE}/api/enterprise/list`;
    const data = await (await fetch(url)).json();
    if (data.length === 0) { list.innerHTML = '<div class="loading">无匹配企业</div>'; return; }
    list.innerHTML = ''; data.forEach(ent => {
      const div = document.createElement('div'); div.className = 'ent-item';
      const tags = (ent.priority_tags || []).map(t => `<span class="ent-tag">${escapeHtml(t)}</span>`).join('');
      div.innerHTML = `<input type="checkbox" data-eid="${ent.id}" ${state.selectedEnterpriseIds.includes(ent.id)?'checked':''}><div><div class="ent-name">${escapeHtml(ent.name)}</div><div class="ent-meta">${escapeHtml(ent.industry||'')} | 年营收 ${escapeHtml(ent.annual_revenue||'-')}</div></div><div class="ent-tags">${tags}</div>`;
      div.querySelector('input').addEventListener('change', (e) => { const eid = e.target.dataset.eid; if (e.target.checked) { if (!state.selectedEnterpriseIds.includes(eid)) state.selectedEnterpriseIds.push(eid); } else { state.selectedEnterpriseIds = state.selectedEnterpriseIds.filter(id => id !== eid); } updateMatchButton(); });
      list.appendChild(div);
    });
  } catch { list.innerHTML = '<div class="loading">加载失败</div>'; }
}
function updateMatchButton() { const b = document.getElementById('ent-match-btn'); const n = state.selectedEnterpriseIds.length; b.disabled = state.role === 'enterprise' || n === 0; b.textContent = state.role === 'enterprise' ? '仅政府端可用' : `匹配选中企业（${n} 家）`; }
async function triggerMatch() {
  if (state.selectedEnterpriseIds.length === 0) return; const btn = document.getElementById('ent-match-btn'); btn.disabled = true; btn.textContent = '匹配中...';
  try {
    const data = await (await fetch(`${API_BASE}/api/enterprise/match`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enterprise_ids: state.selectedEnterpriseIds, role: 'government' }) })).json();
    switchTab('chat'); appendChatMessage('assistant', `🏭 企业匹配结果（${data.length} 家）：`);
    data.forEach(m => { let info = `<b>${escapeHtml(m.enterprise_name)}</b><br>`; if (m.candidates) m.candidates.forEach(c => { info += `  候选: 面积 ${c.area_mu?.toFixed(0)||'-'} 亩，评分 ${c.score}<br>${escapeHtml(c.reason||'')}<br>`; }); appendChatMessage('assistant', info); });
    const allGrids = data.flatMap(m => (m.candidates || []).flatMap(c => c.grid_ids || [])); if (allGrids.length > 0) highlightCandidates(allGrids);
  } catch { appendChatMessage('assistant', '⚠️ 匹配请求失败'); } finally { btn.disabled = false; updateMatchButton(); }
}

// ===== 10. 自进化 =====
async function loadEvolutionStats() {
  try {
    const data = await (await fetch(`${API_BASE}/api/evomap/status`)).json(); state.evolutionStats = data;
    document.getElementById('evo-experience').textContent = `📊 本次评估已学习 ${data.evolution_count} 次历史决策经验`;
    document.getElementById('evo-methodology').textContent = `🧬 已遗传/共享的评估方法论：${data.capsules_published||0} 条`;
    document.getElementById('evo-capsules').textContent = `📦 已为集体智能贡献 ${data.capsules_published||0} 条经验`;
    document.getElementById('evo-pref-fill').style.width = (data.preference_understanding||0) + '%';
    document.getElementById('evo-pref-label').textContent = (data.preference_understanding||0) + '%';
    renderRadarChart(data.radar_values || {});
  } catch {}
}
function renderRadarChart(values) {
  const ctx = document.getElementById('radar-chart').getContext('2d'); if (state.radarChart) state.radarChart.destroy();
  const labels = ['产业匹配','政策理解','空间分析','风险识别','企业匹配'];
  state.radarChart = new Chart(ctx, { type: 'radar', data: { labels, datasets: [{ label: '能力雷达', data: labels.map(l => values[l]||30), backgroundColor: 'rgba(88,166,255,0.2)', borderColor: '#58a6ff', borderWidth: 2, pointBackgroundColor: '#58a6ff', pointBorderColor: '#fff', pointRadius: 4 }] }, options: { responsive: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 20, color: '#8b949e', backdropColor: 'transparent' }, pointLabels: { color: '#e6edf3', font: { size: 11 } }, grid: { color: '#30363d' }, angleLines: { color: '#30363d' } } }, plugins: { legend: { display: false } } } });
}
function startEvolutionPolling() { stopEvolutionPolling(); state.evolutionTimer = setInterval(loadEvolutionStats, 60000); }
function stopEvolutionPolling() { if (state.evolutionTimer) { clearInterval(state.evolutionTimer); state.evolutionTimer = null; } }

// ===== 11. 健康检查 =====
function pollHealth() {
  fetch(`${API_BASE}/health`).then(r => r.json()).then(data => {
    const b = document.getElementById('health-badge');
    if (data.status === 'ok') { b.textContent = data.evomap_online ? '●  在线' : '●  EvoMap 离线'; b.className = 'health-badge ' + (data.evomap_online ? 'online' : 'degraded'); }
    else { b.textContent = '●  服务降级'; b.className = 'health-badge degraded'; }
  }).catch(() => { const b = document.getElementById('health-badge'); b.textContent = '●  服务异常'; b.className = 'health-badge error'; });
} setInterval(pollHealth, 30000);

// ===== 12. StickyNote — 光标旁即时贴 =====
class StickyNote {
  constructor(mapContainerId) {
    this.container = document.getElementById(mapContainerId); this.el = document.getElementById('sticky-note');
    this.arrow = this.el.querySelector('.sticky-arrow'); this.currentGridId = null; this._bindEvents();
  }
  show(gridData, clickPoint) {
    const { x, y } = clickPoint, cw = this.container.clientWidth, ch = this.container.clientHeight;
    const nw = 280, m = 12, nh = Math.min(320, ch - y - m - 20);
    const hasRight = (x + nw + m) <= cw, hasBottom = (y + nh + m) <= ch;
    let left, top, arrowDir;
    if (hasRight && hasBottom) { left = x + m; top = y + m; arrowDir = 'top-left'; }
    else if (!hasRight && hasBottom) { left = x - nw - m; top = y + m; arrowDir = 'top-right'; }
    else if (hasRight && !hasBottom) { left = x + m; top = y - m; arrowDir = 'bottom-left'; }
    else { left = x - nw - m; top = y - m; arrowDir = 'bottom-right'; }
    left = Math.max(4, Math.min(left, cw - nw - 4)); top = Math.max(4, top);
    this.el.style.left = left + 'px'; this.el.style.top = top + 'px';
    this.arrow.className = `sticky-arrow sticky-arrow--${arrowDir}`;
    if (arrowDir.startsWith('bottom')) { this.el.style.top = 'auto'; this.el.style.bottom = (ch - y + m) + 'px'; } else { this.el.style.bottom = 'auto'; }
    this._renderContent(gridData); this.currentGridId = gridData.grid_id;
    this.el.querySelector('.sticky-grid-id').textContent = '📋 ' + gridData.grid_id;
    this.el.classList.remove('hidden'); requestAnimationFrame(() => this.el.classList.add('visible'));
  }
  hide() { this.el.classList.remove('visible'); this.el.classList.add('hidden'); this.currentGridId = null; }
  toggle(gridData, clickPoint) { if (this.currentGridId === gridData.grid_id) this.hide(); else this.show(gridData, clickPoint); }
  _renderContent(data) {
    const body = this.el.querySelector('#sticky-body'); const isAgg = data.level > 0;
    const rows = [
      { label: '用地类型', value: data.land_type || '—' },
      { label: '面积', value: `${(data.area_mu||0).toFixed(1)} 亩` },
      { label: '权属', value: isAgg ? this._fmtOwn(data.ownership) : (data.ownership||'—') },
      { label: '乡镇', value: data.town || '—' },
      { label: '混合用地', value: data.mixed_type || '纯用地' },
    ];
    let top3Html = ''; if (isAgg && data.land_type_top3) { try { const t3 = JSON.parse(data.land_type_top3); if (t3.length) top3Html = `<div class="sticky-top3" id="sticky-top3-toggle"><span class="top3-trigger">📊 地类占比 ▼</span><div class="top3-list hidden" id="sticky-top3-list">${t3.map(t => `<span class="top3-item">${t.name} ${(t.pct*100).toFixed(1)}%</span>`).join('')}</div></div>`; } catch {} }
    let cntH = ''; if (isAgg && data.grid_count_original) cntH = `<div class="sticky-row"><span class="sticky-label">原始网格</span><span class="sticky-value">${data.grid_count_original} 个</span></div>`;
    body.innerHTML = rows.filter(r => r.value).map(r => `<div class="sticky-row"><span class="sticky-label">${r.label}</span><span class="sticky-value">${escapeHtml(String(r.value))}</span></div>`).join('') + cntH + top3Html;
    if (isAgg) { const tg = document.getElementById('sticky-top3-toggle'); if (tg) tg.addEventListener('click', () => { document.getElementById('sticky-top3-list').classList.toggle('hidden'); }); }
    document.getElementById('sticky-eval-btn').style.display = state.role === 'government' ? 'block' : 'none';
  }
  _fmtOwn(json) { try { const o = JSON.parse(json); return Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,2).map(([k,v])=>`${k} ${(v*100).toFixed(0)}%`).join(' / '); } catch { return json||'—'; } }
  _bindEvents() {
    this.el.querySelector('.sticky-close').addEventListener('click', () => this.hide());
    this.el.querySelector('#sticky-eval-btn').addEventListener('click', () => {
      const msg = '评估网格 ' + this.currentGridId;
      const input = document.getElementById('chat-input');
      if (input) input.value = msg;
      this.hide();
      switchTab('chat');
      document.getElementById('chat-send')?.click();
    });
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') this.hide(); });
  }
}

// ===== 14. 启动 =====
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig(); pollHealth();
  initMap(); loadGridLight().catch(() => {});
  stickyNote = new StickyNote('map');
  map.on('zoomend', () => { if (state.currentBbox) handleBboxQuery(state.currentBbox); });
  setupTabs(); setupChat(); setupRoleSwitch();
  loadEnterprises(); document.getElementById('ent-search').addEventListener('input', (e) => loadEnterprises(e.target.value));
  document.getElementById('ent-match-btn').addEventListener('click', triggerMatch);
  loadEvolutionStats();
});
