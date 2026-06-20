/**
 * Urban_Industry_Assistant — 前端交互逻辑 (V2.0)
 * CSS Grid 三栏双角色布局 + 浅色政企主题
 * 保留所有 V1.2 功能，新增企业端表单、EvoMap 双文案、输入源迁移
 */
// ===== 1. 全局配置 =====
const API_BASE = '';
let TIANDITU_KEY = '';
const TONGLU_BBOX = [119.16, 29.58, 119.80, 30.12];

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

// P1-2: 地图高亮 + 雷达联动
let matchHighlightLayer = null;
let candidateLabelLayer = null;
let baselineRadarValues = null;
let matchRadarOverride = null;
let matchRadarTimer = null;
let adminBoundaryLayer = null;
let adminHoveredLayer = null;
let adminTooltip = null;

const INDUSTRY_COLORS = {
  '精密制造': '#FA8C16', '智能制造': '#FA8C16', '智能装备': '#FA8C16',
  '数字经济': '#1890FF', '大健康': '#52C41A',
  '快递物流': '#722ED1', '物流仓储': '#722ED1',
  '文旅康养': '#EB2F96', '绿色经济': '#52C41A',
  '新能源': '#13C2C2', '医疗器械': '#2F54EB', '食品加工': '#FAAD14',
};
const DEFAULT_HIGHLIGHT_COLOR = '#1890FF';

const INDUSTRY_DIMENSION_WEIGHTS = {
  '精密制造': { '产业匹配': 0.5, '空间分析': 0.3, '政策理解': 0.1, '风险识别': 0.1, '企业匹配': 0.0 },
  '智能制造': { '产业匹配': 0.4, '空间分析': 0.3, '政策理解': 0.1, '风险识别': 0.1, '企业匹配': 0.1 },
  '数字经济': { '产业匹配': 0.3, '空间分析': 0.2, '政策理解': 0.2, '风险识别': 0.1, '企业匹配': 0.2 },
  '大健康':   { '产业匹配': 0.2, '空间分析': 0.2, '政策理解': 0.3, '风险识别': 0.2, '企业匹配': 0.1 },
  '快递物流': { '产业匹配': 0.1, '空间分析': 0.5, '政策理解': 0.1, '风险识别': 0.1, '企业匹配': 0.2 },
  '物流仓储': { '产业匹配': 0.1, '空间分析': 0.5, '政策理解': 0.1, '风险识别': 0.1, '企业匹配': 0.2 },
  '文旅康养': { '产业匹配': 0.2, '空间分析': 0.2, '政策理解': 0.3, '风险识别': 0.2, '企业匹配': 0.1 },
  '绿色经济': { '产业匹配': 0.2, '空间分析': 0.2, '政策理解': 0.3, '风险识别': 0.2, '企业匹配': 0.1 },
  '新能源':   { '产业匹配': 0.3, '空间分析': 0.3, '政策理解': 0.2, '风险识别': 0.2, '企业匹配': 0.0 },
  '医疗器械': { '产业匹配': 0.3, '空间分析': 0.2, '政策理解': 0.3, '风险识别': 0.1, '企业匹配': 0.1 },
  '食品加工': { '产业匹配': 0.2, '空间分析': 0.3, '政策理解': 0.2, '风险识别': 0.2, '企业匹配': 0.1 },
  '智能装备': { '产业匹配': 0.4, '空间分析': 0.3, '政策理解': 0.1, '风险识别': 0.1, '企业匹配': 0.1 },
};
const DIMENSION_KEYS = ['产业匹配', '政策理解', '空间分析', '风险识别', '企业匹配'];

// 射线法判断点是否在 Leaflet Polygon 内
function _isInLeafletPolygon(lng, lat, polygon) {
  var rings = polygon.getLatLngs();
  if (!rings || rings.length === 0) return false;
  var flat = [];
  function flatten(r) {
    if (r.length > 0 && (typeof r[0] === 'number' || r[0].lat !== undefined)) { flat = r; return; }
    if (Array.isArray(r[0])) { flatten(r[0]); }
  }
  flatten(rings);
  var pts = flat.map(function(p) { return [p.lng !== undefined ? p.lng : p[0], p.lat !== undefined ? p.lat : p[1]]; });
  return pointInPolygon(lng, lat, pts);
}

// ===== 配置加载 =====
async function loadConfig() {
  try { const r = await fetch(API_BASE + '/api/config'); const data = await r.json(); TIANDITU_KEY = data.tianditu_key || ''; } catch {}
}

// ===== 地图初始化 =====
function initMap() {
  map = L.map('map', { zoomControl: true, maxZoom: 18 });
  if (TIANDITU_KEY) {
    const tileUrl = `http://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_KEY}`;
    L.tileLayer(tileUrl, { subdomains: ['0','1','2','3','4','5','6','7'], minZoom: 10, maxZoom: 18, errorTileUrl: '/data/tiles/{z}/{x}/{y}.png' }).addTo(map);
    const lblUrl = `http://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_KEY}`;
    L.tileLayer(lblUrl, { subdomains: ['0','1','2','3','4','5','6','7'], minZoom: 10, maxZoom: 18 }).addTo(map);
  }
  map.whenReady(() => map.invalidateSize());
  if (state.role === 'government') {
    setupDrawControl();
    setupMouseInteraction();
  }
  loadAdminBoundaries();
}

// ---- Box Selection ----

// ===== P1-3: 行政区划悬停高亮（事件穿透 + 射线法命中检测）=====
async function loadAdminBoundaries() {
  try {
    const resp = await fetch('XZQ_wgs84.geojson');
    const data = await resp.json();

    adminBoundaryLayer = L.geoJSON(data, {
      interactive: false,
      style: { color: '#1A1B1C', weight: 2, fillOpacity: 0, dashArray: null }
    }).addTo(map);

    // XZQ 最大外接矩形约束地图视角
    const xzqBounds = adminBoundaryLayer.getBounds();
    map.setMaxBounds(xzqBounds.pad(0.05));
    map.fitBounds(xzqBounds);
    if (!map.options.minZoom) map.setMinZoom(map.getZoom());

    // XZQ_Merge：dissolve 合并的县域边界，红色描边叠在黑色 XZQ 之上
    fetch('XZQ_Merge.geojson').then(function(r) { return r.json(); }).then(function(mergeData) {
      L.geoJSON(mergeData, {
        interactive: false,
        style: function() { return { color: '#F5222D', weight: 3, fillOpacity: 0, opacity: 0.9 }; }
      }).addTo(map);
    }).catch(function() {});

    state._adminFeatures = data.features;
    state._currentAdminName = null;

    let moveTimer = null;
    map.on('mousemove', function(e) {
      if (state._drawing) return;
      if (state._gridHoverActive) { clearAdminHover(); return; }
      if (moveTimer) return;
      moveTimer = setTimeout(function() { moveTimer = null; }, 16);
      const lng = e.latlng.lng, lat = e.latlng.lat;
      const hit = findAdminFeature(lng, lat);
      if (!hit) { if (state._currentAdminName !== null) clearAdminHover(); return; }
      if (state._currentAdminName === hit.properties.name) {
        if (adminTooltip) adminTooltip.setLatLng(e.latlng);
        return;
      }
      clearAdminHover();
      adminHoveredLayer = L.geoJSON(hit, {
        interactive: false,
        style: { color: '#1890FF', weight: 1.5, fillOpacity: 0.08, fillColor: '#1890FF', dashArray: '6 4' }
      }).addTo(map);
      adminTooltip = L.tooltip({
        permanent: false, direction: 'top', offset: [0, -15],
        className: 'admin-tooltip', interactive: false
      }).setContent(hit.properties.name).setLatLng(e.latlng).addTo(map);
      state._currentAdminName = hit.properties.name;
    });

    map.on('mouseout', clearAdminHover);
    map.on('movestart', clearAdminHover);
    map.on('zoomstart', clearAdminHover);
  } catch (e) { console.warn('行政区划加载失败:', e); }
}

function clearAdminHover() {
  if (adminHoveredLayer) { map.removeLayer(adminHoveredLayer); adminHoveredLayer = null; }
  if (adminTooltip) { map.removeLayer(adminTooltip); adminTooltip = null; }
  state._currentAdminName = null;
}

function pointInPolygon(lng, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersect = ((yi > lat) !== (yj > lat)) &&
      (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function findAdminFeature(lng, lat) {
  if (!state._adminFeatures) return null;
  for (const feat of state._adminFeatures) {
    const geom = feat.geometry;
    if (geom.type === 'Polygon') {
      if (pointInPolygon(lng, lat, geom.coordinates[0])) return feat;
    } else if (geom.type === 'MultiPolygon') {
      for (const poly of geom.coordinates) {
        if (pointInPolygon(lng, lat, poly[0])) return feat;
      }
    }
  }
  return null;
}

// ---- Box Selection ----
function setupDrawControl() {
  if (state.drawControl) return;
  state.drawControl = new L.Control.Draw({ draw: { rectangle: { shapeOptions: { color: '#f0883e', weight: 2 } }, polygon: false, polyline: false, circle: false, marker: false, circlemarker: false }, edit: false });
  map.addControl(state.drawControl);
  map.on('draw:drawstart', () => {
    state._drawing = true;
    clearHighlights();
    if (state.drawnRect) { map.removeLayer(state.drawnRect); state.drawnRect = null; state.currentBbox = null; }
    if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; }
    state.candidateGrids = [];
  });
  map.on(L.Draw.Event.CREATED, (e) => {
    if (state.drawnRect) map.removeLayer(state.drawnRect);
    state.drawnRect = e.layer; map.addLayer(e.layer);
    const b = e.layer.getBounds();
    state.currentBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    handleBboxQuery(state.currentBbox);
    setTimeout(function() { state._drawing = false; }, 500);
  });
  map.on('draw:drawstop', function() { state._gridHoverActive = false; });
}

function removeDrawControl() {
  if (state.drawControl) { map.removeControl(state.drawControl); state.drawControl = null; }
  if (state.drawnRect) { map.removeLayer(state.drawnRect); state.drawnRect = null; state.currentBbox = null; }
  if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; }
  state.candidateGrids = [];
}

async function handleBboxQuery(bbox) {
  const infoBar = document.getElementById('chat-info-bar'), infoText = document.getElementById('chat-info-text');
  infoBar.classList.add('visible'); infoText.textContent = '正在查询...';
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
  } catch { infoText.textContent = '查询异常'; }
}
function renderBboxHighlight(geojson) {
  if (state.candidateLayer) map.removeLayer(state.candidateLayer);
  state.candidateLayer = L.geoJSON(geojson, { style: { color: '#f0883e', weight: 1, fillOpacity: 0.3, fillColor: '#f0883e' } }).addTo(map);
}

// ---- Mouse Interaction ----
function setupMouseInteraction() {
  map.on('mousemove', (e) => { _mouseMoveHandler(e); });
  map.on('mouseout', () => { if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; } });
  map.on('click', (e) => { _mouseClickHandler(e); });
}

function _mouseMoveHandler(e) {
  if (state.role !== 'government') return;
  const now = Date.now(); if (now - _lastQueryTs < 200) return; _lastQueryTs = now;
  const { lat, lng } = e.latlng; const zoom = map.getZoom();
  fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
    .then(r => r.json()).then(cells => { if (cells && cells.length > 0) renderSingleGrid(cells[0]); }).catch(() => {});
}

async function _mouseClickHandler(e) {
  if (state.role !== 'government') return;
  if (state._drawing) return;
  const { lat, lng } = e.latlng; const zoom = map.getZoom();
  let gridId;
  try { const cells = await (await fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)).json(); gridId = cells[0]?.grid_id; } catch {}
  if (!gridId) { stickyNote.hide(); return; }
  try {
    const r = await fetch(`${API_BASE}/api/map/grid/${gridId}?role=government`);
    if (!r.ok) return;
    const data = await r.json(); data.level = [11,12,13,14,15].reduce((a,z,i) => zoom<=z?i+1:a, 0);
    const point = map.latLngToContainerPoint(e.latlng);
    stickyNote.toggle(data, point);
  } catch {}
}

function renderSingleGrid(cell) {
  if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; }
  if (!cell || !cell.coords) return;
  state.highlightLayer = L.geoJSON({ type: 'Feature', properties: { grid_id: cell.grid_id }, geometry: { type: 'Polygon', coordinates: cell.coords } }, { style: { fillOpacity: 0.45, fillColor: getLandColor(cell.land_type || ''), color: getLandColor(cell.land_type || ''), weight: 2 } }).addTo(map);
}

// ===== 渔网精简 =====
function loadFishnetLayer() {
  loadGridLight().catch(() => {});
}
function removeFishnetLayer() {
  if (state.gridLightLayer && map.hasLayer(state.gridLightLayer)) map.removeLayer(state.gridLightLayer);
}

async function loadGridLight() {
  try {
    const r = await fetch('/static/grid_light.geojson');
    if (!r.ok) throw new Error();
    const data = await r.json();
    if (!data.features || data.features.length === 0) { document.getElementById('health-badge').textContent = '● 渔网未就绪'; document.getElementById('health-badge').className = 'health-badge degraded'; return; }
    state.gridLightLayer = L.geoJSON(data, { style: (f) => ({ color: getLandColor(f.properties.land_type), weight: 0.5, fillOpacity: 0.25, fillColor: getLandColor(f.properties.land_type) }) });
    map.on('zoomend', () => { const z = map.getZoom(); if (z >= 13 && !map.hasLayer(state.gridLightLayer)) map.addLayer(state.gridLightLayer); else if (z < 13 && map.hasLayer(state.gridLightLayer)) map.removeLayer(state.gridLightLayer); });
    if (map.getZoom() >= 13) map.addLayer(state.gridLightLayer);
  } catch { document.getElementById('health-badge').textContent = '● 渔网未就绪'; document.getElementById('health-badge').className = 'health-badge degraded'; }
}

// ===== 角色切换 =====
function setupRoleSwitch() {
  document.getElementById('btn-gov').addEventListener('click', () => setRole('government'));
  document.getElementById('btn-ent').addEventListener('click', () => {
    alert('企业端功能建设中，敬请期待');
  });
}

function setRole(role) {
  if (state.role === role) return;
  state.role = role;
  clearHighlights();
  const main = document.getElementById('app-main');
  main.setAttribute('data-role', role);

  // 左栏置换
  document.getElementById('gov-left-panel').style.display = role === 'government' ? '' : 'none';
  document.getElementById('ent-left-panel').style.display = role === 'enterprise' ? '' : 'none';

  // 按钮状态
  document.getElementById('btn-gov').classList.toggle('active', role === 'government');
  document.getElementById('btn-ent').classList.toggle('active', role === 'enterprise');

  // 地图交互
  if (role === 'government') { setupDrawControl(); setupMouseInteraction(); loadFishnetLayer(); }
  else { removeDrawControl(); removeFishnetLayer(); }

  // 更新输入框 placeholder
  const input = document.getElementById('center-chat-input');
  if (input) input.placeholder = role === 'government' ? '输入您的问题，例如：城东30亩适合什么产业？' : '描述您的用地需求，例如：我需要1000㎡厂房';

  // 更新 EvoMap 文案
  if (state.evolutionStats) updateEvoPanel(state.evolutionStats);
  else loadEvolutionStats();

  // 地图重新计算尺寸
  if (map) setTimeout(() => map.invalidateSize(), 100);
}

// ===== 对话 =====
function setupChat() {
  document.getElementById('center-chat-send').addEventListener('click', sendChat);
  const input = document.getElementById('center-chat-input');
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } });
  input.addEventListener('input', () => { document.getElementById('center-char-count').textContent = input.value.length + '/500'; });
}

async function sendChat() {
  clearHighlights();
  const input = document.getElementById('center-chat-input'); const msg = input.value.trim(); if (!msg) return; input.value = '';
  document.getElementById('center-char-count').textContent = '0/500';
  appendChatMessage('user', msg); state.chatHistory.push({ role: 'user', content: msg });
  const loadingId = appendChatMessage('assistant', '<span class="loading">评估中...</span>');
  try {
    const r = await fetch(`${API_BASE}/api/agent/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg, role: state.role, bbox: state.currentBbox || null, context: state.chatHistory.slice(-10) }) });
    const data = await r.json();
    const md = document.getElementById(loadingId); if (md) md.remove();
    renderAgentReply(data); state.chatHistory.push({ role: 'assistant', content: JSON.stringify(data) });
    if (data.candidate_grids && data.candidate_grids.length > 0) highlightCandidateGrids(data.candidate_grids, state.role);
    if (state.drawnRect) { map.removeLayer(state.drawnRect); state.drawnRect = null; }
    if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; }
    state.currentBbox = null;
    if (state.role === 'government' && data.items && data.items.length > 0) applyMatchRadar(data.items);
  } catch { const md = document.getElementById(loadingId); if (md) md.innerHTML = '请求失败，请重试'; resetInteractionState(); }
}
function appendChatMessage(role, content) { const d = document.createElement('div'); d.className = `chat-msg ${role}`; d.id = 'msg-' + Date.now(); d.innerHTML = typeof content === 'string' ? content : ''; document.getElementById('chat-messages').appendChild(d); d.scrollIntoView({ behavior: 'smooth' }); return d.id; }

function renderAgentReply(data) {
  const d = document.createElement('div'); d.className = 'chat-msg assistant agent-reply';
  let h = '';
  if (typeof data.summary === 'string') h += `<p>${escapeHtml(data.summary)}</p>`;
  if (data.items) data.items.forEach(item => {
    h += `<div class="item"><span class="rank">#${item.rank}</span> <b>${escapeHtml(item.industry||'')}</b> <span class="score">${item.score||0}/10</span><p>${escapeHtml(item.reason||'')}</p>`;
    if (item.policy_refs && item.policy_refs.length) h += `<div class="policy-cite">📜 ${item.policy_refs.map(escapeHtml).join('；')}</div>`;
    if (item.risk) h += `<div class="risk">⚠️ ${escapeHtml(item.risk)}</div>`; h += '</div>';
  });
  if (data.risks && data.risks.length) h += '<div class="risks-block">⚠️ 风险提示：' + data.risks.map(escapeHtml).join('；') + '</div>';

  // 企业端专属：下一步建议
  if (state.role === 'enterprise' && data.next_steps) {
    h += `<div class="card section-next-steps"><h4>👉 下一步建议</h4><p>${escapeHtml(data.next_steps)}</p></div>`;
  }

  d.innerHTML = h; document.getElementById('chat-messages').appendChild(d); d.scrollIntoView({ behavior: 'smooth' });
}
function escapeHtml(str) { if (!str) return ''; const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
function highlightCandidates(gridIds) {
  if (!gridIds || gridIds.length === 0) return;
  if (gridIds.length > 0 && typeof gridIds[0] === 'object' && gridIds[0].grid_id) {
    highlightCandidateGrids(gridIds, state.role);
  }
}

// ===== 企业卡片网格（政府端） =====

// ===== 企业卡片网格（政府端） =====
async function loadEnterprises(search = '') {
  const grid = document.getElementById('ent-card-grid');
  grid.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const url = search ? `${API_BASE}/api/enterprise/list?search=${encodeURIComponent(search)}` : `${API_BASE}/api/enterprise/list`;
    const data = await (await fetch(url)).json();
    if (data.length === 0) { grid.innerHTML = '<div class="loading">无匹配企业</div>'; return; }
    renderEnterpriseCards(data);
  } catch { grid.innerHTML = '<div class="loading">加载失败</div>'; }
}

function renderEnterpriseCards(enterprises) {
  window._cachedEnterprises = enterprises;
  const grid = document.getElementById('ent-card-grid');
  grid.innerHTML = '';
  enterprises.forEach(ent => {
    const card = document.createElement('div');
    card.className = 'ent-card' + (state.selectedEnterpriseIds.includes(ent.id) ? ' selected' : '');
    card.dataset.eid = ent.id;
    card.innerHTML = `<div class="card-name">${escapeHtml(ent.name)}</div><div class="card-industry">${escapeHtml(ent.industry||'')}</div><div class="card-revenue">年营收 ${escapeHtml(ent.annual_revenue||'-')}</div>`;
    card.addEventListener('click', () => {
      if (state.selectedEnterpriseIds.includes(ent.id)) {
        state.selectedEnterpriseIds = state.selectedEnterpriseIds.filter(id => id !== ent.id);
      } else {
        state.selectedEnterpriseIds.push(ent.id);
      }
      updateEnterpriseCards();
      updateMatchButton();
    });
    grid.appendChild(card);
  });
}

function updateEnterpriseCards() {
  var cached = window._cachedEnterprises;
  if (!cached) return;
  document.querySelectorAll('#ent-card-grid .ent-card').forEach(function(card) {
    var eid = card.dataset.eid;
    if (eid) {
      card.className = 'ent-card' + (state.selectedEnterpriseIds.includes(eid) ? ' selected' : '');
    }
  });
}

function updateMatchButton() {
  const b = document.getElementById('ent-match-btn');
  const n = state.selectedEnterpriseIds.length;
  b.disabled = state.role === 'enterprise' || n === 0;
  b.textContent = n === 0 ? '分析选中企业（0 家）' : `分析选中企业（${n} 家）`;
}

async function triggerMatch() {
  if (state.selectedEnterpriseIds.length === 0) return;
  const btn = document.getElementById('ent-match-btn'); btn.disabled = true; btn.textContent = '匹配中...';
  try {
    var bbox = map ? map.getBounds().toBBoxString() : null;
    const data = await (await fetch(`${API_BASE}/api/enterprise/match`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enterprise_ids: state.selectedEnterpriseIds, bbox: bbox }) })).json();
    const n = data.enterprise_names?.length || 0;
    appendChatMessage('assistant', `🏭 综合布局分析（${n} 家企业，合计 ${data.total_area_mu || 0} 亩）`);
    if (data.summary) appendChatMessage('assistant', data.summary);
    if (data.items) {
      data.items.forEach(item => {
        appendChatMessage('assistant', `📌 ${item.rank}. ${escapeHtml(item.industry||'')}（${item.score}分）\n${escapeHtml(item.reason||'')}`);
      });
    }
    // P1-2: 地图高亮 + 雷达联动
    if (data.candidate_grids && data.candidate_grids.length > 0) {
      highlightCandidateGrids(data.candidate_grids, 'government');
    }
    if (state.drawnRect) { map.removeLayer(state.drawnRect); state.drawnRect = null; }
    if (state.candidateLayer) { map.removeLayer(state.candidateLayer); state.candidateLayer = null; }
    state.currentBbox = null;
    if (data.items && data.items.length > 0) {
      applyMatchRadar(data.items);
    }
  } catch { appendChatMessage('assistant', '⚠️ 匹配请求失败'); } finally { btn.disabled = false; updateMatchButton(); resetInteractionState(); }
}

// ===== P1-2: 地图高亮 =====
async function highlightCandidateGrids(candidateData, role) {
  clearHighlights();
  if (!candidateData || candidateData.length === 0) return;
  matchHighlightLayer = L.layerGroup();
  candidateLabelLayer = L.layerGroup();
  if (role === 'government') {
    await highlightAsGridPolygons(candidateData);
  } else {
    highlightAsConvexHull(candidateData);
  }
  addLabelBubbles(candidateData);
  map.addLayer(matchHighlightLayer);
  if (candidateLabelLayer) map.addLayer(candidateLabelLayer);
  // 视图移到高亮区域中心
  var lngs = candidateData.map(function(c) { return c.lng; }).filter(Boolean);
  var lats = candidateData.map(function(c) { return c.lat; }).filter(Boolean);
  if (lngs.length > 0 && lats.length > 0) {
    var bounds = L.latLngBounds(
      [Math.min.apply(null, lats), Math.min.apply(null, lngs)],
      [Math.max.apply(null, lats), Math.max.apply(null, lngs)]
    );
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.3));
  }
}

async function highlightAsGridPolygons(candidates) {
  var gridIds = candidates.map(function(c) { return c.grid_id; }).filter(Boolean);
  if (gridIds.length > 200) gridIds = gridIds.slice(0, 200);
  try {
    var resp = await fetch(API_BASE + '/api/map/grids_geometry', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grid_ids: gridIds, role: 'government' }),
    });
    var data = await resp.json();
    if (!data.features || data.features.length === 0) { highlightAsConvexHull(candidates); return; }
    var groups = {};
    candidates.forEach(function(c) {
      var ind = c.industry || '其他';
      if (!groups[ind]) groups[ind] = [];
      groups[ind].push(c);
    });
    for (var industry in groups) {
      var items = groups[industry];
      var color = INDUSTRY_COLORS[industry] || DEFAULT_HIGHLIGHT_COLOR;
      var groupIds = items.map(function(i) { return i.grid_id; });
      var feats = data.features.filter(function(f) { return groupIds.indexOf(f.properties.grid_id) >= 0; });
      if (feats.length === 0) continue;
      L.geoJSON({ type: 'FeatureCollection', features: feats }, {
        interactive: false,
        style: { color: color, weight: 2, fillColor: color, fillOpacity: items.length > 1 ? 0.15 : 0.25 },
        onEachFeature: function(feature, layer) {
          var item = items.find(function(i) { return i.grid_id === feature.properties.grid_id; });
          if (item) layer.bindPopup('<b>' + escapeHtml(item.industry || '') + '</b> 评分 ' + (item.score || 0) + '<br>' + escapeHtml((item.reason || '').slice(0, 80)));
        },
      }).addTo(matchHighlightLayer);
    }
  } catch (e) { highlightAsConvexHull(candidates); }
}

function computeConvexHull(points) {
  if (points.length < 3) return points;
  points.sort(function(a, b) { return a[0] === b[0] ? a[1] - b[1] : a[0] - b[0]; });
  var build = function(pts) {
    var h = [];
    for (var i = 0; i < pts.length; i++) {
      while (h.length >= 2) {
        var a = h[h.length - 2], b = h[h.length - 1], c = pts[i];
        if ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0) break;
        h.pop();
      }
      h.push(pts[i]);
    }
    return h;
  };
  var lower = build(points);
  var upper = build(points.slice().reverse());
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

function highlightAsConvexHull(candidates) {
  var points = candidates.filter(function(c) { return c.lng && c.lat; }).map(function(c) { return [c.lng, c.lat]; });
  if (points.length >= 3) {
    var hull = computeConvexHull(points);
    if (hull.length >= 3) {
      var latlngs = hull.map(function(p) { return [p[1], p[0]]; });
      var poly = L.polygon(latlngs, { color: '#1890FF', weight: 2, fillColor: '#1890FF', fillOpacity: 0.12, dashArray: '6 4' }).addTo(matchHighlightLayer);
      poly.bindTooltip('大致范围示意，非精确地块边界', { permanent: true, direction: 'center', className: 'convex-hull-tip', offset: [0, 0] });
    }
  } else if (points.length === 1) {
    L.circle([points[0][1], points[0][0]], { radius: 800, color: '#1890FF', weight: 2, fillColor: '#1890FF', fillOpacity: 0.12, dashArray: '6 4' }).addTo(matchHighlightLayer);
  }
}

function addLabelBubbles(candidates) {
  candidates.forEach(function(c, i) {
    if (c.lng && c.lat) {
      var icon = L.divIcon({ className: 'candidate-label', html: '<span>' + (i + 1) + '</span>', iconSize: [24, 24], iconAnchor: [12, 12] });
      var marker = L.marker([c.lat, c.lng], { icon: icon, interactive: true });
      if (c.industry) {
        marker.bindPopup('<b>' + escapeHtml(c.industry || '') + '</b> 评分 ' + (c.score || 0) + '<br>' + escapeHtml((c.reason || '').slice(0, 80)));
      }
      marker.addTo(candidateLabelLayer);
    }
  });
}

function clearHighlights() {
  if (matchHighlightLayer) { matchHighlightLayer.clearLayers(); map.removeLayer(matchHighlightLayer); matchHighlightLayer = null; }
  if (candidateLabelLayer) { candidateLabelLayer.clearLayers(); map.removeLayer(candidateLabelLayer); candidateLabelLayer = null; }
  state._highlightBounds = null;
  resetInteractionState();
}

function resetInteractionState() {
  state._drawing = false;
  state._gridHoverActive = false;
  state._highlightBounds = null;
}

// ===== P1-2: 雷达联动 =====
function computeMatchRadar(items) {
  var scores = {};
  DIMENSION_KEYS.forEach(function(d) { scores[d] = 0; });
  var totalWeight = 0;
  items.forEach(function(item) {
    var w = INDUSTRY_DIMENSION_WEIGHTS[item.industry];
    if (!w) return;
    var iw = (item.score || 0) / 10;
    DIMENSION_KEYS.forEach(function(d) { scores[d] += (w[d] || 0) * iw; });
    totalWeight += iw;
  });
  if (totalWeight === 0) return null;
  var result = {};
  DIMENSION_KEYS.forEach(function(d) { result[d] = Math.round((scores[d] / totalWeight) * 100); });
  return result;
}

function applyMatchRadar(items) {
  var matchValues = computeMatchRadar(items);
  if (!matchValues) return;
  matchRadarOverride = matchValues;
  updateRadarDisplay();
  clearTimeout(matchRadarTimer);
  matchRadarTimer = setTimeout(function() {
    matchRadarOverride = null;
    updateRadarDisplay();
  }, 30000);
}

function updateRadarDisplay() {
  if (!state.radarChart) return;
  var values = matchRadarOverride || baselineRadarValues || {};
  var data = DIMENSION_KEYS.map(function(dim) { return values[dim] || 0; });
  state.radarChart.data.datasets[0].data = data;
  state.radarChart.update('none');
  var isLinked = !!matchRadarOverride;
  var panel = document.getElementById('evo-panel');
  if (panel) panel.classList.toggle('radar-linked', isLinked);
  var badge = document.getElementById('evo-role-badge');
  if (badge) badge.textContent = isLinked ? '匹配侧重' : (state.role === 'government' ? '政府端' : '企业端');
}

// ===== 自进化 + EvoMap 双文案 =====
const EVO_LABELS = {
  government: {
    title: '🧬 Agent 自进化',
    tabRadar: '能力雷达',
    tabCurve: '进化曲线',
    tabCapsules: '经验胶囊',
    experience: (n) => `已学习 ${n} 次决策经验`,
    understanding: (p) => `偏好理解度 ${p}%`,
    capsules: (n) => `已贡献 ${n} 条经验`,
    emptyCurve: '尚未积累进化数据，完成首次评估后将自动生成进化曲线',
    emptyCapsules: '尚未发布经验胶囊，评估产生方法论变更后将自动发布',
    curveTitle: '评估基因权重进化轨迹',
  },
  enterprise: {
    title: '🧬 Agent 自进化',
    tabRadar: '能力雷达',
    tabCurve: '进化曲线',
    tabCapsules: '匹配经验',
    experience: (n) => `已学习 ${n} 次企业匹配经验`,
    understanding: (p) => `需求理解度 ${p}%`,
    capsules: (n) => `已积累 ${n} 条匹配经验`,
    emptyCurve: '尚未积累进化数据，完成首次匹配后将自动生成进化曲线',
    emptyCapsules: '尚未积累匹配经验，每次匹配都将帮助 Agent 更懂您的需求',
    curveTitle: '需求匹配能力进化轨迹',
  },
};

let currentEvoTab = 'radar';
let curveChart = null;

// === Tab 切换 ===
function setupEvoTabs() {
  document.querySelectorAll('.evo-tab').forEach(btn => {
    btn.addEventListener('click', () => switchEvoTab(btn.dataset.evoTab));
  });
}

function switchEvoTab(tabName) {
  currentEvoTab = tabName;
  document.querySelectorAll('.evo-content').forEach(el => {
    el.classList.toggle('active', el.id === 'evo-content-' + tabName);
  });
  document.querySelectorAll('.evo-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.evoTab === tabName);
  });
  if (tabName === 'radar') {
    destroyCurveChart();
    if (state.evolutionStats && state.evolutionStats.radar_values) {
      renderRadarChart(state.evolutionStats.radar_values);
    }
  } else if (tabName === 'curve') {
    destroyCurveChart();
    if (state.evolutionStats && state.evolutionStats.gene_history) {
      renderCurveChart(state.evolutionStats.gene_history);
    } else {
      var el = document.getElementById('evo-content-curve');
      if (el) el.innerHTML = '<div class="evo-empty">' + getEvoLabels().emptyCurve + '</div>';
    }
  } else if (tabName === 'capsules') {
    destroyCurveChart();
    renderCapsuleList();
  }
}

// === 进化曲线 ===
function renderCurveChart(geneHistory) {
  var el = document.getElementById('evo-content-curve');
  if (!geneHistory || geneHistory.length < 2) {
    if (el) el.innerHTML = '<div class="evo-empty">' + getEvoLabels().emptyCurve + '</div>';
    return;
  }
  el.innerHTML = '<div class="curve-wrap"><canvas id="curve-chart"></canvas></div>';
  var canvas = document.getElementById('curve-chart');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  curveChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: geneHistory.map(function(g) { return 'v' + g.version; }),
      datasets: [
        { label: '权属协调度', data: geneHistory.map(function(g) { return g.nld_qsxt; }), borderColor: '#1890FF', backgroundColor: 'rgba(24,144,255,0.1)', tension: 0.2, yAxisID: 'y' },
        { label: '产业集聚度', data: geneHistory.map(function(g) { return g.yld_jjd; }), borderColor: '#FA8C16', tension: 0.2, yAxisID: 'y' },
        { label: '交通可达性', data: geneHistory.map(function(g) { return g.yld_jtkd; }), borderColor: '#52C41A', tension: 0.2, yAxisID: 'y' },
        { label: '评估累计（次）', data: geneHistory.map(function(g) { return g.eval_count; }), borderColor: '#8B8FA3', borderDash: [4,4], tension: 0.2, yAxisID: 'y1' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 800 },
      scales: {
        y: { type: 'linear', position: 'left', min: 0, max: 1.0, title: { display: true, text: '权重' } },
        y1: { type: 'linear', position: 'right', title: { display: true, text: '评估次数' }, grid: { drawOnChartArea: false } },
        x: { title: { display: true, text: 'Gene 版本' } },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(3); },
            afterBody: function(ctx) { var g = geneHistory[ctx[0].dataIndex]; return g.change_desc ? '变更: ' + g.change_desc : ''; },
          },
        },
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
      },
    },
  });
}

function destroyCurveChart() {
  if (curveChart) { curveChart.destroy(); curveChart = null; }
  // 恢复曲线容器模板
  var el = document.getElementById('evo-content-curve');
  if (el && el.querySelector('#curve-chart')) {
    el.innerHTML = '<div class="curve-wrap"><canvas id="curve-chart"></canvas></div>';
  }
}

// === Capsule 列表 ===
async function renderCapsuleList() {
  var list = document.getElementById('capsule-list');
  if (!list) return;
  list.innerHTML = '<div class="loading">加载中...</div>';
  try {
    var data = await (await fetch(API_BASE + '/api/evomap/capsules?limit=10')).json();
    var capsules = data.capsules || [];
    if (capsules.length === 0) {
      list.innerHTML = '<div class="evo-empty">' + getEvoLabels().emptyCapsules + '</div>';
      return;
    }
    list.innerHTML = '';
    capsules.forEach(function(c) {
      var status = c.publish_status || 'candidate';
      var scene = c.scene || c.summary || '未标注场景';
      var reason = c.change_reason || c.trigger_reason || c.summary || '';
      var impact = c.impact || '';
      var time = (c.created_at || '').slice(5, 16).replace('T', ' ');
      var div = document.createElement('div');
      div.className = 'capsule-item';
      div.setAttribute('data-status', status);
      div.innerHTML =
        '<div class="capsule-header">' +
        '<span class="capsule-badge" data-status="' + status + '">● ' + (status === 'candidate' ? '已发布' : '失败') + '</span>' +
        '<span class="capsule-scene">' + escapeHtml(scene) + '</span>' +
        '<span class="capsule-time">' + time + '</span>' +
        '</div>' +
        (reason ? '<p class="capsule-reason">' + escapeHtml(reason) + '</p>' : '') +
        (impact ? '<p class="capsule-impact">📈 ' + escapeHtml(impact) + '</p>' : '');
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = '<div class="evo-empty">加载失败</div>';
  }
}

function getEvoLabels() {
  return EVO_LABELS[state.role] || EVO_LABELS.government;
}

async function loadEvolutionStats() {
  try {
    const data = await (await fetch(`${API_BASE}/api/evomap/status`)).json();
    state.evolutionStats = data;
    updateEvoPanel(data);
    if (!matchRadarOverride) {
      baselineRadarValues = data.radar_values;
      if (currentEvoTab === 'radar' && data.radar_values) renderRadarChart(data.radar_values);
    }
    if (currentEvoTab === 'curve') {
      destroyCurveChart();
      if (data.gene_history && data.gene_history.length >= 2) renderCurveChart(data.gene_history);
    }
  } catch {}
}

function updateEvoPanel(data) {
  var labels = getEvoLabels();
  // 统计摘要
  var countEl = document.getElementById('evo-count');
  var prefEl = document.getElementById('evo-pref');
  var capsEl = document.getElementById('evo-caps');
  if (countEl) countEl.textContent = data.evolution_count || 0;
  if (prefEl) prefEl.textContent = (data.preference_understanding || 0) + '%';
  if (capsEl) capsEl.textContent = data.capsules_published || 0;

  // 角色角标
  var badge = document.getElementById('evo-role-badge');
  if (badge) badge.textContent = state.role === 'government' ? '政府端' : '企业端';

  // 兼容旧 DOM（evo-experience 等可能已被移除）
  var expEl = document.getElementById('evo-experience');
  var methEl = document.getElementById('evo-methodology');
  var capsTextEl = document.getElementById('evo-capsules');
  if (expEl) expEl.textContent = '📊 ' + labels.experience(data.evolution_count || 0);
  if (methEl) methEl.textContent = '🧬 ' + labels.experience(data.capsules_published || 0);
  if (capsTextEl) capsTextEl.textContent = '📦 ' + labels.capsules(data.capsules_published || 0);
}

function renderRadarChart(values) {
  const canvas = document.getElementById('radar-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (state.radarChart) state.radarChart.destroy();
  const labels = ['产业匹配', '政策理解', '空间分析', '风险识别', '企业匹配'];
  state.radarChart = new Chart(ctx, {
    type: 'radar',
    data: { labels, datasets: [{ label: '能力雷达', data: labels.map(l => values[l] || 30), backgroundColor: 'rgba(24,144,255,0.15)', borderColor: '#1890FF', borderWidth: 2, pointBackgroundColor: '#1890FF', pointBorderColor: '#fff', pointRadius: 4 }] },
    options: { responsive: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 20, color: '#6B7280', backdropColor: 'transparent' }, pointLabels: { color: '#1A1B1C', font: { size: 10 } }, grid: { color: '#E0E3E8' }, angleLines: { color: '#E0E3E8' } } }, plugins: { legend: { display: false } } }
  });
}
function startEvolutionPolling() { if (!state.evolutionTimer) state.evolutionTimer = setInterval(loadEvolutionStats, 60000); }
function stopEvolutionPolling() { if (state.evolutionTimer) { clearInterval(state.evolutionTimer); state.evolutionTimer = null; } }

// ===== 健康检查 =====
function pollHealth() {
  fetch(`${API_BASE}/health`).then(r => r.json()).then(data => {
    const b = document.getElementById('health-badge');
    if (data.status === 'ok') { b.textContent = data.evomap_online ? '● 在线' : '● EvoMap 离线'; b.className = 'health-badge ' + (data.evomap_online ? 'online' : 'degraded'); }
    else { b.textContent = '● 服务降级'; b.className = 'health-badge degraded'; }
  }).catch(() => { const b = document.getElementById('health-badge'); b.textContent = '● 服务异常'; b.className = 'health-badge error'; });
} setInterval(pollHealth, 30000);

// ===== StickyNote =====
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
      const input = document.getElementById('center-chat-input');
      if (input) input.value = msg;
      this.hide();
      sendChat();
    });
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') this.hide(); });
  }
}

// ===== 企业端表单 =====
function initEnterpriseForm() {
  const form = document.getElementById('ent-form');
  if (!form) return;

  // 加载行业选项
  fetch(`${API_BASE}/api/enterprise/list?search=`).then(r => r.json()).then(data => {
    const industries = [...new Set(data.map(e => e.industry).filter(Boolean))];
    const sel = document.getElementById('ent-industry-select');
    industries.forEach(i => { const opt = document.createElement('option'); opt.value = i; opt.textContent = i; sel.appendChild(opt); });
  }).catch(() => {});

  // "不限"互斥逻辑
  ['location-prefs', 'facility-prefs'].forEach(groupId => {
    const group = document.getElementById(groupId);
    if (!group) return;
    group.addEventListener('change', (e) => {
      if (e.target.value === 'any' && e.target.checked) {
        group.querySelectorAll('input:not([value="any"])').forEach(cb => cb.checked = false);
      } else {
        group.querySelector('input[value="any"]').checked = false;
      }
    });
  });

  // 提交
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      enterprise_name: fd.get('ent_name'),
      industry: fd.get('industry'),
      area: parseFloat(fd.get('area')) || 0,
      area_unit: fd.get('area_unit') || '㎡',
      location: fd.getAll('loc'),
      facilities: fd.getAll('fac'),
      investment: parseFloat(fd.get('investment')) || 0,
      annual_output: parseFloat(fd.get('annual_output')) || 0,
      employees: parseInt(fd.get('employees')) || 0,
    };
    if (!payload.enterprise_name || !payload.industry || !payload.area) {
      alert('请填写企业名称、行业和用地面积');
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/api/enterprise/match`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      const messages = document.getElementById('chat-messages');
      messages.innerHTML = '';
      appendChatMessage('assistant', `🏢 ${payload.enterprise_name}（${payload.industry}）用地需求已提交`);
      renderAgentReply(data);
    } catch { appendChatMessage('assistant', '⚠️ 提交失败，请重试'); }
  });

  // 重置
  form.addEventListener('reset', () => {
    setTimeout(() => {
      document.getElementById('chat-messages').innerHTML = '';
    }, 0);
  });
}

// ===== 启动 =====
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  initMap();
  loadFishnetLayer();
  stickyNote = new StickyNote('map');
  map.on('zoomend', () => { if (state.currentBbox) handleBboxQuery(state.currentBbox); });
  setupRoleSwitch();
  setupChat();
  loadEnterprises();
  document.getElementById('ent-search').addEventListener('input', (e) => loadEnterprises(e.target.value));
  document.getElementById('ent-match-btn').addEventListener('click', triggerMatch);
  initEnterpriseForm();
  setupEvoTabs();
  loadEvolutionStats();
  startEvolutionPolling();
  pollHealth();
});
