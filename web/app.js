'use strict';

/* =====================================================================
 * 三角债智能梳理与净额轧差系统 · 前端
 * 单页应用，仅依赖标准浏览器 API 与本地 /api 接口。
 * ===================================================================== */

const VIEW = document.getElementById('view');
const NAV = document.getElementById('nav');
const TOPBAR = document.getElementById('topbar-actions');
const MODAL_ROOT = document.getElementById('modal-root');
const TOAST_ROOT = document.getElementById('toast-root');

const GROUP_LABELS = {
  ordinary: '普通债权',
  mortgage: '抵押优先债权',
  wage: '职工工资债权',
  tax: '税款债权',
  custom: '其他优先债权',
};
const STATUS_LABELS = { confirmed: '已确认', pending: '待复核', rejected: '已排除' };
const ACTION_LABELS = {
  'debt.create': '新增债务', 'debt.update': '修改债务', 'debt.delete': '删除债务',
  'debt.confirmed': '确认债务', 'debt.rejected': '排除债务', 'debt.pending': '转为待复核',
  'entity.create': '新增主体', 'entity.update': '修改主体', 'entity.delete': '删除主体',
  'netting.run': '生成清偿方案', 'eligibility.recheck': '重新校验抵销资格',
  'material.extract': '材料要素抽取', 'material.import': '导入抽取结果',
  'settings.update': '修改系统设置', 'ontology.reload': '重新加载本体',
  'plan.delete': '删除方案', 'export': '导出结果', 'demo.seed': '载入示例数据',
  'system.reset': '重置数据', 'llm.test': '测试模型连通性',
};

const NAV_ITEMS = [
  { key: 'cases', label: '工作记录', icon: 'cases' },
  { key: 'dashboard', label: '工作台', icon: 'dashboard' },
  { key: 'debts', label: '债务台账', icon: 'debts' },
  { key: 'materials', label: '材料抽取', icon: 'materials' },
  { key: 'graph', label: '债务图谱', icon: 'graph' },
  { key: 'plan', label: '轧差方案', icon: 'plan' },
  { key: 'records', label: '核算记录', icon: 'records' },
  { key: 'audit', label: '审计留痕', icon: 'audit' },
  { key: 'settings', label: '系统设置', icon: 'settings' },
];

const ICONS = {
  cases: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 7.5h16v11.5H4z"/><path d="M8 7.5V5h8v2.5M4 12h16"/><path d="M10 12v2h4v-2"/></svg>',
  dashboard: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/></svg>',
  debts: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/></svg>',
  materials: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"/><path d="M4 15v4.5h16V15"/></svg>',
  graph: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="7" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.2 6.5l7.5.4M7.2 8.1l3.6 7.5M16.4 9l-3.2 6.7"/></svg>',
  plan: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M5 12.5l4.2 4L19 7"/><circle cx="12" cy="12" r="9"/></svg>',
  records: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M5 4.5h14M5 10.5h14M5 16.5h8"/><circle cx="18" cy="18" r="2.4"/><path d="M18 16.2v1.8l1.2.8"/></svg>',
  audit: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.4 2"/></svg>',
  settings: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"/></svg>',
};

const state = {
  route: 'cases',
  activeCase: null,
  cases: [],
  bootstrap: null,
  settings: null,
  entities: [],
  debts: [],
  plans: [],
  materials: [],
  plan: null,
  pendingPlanId: null,
  comparison: null,
  comparePlans: null,
  planDetailOpen: false,
  graph: null,
  audit: [],
  extraction: null,
  selectedCandidates: new Set(),
  materialFile: null,
  materialText: '',
  selectedNode: null,
  graphIneligible: true,
  graphGroup: 'all',
  graphShowAmounts: true,
  graphView: 'auto',
  graphActiveCycle: null,
  graphTransform: { x: 0, y: 0, k: 1 },
  graphModel: null,
  graphChart: null,
  filters: { q: '', status: '', group: '' },
  busy: false,
};

/* ------------------------------------------------------------------ 工具 */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function fmtMoney(value) {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtCents(cents) {
  return fmtMoney(Number(cents || 0) / 100);
}

function fmtCompact(cents) {
  const value = Number(cents || 0) / 100;
  const abs = Math.abs(value);
  if (abs >= 100000000) return `${(value / 100000000).toFixed(2)}<em>亿元</em>`;
  if (abs >= 10000) return `${(value / 10000).toFixed(2)}<em>万元</em>`;
  return `${fmtMoney(value)}<em>元</em>`;
}

function shortId(id) {
  return String(id || '').replace(/^(debt|ent|plan|mat)_/, '#');
}

function fmtDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return esc(value);
  return date.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function fmtDate(value) {
  if (!value) return '—';
  return esc(String(value).slice(0, 10));
}

function truncate(value, length = 10) {
  const text = String(value || '');
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function badgeEligibility(debt) {
  const eligible = debt.eligibility?.eligible;
  return eligible
    ? '<span class="badge badge-ok">可抵销</span>'
    : `<span class="badge badge-danger">不入池</span>`;
}

function statusBadge(status) {
  const map = {
    confirmed: '<span class="badge badge-ok">已确认</span>',
    pending: '<span class="badge badge-warn">待复核</span>',
    rejected: '<span class="badge badge-neutral">已排除</span>',
  };
  return map[status] || `<span class="badge badge-neutral">${esc(status)}</span>`;
}

function severityBadge(severity) {
  if (severity === 'blocking') return '<span class="badge badge-danger">阻断</span>';
  if (severity === 'review') return '<span class="badge badge-warn">复核</span>';
  return '<span class="badge badge-info">提示</span>';
}

function toast(message, type = 'ok') {
  const node = document.createElement('div');
  node.className = `toast ${type}`;
  node.innerHTML = `<div class="toast-msg">${esc(message)}</div><button aria-label="关闭">×</button>`;
  node.querySelector('button').addEventListener('click', () => node.remove());
  TOAST_ROOT.appendChild(node);
  setTimeout(() => {
    node.style.opacity = '0';
    node.style.transition = 'opacity .25s ease';
    setTimeout(() => node.remove(), 250);
  }, type === 'err' ? 6500 : 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'debt-netting',
    },
    ...options,
  });
  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!response.ok) throw new Error((data && data.error) || `请求失败（HTTP ${response.status}）`);
  return data;
}

function setBusy(button, busy) {
  if (!button) return;
  button.disabled = busy;
  if (busy) {
    button.dataset.label = button.innerHTML;
    button.innerHTML = '<span class="spinner"></span> 处理中…';
  } else if (button.dataset.label) {
    button.innerHTML = button.dataset.label;
    delete button.dataset.label;
  }
}

function emptyState(icon, title, text, actionHtml = '') {
  return `<div class="empty"><div class="empty-icon">${icon}</div><h3>${esc(title)}</h3><p>${esc(text)}</p>${actionHtml}</div>`;
}

function skeleton() {
  return `<div class="card skeleton">
    <div class="sk-line w40"></div><div class="sk-line w80"></div><div class="sk-line w60"></div>
    <div style="height:22px"></div><div class="sk-line"></div><div class="sk-line"></div><div class="sk-line w80"></div>
  </div>`;
}

/* ------------------------------------------------------------------ 弹窗 */
function openModal({ title, subtitle = '', body, footer = '', wide = false, onMount = null }) {
  MODAL_ROOT.innerHTML = `
    <div class="modal-overlay" id="modal-overlay">
      <div class="modal ${wide ? 'modal-wide' : ''}" role="dialog" aria-modal="true">
        <div class="modal-head">
          <div><h2>${esc(title)}</h2>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div>
          <button class="modal-close" data-close aria-label="关闭">×</button>
        </div>
        <div class="modal-body">${body}</div>
        ${footer ? `<div class="modal-foot">${footer}</div>` : ''}
      </div>
    </div>`;
  document.body.style.overflow = 'hidden';
  const overlay = $('#modal-overlay');
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeModal();
  });
  $$('[data-close]', MODAL_ROOT).forEach((button) => button.addEventListener('click', closeModal));
  if (onMount) onMount(MODAL_ROOT);
}

function closeModal() {
  MODAL_ROOT.innerHTML = '';
  document.body.style.overflow = '';
}

function confirmDialog(title, message, confirmText = '确认', danger = false) {
  return new Promise((resolve) => {
    openModal({
      title,
      body: `<p style="font-size:13px;color:#475467;line-height:1.7">${esc(message)}</p>`,
      footer: `<button class="btn" data-close>取消</button>
               <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" id="confirm-yes">${esc(confirmText)}</button>`,
      onMount(root) {
        root.querySelector('#confirm-yes').addEventListener('click', () => {
          closeModal();
          resolve(true);
        });
        root.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => resolve(false)));
      },
    });
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && MODAL_ROOT.innerHTML) closeModal();
});

/* ------------------------------------------------------------------ 导航 */
function currentRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '');
  return NAV_ITEMS.some((item) => item.key === hash) ? hash : 'cases';
}

function renderNav() {
  const pending = state.bootstrap?.debts?.pending || 0;
  NAV.innerHTML = NAV_ITEMS.map((item) => {
    const count = item.key === 'debts' && pending
      ? `<span class="nav-count">${pending}</span>`
      : item.key === 'cases' && state.caseCount
        ? `<span class="nav-count">${state.caseCount}</span>`
        : item.key === 'records' && state.plans.length
          ? `<span class="nav-count">${state.plans.length}</span>`
          : '';
    return `<a class="nav-item ${state.route === item.key ? 'active' : ''}" href="#/${item.key}">
      ${ICONS[item.icon] || ''}<span class="nav-label">${item.label}</span>${count}
    </a>`;
  }).join('');
}

function renderTopbar() {
  const route = routes[state.route];
  const titleNode = $('#page-title');
  const subtitleNode = $('#page-subtitle');
  if (titleNode) titleNode.textContent = route?.title || '工作台';
  if (subtitleNode) subtitleNode.textContent = route?.subtitle || '三角债智能梳理与净额轧差';
  const date = state.bootstrap?.as_of_date || new Date().toISOString().slice(0, 10);
  const actions = [];
  if (state.route !== 'cases' && state.activeCase) {
    actions.push(`<a class="case-chip" href="#/cases" title="切换工作记录">
      <span class="case-chip-label">当前工作记录</span>
      <strong>${esc(state.activeCase.name)}</strong>
      <span class="case-chip-switch">切换</span>
    </a>`);
  }
  if (state.route === 'cases') {
    actions.push('<button class="btn btn-primary" data-action="new-case">＋ 新建工作记录</button>');
  } else if (state.route === 'dashboard') {
    actions.push('<button class="btn" data-action="add-debt">＋ 新增债务</button>');
    actions.push('<button class="btn btn-primary" data-action="run-netting">运行净额轧差</button>');
  } else if (state.route === 'debts') {
    actions.push('<button class="btn" data-action="add-entity">＋ 新增主体</button>');
    actions.push('<button class="btn btn-primary" data-action="add-debt">＋ 新增债务</button>');
  } else if (state.route === 'plan') {
    actions.push('<button class="btn" data-action="run-netting">重新计算</button>');
  } else if (state.route === 'records') {
    const latest = (state.plans || [])[0];
    actions.push('<button class="btn btn-primary" data-action="run-netting">＋ 开始新的核算</button>');
    if (latest) {
      actions.push(`<button class="btn" data-action="open-plan" data-id="${esc(latest.id)}">打开最新核算</button>`);
    }
  } else if (state.route === 'materials') {
    actions.push('<button class="btn" data-action="add-debt">手工录入债务</button>');
  }
  actions.push(`<span class="badge badge-navy">基准日 ${esc(date)}</span>`);
  TOPBAR.innerHTML = actions.join('');
}

/* ------------------------------------------------------------------ 数据 */
async function loadBootstrap() {
  const data = await api('/api/bootstrap');
  state.bootstrap = data;
  state.settings = data.settings;
  state.activeCase = data.active_case || null;
  state.caseCount = data.case_count || 1;
  renderNav();
  renderTopbar();
}

async function ensureBootstrap() {
  if (!state.bootstrap) await loadBootstrap();
}

async function loadEntities() {
  state.entities = (await api('/api/entities')).items || [];
}

async function loadDebts() {
  state.debts = (await api('/api/debts')).items || [];
}

async function loadCases() {
  state.cases = (await api('/api/cases')).items || [];
}

async function loadPlans() {
  state.plans = (await api('/api/plans')).items || [];
}

async function loadPlan() {
  try {
    state.plan = await api('/api/plans/latest');
  } catch (error) {
    state.plan = null;
  }
  await loadPlans();
}

async function loadGraph() {
  state.graph = await api(`/api/graph?ineligible=${state.graphIneligible ? 1 : 0}`);
  state.graphModel = null;
  state.graphActiveCycle = null;
  state.graphTransform = { x: 0, y: 0, k: 1 };
  const exists = state.graph.nodes?.some((node) => node.id === state.selectedNode);
  if (!exists) state.selectedNode = null;
}

async function loadMaterials() {
  state.materials = (await api('/api/materials')).items || [];
}

async function loadAudit() {
  state.audit = (await api('/api/audit?limit=200')).items || [];
}

async function refreshAfterMutation() {
  await loadBootstrap();
  if (['debts', 'materials', 'dashboard'].includes(state.route)) {
    await loadEntities();
    await loadDebts();
  }
  if (state.route === 'plan') await loadPlan();
  if (state.route === 'graph') await loadGraph();
  if (state.route === 'audit') await loadAudit();
  await renderView();
}

/* ------------------------------------------------------------------ 视图路由 */
const routes = {
  cases: {
    title: '工作记录',
    subtitle: '先选择一次历史工作记录，或新建一次；进入后所有模块只显示该记录的数据',
    load: async () => { if (!state.bootstrap) await loadBootstrap(); await loadCases(); },
    render: viewCases,
  },
  dashboard: {
    title: '工作台',
    subtitle: '三角债智能梳理与净额轧差',
    load: async () => { await ensureBootstrap(); await loadPlan(); },
    render: viewDashboard,
  },
  debts: {
    title: '债务台账',
    subtitle: '逐笔登记债权债务，由本体规则自动判定抵销资格',
    load: async () => { await ensureBootstrap(); await loadEntities(); await loadDebts(); },
    render: viewDebts,
    after: bindDebtFilters,
  },
  materials: {
    title: '材料抽取',
    subtitle: '合同、欠条、对账函 → 结构化债务要素 → 人工复核入池',
    load: async () => { await ensureBootstrap(); await loadEntities(); await loadDebts(); await loadMaterials(); },
    render: viewMaterials,
    after: bindMaterialEvents,
  },
  graph: {
    title: '债务图谱',
    subtitle: '以主体为节点、债务为有向边，检索环路与枢纽主体',
    load: async () => { await ensureBootstrap(); await loadGraph(); },
    render: viewGraph,
    after: drawGraph,
  },
  plan: {
    title: '轧差方案',
    subtitle: '净头寸汇总与最小交易笔数清偿清单',
    load: async () => {
      await ensureBootstrap();
      if (state.pendingPlanId) {
        state.plan = await api(`/api/plans/${state.pendingPlanId}`);
        state.pendingPlanId = null;
      } else {
        await loadPlan();
      }
    },
    render: viewPlan,
  },
  records: {
    title: '核算记录',
    subtitle: '每次债务核算都保留当时的债务快照，按编号持续累积',
    load: async () => { await ensureBootstrap(); await loadPlans(); },
    render: viewRecords,
  },
  audit: {
    title: '审计留痕',
    subtitle: '规则命中、方案生成与数据变更的可追溯记录',
    load: async () => { await ensureBootstrap(); await loadAudit(); },
    render: viewAudit,
  },
  settings: {
    title: '系统设置',
    subtitle: '基准日、求解参数、本体规则与线上模型配置',
    load: ensureBootstrap,
    render: viewSettings,
    after: bindSettingsEvents,
  },
};

async function renderView() {
  const route = currentRoute();
  state.route = route;
  renderNav();
  renderTopbar();
  VIEW.innerHTML = skeleton();
  try {
    await routes[route].load();
    renderNav();
    renderTopbar();
    VIEW.innerHTML = routes[route].render();
    if (routes[route].after) routes[route].after();
  } catch (error) {
    VIEW.innerHTML = `<div class="card">${emptyState('!', '页面加载失败', error.message,
      '<button class="btn" data-action="rerender">重试</button>')}</div>`;
    toast(error.message, 'err');
  }
}

/* ------------------------------------------------------------------ 工作记录 */
function viewCases() {
  const cases = state.cases || [];
  const activeId = state.activeCase?.id;
  const cards = cases.map((item) => {
    const latest = item.latest_plan;
    const summary = latest?.summary || {};
    return `<button class="case-card ${item.active ? 'case-card-active' : ''}" data-action="open-case" data-id="${esc(item.id)}">
      <div class="case-card-top">
        <span class="record-seq">#${esc(item.seq)}</span>
        <div class="case-card-title">
          <h3>${esc(item.name)}</h3>
          <p>${fmtDateTime(item.created_at)}${item.updated_at && item.updated_at !== item.created_at ? ` · 更新 ${fmtDateTime(item.updated_at)}` : ''}</p>
        </div>
        ${item.active ? '<span class="badge badge-ok">当前</span>' : '<span class="case-open">打开 →</span>'}
      </div>
      <div class="case-card-stats">
        <span><strong>${item.debt_count ?? 0}</strong> 笔债务</span>
        <span><strong>${item.entity_count ?? 0}</strong> 个主体</span>
        <span><strong>${item.plan_count ?? 0}</strong> 次核算</span>
        <span><strong>${item.material_count ?? 0}</strong> 份材料</span>
      </div>
      <div class="case-card-latest">
        ${latest
          ? `最近核算：<strong>${esc(latest.name || `核算 #${latest.seq}`)}</strong> · ${summary.transaction_count ?? '—'} 笔付款 · ¥${fmtCents(summary.transaction_amount_cents)} · ${summary.mode === 'pure' ? '纯数学口径' : '法律合规口径'}`
          : '还没有核算记录，进入后可以开始第一次核算。'}
      </div>
    </button>`;
  }).join('');

  return `<section class="card">
    <div class="card-head">
      <div><h3>历次工作记录</h3><p>每次债务清理是一个独立工作记录；打开后，工作台、台账、材料、图谱、核算记录都只显示这一条记录的数据</p></div>
      <div class="row">
        <button class="btn btn-primary" data-action="new-case">＋ 新建工作记录</button>
        <button class="btn btn-sm btn-ghost" data-action="rerender">刷新</button>
      </div>
    </div>
    <div class="card-body">
      ${cases.length ? `<div class="case-grid">${cards}</div>` : `<div class="empty" style="padding:44px 10px">
        <div class="empty-icon">＋</div>
        <p>还没有工作记录。新建一条，开始第一次债务清理。</p>
        <button class="btn btn-primary" data-action="new-case">新建第一条工作记录</button>
      </div>`}
      <p class="tiny muted" style="margin-top:16px">提示：工作记录之间完全独立，删除或清空当前记录不会影响其他记录。当前选中的记录：<b>${esc(state.activeCase?.name || '—')}</b></p>
    </div>
  </section>`;
}

function resetCaseState() {
  state.bootstrap = null;
  state.plan = null;
  state.plans = [];
  state.debts = [];
  state.entities = [];
  state.materials = [];
  state.audit = [];
  state.comparison = null;
  state.comparePlans = null;
  state.planDetailOpen = false;
  state.graphModel = null;
  state.selectedNode = null;
  state.graphActiveCycle = null;
  state.filters = { q: '', status: '', group: '' };
  state.extraction = null;
}

async function openCase(caseId) {
  try {
    if (state.activeCase?.id !== caseId) {
      await api(`/api/cases/${caseId}/activate`, { method: 'POST', body: '{}' });
      resetCaseState();
      await loadBootstrap();
    }
    if (currentRoute() === 'dashboard') {
      await renderView();
    } else {
      window.location.hash = '#/dashboard';
    }
  } catch (error) {
    toast(error.message, 'err');
  }
}

function showCaseForm() {
  openModal({
    title: '新建工作记录',
    subtitle: '每条工作记录有独立的债务台账、材料、图谱和核算历史',
    body: `<form id="case-form" class="stack">
      <div class="field">
        <label>工作记录名称</label>
        <input name="name" maxlength="80" placeholder="例如：2026 年华东三角债清理">
        <p class="tiny muted">留空则自动命名为“工作记录 #N”。</p>
      </div>
      <label class="check-row" style="display:flex;gap:8px;align-items:flex-start">
        <input type="checkbox" name="with_demo" style="margin-top:3px">
        <span><b>载入示例数据</b><br><span class="tiny muted">建立 6 个主体、11 笔债务，并自动生成一次法律口径核算；适合先体验。</span></span>
      </label>
    </form>`,
    footer: `<button class="btn" data-close>取消</button>
             <button class="btn btn-primary" id="case-create-submit">创建工作记录</button>`,
    onMount(root) {
      root.querySelector('#case-create-submit').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        const form = root.querySelector('#case-form');
        setBusy(button, true);
        try {
          await api('/api/cases', {
            method: 'POST',
            body: JSON.stringify({
              name: form.querySelector('[name=name]').value,
              with_demo: form.querySelector('[name=with_demo]').checked,
            }),
          });
          closeModal();
          resetCaseState();
          await loadBootstrap();
          toast('工作记录已建立。');
          window.location.hash = '#/dashboard';
        } catch (error) {
          toast(error.message, 'err');
        } finally {
          setBusy(button, false);
        }
      });
    },
  });
}

/* ------------------------------------------------------------------ 工作台 */
function viewDashboard() {
  const data = state.bootstrap;
  if (!data) return '';
  const debts = data.debts;
  const amount = data.amount;
  const latest = data.latest_plan;
  const planSummary = latest?.summary;
  const total = Math.max(1, debts.total);
  const composition = `
    <div class="composition">
      <i class="seg-ok" style="width:${(debts.eligible / total) * 100}%"></i>
      <i class="seg-warn" style="width:${(debts.pending / total) * 100}%"></i>
      <i class="seg-muted" style="width:${(debts.excluded / total) * 100}%"></i>
    </div>
    <div class="composition-legend">
      <span><i class="swatch seg-ok"></i>可抵销 ${debts.eligible} 笔</span>
      <span><i class="swatch seg-warn"></i>待复核 ${debts.pending} 笔</span>
      <span><i class="swatch seg-muted"></i>不可抵销 ${debts.excluded} 笔</span>
    </div>`;

  const hasData = data.entities > 0 || debts.total > 0;
  const heroActions = hasData
    ? `<button class="btn btn-primary" data-action="run-netting">运行净额轧差</button>
       <a class="btn btn-ghost" href="#/materials">上传材料抽取</a>`
    : `<button class="btn btn-primary" data-action="seed-demo">载入示例数据</button>
       <a class="btn btn-ghost" href="#/debts">手工录入</a>`;

  const txPreview = planSummary && latest
    ? `<div class="plan-mini">${state.plan?.transactions?.slice(0, 5).map((tx) => `
        <div class="tx-line"><span class="tx-seq">${tx.seq}</span>
          <span class="tx-parties"><b>${esc(truncate(tx.from_name, 12))}</b> → <b>${esc(truncate(tx.to_name, 12))}</b></span>
          <span class="tx-amount">¥${fmtCents(tx.amount_cents)}</span></div>`).join('') || ''}
        ${planSummary.transaction_count > 5 ? `<p class="tiny muted" style="margin-top:8px">另有 ${planSummary.transaction_count - 5} 笔，详见方案页</p>` : ''}
      </div>`
    : `<div class="empty" style="padding:26px 10px"><div class="empty-icon">↻</div>
        <p>还没有生成过清偿方案。运行轧差后，这里会出现最少交易笔数的清偿清单。</p></div>`;

  const rules = (data.rules || []).slice(0, 4).map((rule) => `
    <div class="rule-mini-item">
      <span class="rule-id">${esc(rule.id)}</span>
      <div><strong>${esc(rule.name)}</strong><span>${esc(rule.body)}</span></div>
      <span style="margin-left:auto">${severityBadge(rule.severity)}</span>
    </div>`).join('');

  const audits = (data.recent_audit || []).slice(0, 5).map((item) => `
    <li><span class="time">${fmtDateTime(item.ts)}</span>
        <span class="what">${esc(ACTION_LABELS[item.action] || item.action)}</span></li>`).join('');

  return `
  <div class="dashboard-case">当前工作记录：<strong>${esc(state.activeCase?.name || '—')}</strong> <a href="#/cases">切换工作记录</a></div>
  <section class="hero">
    <div class="hero-copy">
      <div class="eyebrow">LOCAL-FIRST · 规则与金额不出本机</div>
      <h2>把环环相扣的三角债，拆成一张可执行的清偿清单。</h2>
      <p>本体规则判定可抵销性，债务图谱汇总净头寸，精确求解器以最少交易笔数完成全额结清；每一笔结论都可回溯到规则与原始债务。</p>
      <div class="hero-actions">${heroActions}</div>
    </div>
    <div class="hero-stats">
      <div class="hero-stat"><span>参与主体</span><strong>${data.entities}<em>个</em></strong></div>
      <div class="hero-stat"><span>纳入轧差金额</span><strong>${fmtCompact(amount.eligible_cents)}</strong></div>
      <div class="hero-stat"><span>上轮最少交易</span><strong>${planSummary ? planSummary.transaction_count : '—'}<em>${planSummary ? '笔' : ''}</em></strong></div>
    </div>
  </section>

  <div class="kpi-grid">
    <div class="kpi kpi-navy"><div class="kpi-label">台账债务</div><div class="kpi-value">${debts.total}<small>笔</small></div><div class="kpi-foot">债务总额 ¥${fmtCompact(amount.total_cents)}</div></div>
    <div class="kpi kpi-green"><div class="kpi-label">可抵销债务</div><div class="kpi-value">${debts.eligible}<small>笔</small></div><div class="kpi-foot">金额 ¥${fmtCompact(amount.eligible_cents)}</div></div>
    <div class="kpi kpi-warn"><div class="kpi-label">未入池债务</div><div class="kpi-value">${debts.excluded + debts.pending}<small>笔</small></div><div class="kpi-foot">不可抵销 ${debts.excluded} 笔 · 待复核 ${debts.pending} 笔</div></div>
    <div class="kpi"><div class="kpi-label">净债务人 / 净债权人</div><div class="kpi-value">${planSummary ? planSummary.debtor_count : 0}<small>/ ${planSummary ? planSummary.creditor_count : 0}</small></div><div class="kpi-foot">${planSummary ? `头寸归零出局 ${planSummary.zero_out_count} 个` : '尚无方案'}</div></div>
  </div>

  ${hasData ? '' : `<div class="card" style="margin-top:18px">${emptyState('＋', '台账还没有数据', '可以从示例数据开始体验完整流程，也可以直接手工录入债务。',
    '<div class="row" style="justify-content:center"><button class="btn btn-primary" data-action="seed-demo">载入示例数据</button><button class="btn" data-action="add-debt">手工新增债务</button></div>')}</div>`}

  <div class="dashboard-grid">
    <section class="card">
      <div class="card-head"><div><h3>最近清偿方案</h3><p>${latest ? `生成于 ${fmtDateTime(latest.created_at)} · 共 ${planSummary.group_count} 个顺位分组` : '尚未生成方案'}</p></div>
        ${latest ? '<a class="btn btn-sm" href="#/plan">查看完整方案</a>' : ''}</div>
      <div class="card-body">
        ${latest ? `<div class="row" style="margin-bottom:10px">
          <span class="badge badge-navy">${esc(planSummary.name || `核算 #${planSummary.seq || '—'}`)}</span>
          <span class="badge badge-ok">${planSummary.transaction_count} 笔交易</span>
          <span class="badge ${planSummary.mode === 'pure' ? 'badge-warn' : 'badge-info'}">${esc(planSummary.mode_label || '法律合规口径')}</span>
          <span class="badge badge-info">${planSummary.optimality === 'proven' ? '已证明最优' : '启发式近优'}</span>
          <span class="badge badge-neutral">¥${fmtCents(planSummary.transaction_amount_cents)}</span></div>` : ''}
        ${txPreview}
      </div>
    </section>

    <section class="card">
      <div class="card-head"><div><h3>本体规则底座</h3><p>${data.ontology.rules} 条 SWRL 规则 · ${data.ontology.classes} 个实体类</p></div>
        <a class="btn btn-sm" href="#/settings">规则详情</a></div>
      <div class="card-body rule-mini">${rules}</div>
    </section>
  </div>

  <div class="dashboard-grid">
    <section class="card">
      <div class="card-head"><div><h3>债务构成</h3><p>抵销资格由本地本体规则实时判定</p></div></div>
      <div class="card-body">${composition}</div>
    </section>
    <section class="card">
      <div class="card-head"><div><h3>最近操作</h3><p>规则命中、方案与数据变更均留痕</p></div>
        <a class="btn btn-sm" href="#/audit">全部记录</a></div>
      <div class="card-body">
        ${audits ? `<ul class="audit-mini">${audits}</ul>` : '<p class="tiny muted">暂无操作记录</p>'}
      </div>
    </section>
  </div>

  <div class="notice notice-warn" style="margin-top:18px">
    <span>⚖</span><div><strong>法律边界：</strong>本系统输出的是多方协商一致的清偿安排建议，不是法定自动抵销。落地前须由全部参与方签署多方债务抵销及清偿协议，并经法务终审。</div>
  </div>`;
}

/* ------------------------------------------------------------------ 债务台账 */
function filteredDebts() {
  const { q, status, group } = state.filters;
  const keyword = q.trim();
  return state.debts.filter((debt) => {
    if (status && debt.status !== status) return false;
    if (group && debt.priority_group !== group) return false;
    if (keyword) {
      const haystack = `${debt.debtor_name}${debt.creditor_name}${debt.note}${debt.id}`;
      if (!haystack.includes(keyword)) return false;
    }
    return true;
  });
}

function debtRowsHtml() {
  const debts = filteredDebts();
  if (!debts.length) {
    return `<tr><td colspan="8">${emptyState('—', '没有符合条件的债务', '试试调整筛选条件，或新增一笔债务。')}</td></tr>`;
  }
  return debts.map((debt) => {
    const flags = [
      debt.disputed ? '<span class="chip chip-danger">争议</span>' : '',
      debt.frozen ? '<span class="chip chip-danger">查封冻结</span>' : '',
      debt.no_setoff_clause ? '<span class="chip chip-warn">禁止抵销</span>' : '',
      debt.source === 'ai' ? '<span class="chip chip-info">AI抽取</span>' : '',
    ].join('');
    const reasons = debt.eligibility?.blocking?.length || debt.eligibility?.review?.length
      ? `<span class="tiny muted" style="display:block;margin-top:3px">${esc((debt.eligibility.blocking[0] || debt.eligibility.review[0] || {}).name || '')}</span>`
      : '';
    const pendingActions = debt.status === 'pending'
      ? `<button class="btn btn-sm btn-primary" data-action="confirm-debt" data-id="${debt.id}">确认</button>
         <button class="btn btn-sm" data-action="reject-debt" data-id="${debt.id}">排除</button>`
      : '';
    return `<tr>
      <td><span class="mono">${esc(shortId(debt.id))}</span></td>
      <td>
        <div class="party-cell">
          <span class="label">债务人 → 债权人</span>
          <span class="name">${esc(debt.debtor_name)} <span class="dir">→</span> ${esc(debt.creditor_name)}</span>
          <span class="flags">${flags}</span>
        </div>
      </td>
      <td class="num strong">¥${fmtCents(debt.amount_cents)}</td>
      <td>${fmtDate(debt.due_date)}</td>
      <td><span class="badge badge-neutral">${esc(debt.priority_label)}</span></td>
      <td>${statusBadge(debt.status)}</td>
      <td>${badgeEligibility(debt)}${reasons}</td>
      <td class="nowrap">
        <button class="btn btn-sm btn-ghost" data-action="trace" data-id="${debt.id}">推理</button>
        <button class="btn btn-sm btn-ghost" data-action="edit-debt" data-id="${debt.id}">编辑</button>
        ${pendingActions}
        <button class="btn btn-sm btn-ghost" data-action="delete-debt" data-id="${debt.id}" style="color:#b42318">删除</button>
      </td>
    </tr>`;
  }).join('');
}

function entitiesCardHtml() {
  return `<section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>参与主体</h3><p>${state.entities.length} 个主体 · 可动用资金用于资金约束与分期提示</p></div>
      <button class="btn btn-sm" data-action="add-entity">＋ 新增主体</button></div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>主体名称</th><th>统一社会信用代码</th><th>经营状态</th><th class="num">可动用资金</th><th>风险标记</th><th>操作</th></tr></thead>
        <tbody>
          ${state.entities.length ? state.entities.map((entity) => `<tr>
            <td class="strong">${esc(entity.name)}</td>
            <td class="mono">${esc(entity.credit_code || '—')}</td>
            <td>${esc(entity.status || '—')}</td>
            <td class="num">¥${fmtCents(entity.available_cash_cents)}</td>
            <td>${entity.litigation ? '<span class="chip chip-warn">涉诉</span>' : ''} ${entity.enforced ? '<span class="chip chip-danger">被执行</span>' : ''} ${!entity.litigation && !entity.enforced ? '<span class="tiny muted">—</span>' : ''}</td>
            <td class="nowrap">
              <button class="btn btn-sm btn-ghost" data-action="edit-entity" data-id="${entity.id}">编辑</button>
              <button class="btn btn-sm btn-ghost" data-action="delete-entity" data-id="${entity.id}" style="color:#b42318">删除</button>
            </td>
          </tr>`).join('') : '<tr><td colspan="6" class="tiny muted" style="padding:16px">还没有登记主体。</td></tr>'}
        </tbody>
      </table>
    </div>
  </section>`;
}

function viewDebts() {
  const debts = state.debts;
  const eligible = debts.filter((item) => item.eligibility?.eligible && item.status === 'confirmed').length;
  const pending = debts.filter((item) => item.status === 'pending').length;
  const filtered = filteredDebts();
  return `
  <div class="kpi-grid" style="margin-bottom:18px">
    <div class="kpi"><div class="kpi-label">台账债务</div><div class="kpi-value">${debts.length}<small>笔</small></div><div class="kpi-foot">含全部确认状态</div></div>
    <div class="kpi kpi-green"><div class="kpi-label">可参与轧差</div><div class="kpi-value">${eligible}<small>笔</small></div><div class="kpi-foot">已确认且通过本体规则</div></div>
    <div class="kpi kpi-warn"><div class="kpi-label">待人工复核</div><div class="kpi-value">${pending}<small>笔</small></div><div class="kpi-foot">AI 抽取或字段异常</div></div>
    <div class="kpi kpi-navy"><div class="kpi-label">规则阻断</div><div class="kpi-value">${debts.filter((item) => item.eligibility?.blocking?.length).length}<small>笔</small></div><div class="kpi-foot">争议 / 查封 / 未到期 / 禁止抵销</div></div>
  </div>

  <section class="card" id="debt-table-card">
    <div class="card-head"><div><h3>债务清单</h3><p id="debt-count">共 ${filtered.length} 笔 · 金额合计 ¥${fmtCents(filtered.reduce((sum, item) => sum + item.amount_cents, 0))}</p></div>
      <div class="row"><span class="badge badge-info">规则推理实时生效</span></div>
    </div>
    <div class="toolbar">
      <div class="search-box"><input id="debt-search" placeholder="搜索主体、备注或编号" value="${esc(state.filters.q)}"></div>
      <select id="debt-status" class="field-inline">
        <option value="">全部确认状态</option>
        ${['confirmed', 'pending', 'rejected'].map((value) => `<option value="${value}" ${state.filters.status === value ? 'selected' : ''}>${STATUS_LABELS[value]}</option>`).join('')}
      </select>
      <select id="debt-group" class="field-inline">
        <option value="">全部顺位分组</option>
        ${Object.entries(GROUP_LABELS).map(([value, label]) => `<option value="${value}" ${state.filters.group === value ? 'selected' : ''}>${label}</option>`).join('')}
      </select>
      <div class="spacer"></div>
      <button class="btn btn-sm" data-action="recheck">重新校验</button>
      <button class="btn btn-sm" data-action="import-debts">批量导入</button>
      <button class="btn btn-sm btn-primary" data-action="add-debt">＋ 新增债务</button>
    </div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr>
          <th>编号</th><th>债务关系</th><th class="num">金额</th><th>到期日</th><th>顺位分组</th><th>确认</th><th>抵销资格</th><th>操作</th>
        </tr></thead>
        <tbody id="debt-tbody">${debtRowsHtml()}</tbody>
      </table>
    </div>
  </section>
  ${entitiesCardHtml()}`;
}

function refreshDebtTable() {
  const table = $('#debt-tbody');
  if (table) table.innerHTML = debtRowsHtml();
  const count = $('#debt-count');
  if (count) {
    const debts = filteredDebts();
    count.textContent = `共 ${debts.length} 笔 · 金额合计 ¥${fmtCents(debts.reduce((sum, item) => sum + item.amount_cents, 0))}`;
  }
}

function bindDebtFilters() {
  const search = $('#debt-search');
  const status = $('#debt-status');
  const group = $('#debt-group');
  if (search) search.addEventListener('input', () => {
    state.filters.q = search.value;
    refreshDebtTable();
  });
  if (status) status.addEventListener('change', () => {
    state.filters.status = status.value;
    refreshDebtTable();
  });
  if (group) group.addEventListener('change', () => {
    state.filters.group = group.value;
    refreshDebtTable();
  });
}

/* ------------------------------------------------------------------ 债务弹窗 */
function entityOptions(selected) {
  return `<option value="">请选择主体</option>` + state.entities.map((entity) =>
    `<option value="${entity.id}" ${selected === entity.id ? 'selected' : ''}>${esc(entity.name)}</option>`
  ).join('');
}

/* ------------------------------------------------------------------ 批量导入 */
function parseDelimitedLine(line, delimiter) {
  const cells = [];
  let current = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      if (quoted && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === delimiter && !quoted) {
      cells.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function parseDebtImportText(text) {
  const raw = (text || '').replace(/^\uFEFF/, '').trim();
  if (!raw) return [];
  if (raw.startsWith('[') || raw.startsWith('{')) {
    const data = JSON.parse(raw);
    const rows = Array.isArray(data) ? data : data.rows;
    if (!Array.isArray(rows)) throw new Error('JSON 中缺少 rows 数组');
    return rows;
  }
  const lines = raw.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return [];
  const delimiter = (lines[0].match(/\t/g) || []).length > (lines[0].match(/,/g) || []).length ? '\t' : ',';
  const headerCells = parseDelimitedLine(lines[0], delimiter);
  const aliases = {
    '债务人': 'debtor_name', '债务人名称': 'debtor_name', 'debtor': 'debtor_name', 'debtor_name': 'debtor_name',
    '债权人': 'creditor_name', '债权人名称': 'creditor_name', 'creditor': 'creditor_name', 'creditor_name': 'creditor_name',
    '金额': 'amount', '债务金额': 'amount', 'amount': 'amount',
    '本金': 'principal', 'principal': 'principal', '利息': 'interest', 'interest': 'interest',
    '到期日': 'due_date', '到期时间': 'due_date', 'due_date': 'due_date',
    '争议': 'disputed', '是否存在争议': 'disputed', 'disputed': 'disputed',
    '查封': 'frozen', '查封冻结': 'frozen', '是否被查封冻结': 'frozen', 'frozen': 'frozen',
    '禁止抵销': 'no_setoff_clause', '是否约定禁止抵销': 'no_setoff_clause', 'no_setoff_clause': 'no_setoff_clause',
    '分组': 'priority_group', '顺位分组': 'priority_group', 'priority_group': 'priority_group',
    '状态': 'status', 'status': 'status', '备注': 'note', 'note': 'note',
  };
  const hasHeader = headerCells.some((cell) => aliases[cell.trim()]);
  const headers = hasHeader ? headerCells.map((cell) => aliases[cell.trim()] || '') : null;
  const dataLines = hasHeader ? lines.slice(1) : lines;
  const rows = [];
  dataLines.forEach((line, index) => {
    const cells = parseDelimitedLine(line, delimiter);
    if (!cells.some((cell) => cell !== '')) return;
    if (headers) {
      const row = {};
      headers.forEach((key, column) => {
        if (key) row[key] = cells[column] ?? '';
      });
      row._line = index + (hasHeader ? 2 : 1);
      rows.push(row);
    } else {
      rows.push({
        debtor_name: cells[0] || '',
        creditor_name: cells[1] || '',
        amount: cells[2] || '',
        due_date: cells[3] || '',
        note: cells[4] || '',
        _line: index + 1,
      });
    }
  });
  return rows;
}

function showDebtImport() {
  openModal({
    title: '批量导入债务',
    subtitle: '支持 CSV、TSV、JSON；每行一笔债务，金额单位与台账一致',
    wide: true,
    body: `<div class="stack">
      <div class="notice notice-info"><span>i</span><div>
        表头支持：<b>债务人、债权人、金额、到期日、争议、查封、禁止抵销、分组、备注、状态</b>。
        没有表头时按“债务人、债权人、金额、到期日、备注”的顺序读取。债务人或债权人不存在时会自动建立主体。
      </div></div>
      <div class="row">
        <label class="btn btn-sm" style="cursor:pointer">选择 CSV / JSON 文件
          <input type="file" id="debt-import-file" accept=".csv,.tsv,.txt,.json" hidden>
        </label>
        <button class="btn btn-sm" data-action="load-complex-debts">填入复杂示例（28 笔）</button>
        <span class="tiny muted">示例：5 个主体、28 笔欠款，应化简为 2 笔付款</span>
      </div>
      <div class="field">
        <label>待导入数据</label>
        <textarea id="debt-import-text" style="min-height:300px" placeholder="债务人,债权人,金额,到期日,争议,查封,禁止抵销,分组,备注&#10;A公司,B公司,500000,2026-01-01,否,否,否,ordinary,货款"></textarea>
      </div>
      <p class="tiny muted">金额可写 500000、50万、500000元；日期支持 2026-01-01 或 2026年1月1日；是否字段支持 是/否、true/false。</p>
    </div>`,
    footer: `<button class="btn" data-close>取消</button>
             <button class="btn btn-primary" id="debt-import-submit">开始导入</button>`,
    onMount(root) {
      const textarea = root.querySelector('#debt-import-text');
      const fileInput = root.querySelector('#debt-import-file');
      fileInput.addEventListener('change', async () => {
        const file = fileInput.files?.[0];
        if (!file) return;
        textarea.value = await file.text();
      });
      root.querySelector('#debt-import-submit').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        let rows;
        try {
          rows = parseDebtImportText(textarea.value);
        } catch (error) {
          toast(`数据格式错误：${error.message}`, 'err');
          return;
        }
        if (!rows.length) {
          toast('没有可导入的行，请粘贴数据或选择文件。', 'warn');
          return;
        }
        setBusy(button, true);
        try {
          const result = await api('/api/debts/import', {
            method: 'POST',
            body: JSON.stringify({ rows }),
          });
          closeModal();
          toast(`已导入 ${result.created} 笔债务${result.errors.length ? `，${result.errors.length} 行失败` : ''}。`);
          if (result.errors.length) {
            openModal({
              title: '部分行未导入',
              body: `<div class="table-wrap" style="border:1px solid #e2e8f0;border-radius:10px"><table class="data">
                <thead><tr><th>行号</th><th>原因</th></tr></thead>
                <tbody>${result.errors.map((item) => `<tr><td>${item.row}</td><td class="tiny">${esc(item.error)}</td></tr>`).join('')}</tbody>
              </table></div>`,
              footer: '<button class="btn" data-close>知道了</button>',
            });
          }
          await refreshAfterMutation();
        } catch (error) {
          toast(error.message, 'err');
        } finally {
          setBusy(button, false);
        }
      });
    },
  });
}

async function showDebtForm(debt = null) {
  if (!state.entities.length) {
    try {
      await loadEntities();
    } catch (error) {
      toast(error.message, 'err');
      return;
    }
  }
  if (!state.entities.length) {
    openModal({
      title: '需要先建立参与主体',
      body: `<p style="font-size:13px;line-height:1.7;color:#475467">债务必须指向两个不同的主体。请先在台账中新增债务人、债权人，再登记债务。</p>`,
      footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" data-action="add-entity">新增主体</button>`,
    });
    return;
  }
  const editing = Boolean(debt);
  const body = `
    <form id="debt-form" class="form-grid">
      <div class="field"><label>债务人</label><select name="debtor_id" required>${entityOptions(debt?.debtor_id)}</select></div>
      <div class="field"><label>债权人</label><select name="creditor_id" required>${entityOptions(debt?.creditor_id)}</select></div>
      <div class="field"><label>本金（元）</label><input name="principal" type="number" min="0" step="0.01" value="${debt ? debt.principal : ''}" placeholder="0.00"></div>
      <div class="field"><label>利息（元）</label><input name="interest" type="number" min="0" step="0.01" value="${debt ? debt.interest : '0'}" placeholder="0.00"></div>
      <div class="field"><label>债务总额（元）</label><input name="amount" type="number" min="0" step="0.01" value="${debt ? debt.amount : ''}" placeholder="留空则按本金 + 利息计算"><div class="hint">净额轧差以该金额为准</div></div>
      <div class="field"><label>到期日</label><input name="due_date" type="date" value="${debt?.due_date || ''}"><div class="hint">晚于基准日将被判定为未到期</div></div>
      <div class="field"><label>债权顺位分组</label><select name="priority_group">
        ${Object.entries(GROUP_LABELS).map(([value, label]) => `<option value="${value}" ${debt?.priority_group === value ? 'selected' : ''}>${label}</option>`).join('')}
      </select><div class="hint">优先顺位分组独立计算，不与普通债权混算</div></div>
      <div class="field"><label>备注</label><input name="note" type="text" value="${esc(debt?.note || '')}" placeholder="基础交易、材料出处等"></div>
      <div class="span-2">
        <label class="check"><input type="checkbox" name="disputed" ${debt?.disputed ? 'checked' : ''}><span>存在争议<small>金额或事实有争议时阻断抵销</small></span></label>
      </div>
      <div class="span-2">
        <label class="check"><input type="checkbox" name="frozen" ${debt?.frozen ? 'checked' : ''}><span>被查封 / 冻结<small>处分受限，阻断抵销</small></span></label>
      </div>
      <div class="span-2">
        <label class="check"><input type="checkbox" name="no_setoff_clause" ${debt?.no_setoff_clause ? 'checked' : ''}><span>合同约定禁止抵销<small>尊重意思自治，阻断抵销</small></span></label>
      </div>
    </form>`;
  openModal({
    title: editing ? '编辑债务' : '新增债务',
    subtitle: editing ? `${debt.debtor_name} → ${debt.creditor_name}` : '录入后将立即执行本体规则推理',
    body,
    footer: `<button class="btn" data-close>取消</button>
             <button class="btn btn-primary" type="submit" form="debt-form">${editing ? '保存修改' : '新增并推理'}</button>`,
    wide: true,
    onMount(root) {
      const form = root.querySelector('#debt-form');
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submit = root.querySelector('[form="debt-form"]');
        setBusy(submit, true);
        try {
          const payload = {
            debtor_id: form.debtor_id.value,
            creditor_id: form.creditor_id.value,
            principal: Number(form.principal.value || 0),
            interest: Number(form.interest.value || 0),
            due_date: form.due_date.value,
            priority_group: form.priority_group.value,
            note: form.note.value,
            disputed: form.disputed.checked,
            frozen: form.frozen.checked,
            no_setoff_clause: form.no_setoff_clause.checked,
          };
          if (form.amount.value) payload.amount = Number(form.amount.value);
          if (editing) await api(`/api/debts/${debt.id}`, { method: 'PUT', body: JSON.stringify(payload) });
          else await api('/api/debts', { method: 'POST', body: JSON.stringify(payload) });
          closeModal();
          toast(editing ? '债务已更新，规则结论已刷新。' : '债务已登记，并完成本体规则推理。');
          await refreshAfterMutation();
        } catch (error) {
          toast(error.message, 'err');
        } finally {
          setBusy(submit, false);
        }
      });
    },
  });
}

function showEntityForm(entity = null) {
  const editing = Boolean(entity);
  const body = `
    <form id="entity-form" class="form-grid">
      <div class="field span-2"><label>主体名称</label><input name="name" required value="${esc(entity?.name || '')}" placeholder="企业或个人全称"></div>
      <div class="field"><label>统一社会信用代码</label><input name="credit_code" value="${esc(entity?.credit_code || '')}"></div>
      <div class="field"><label>经营状态</label><input name="status" value="${esc(entity?.status || '正常经营')}"></div>
      <div class="field"><label>可动用资金（元）</label><input name="available_cash" type="number" min="0" step="0.01" value="${entity ? entity.available_cash : '0'}"><div class="hint">用于资金约束提示与分期建议</div></div>
      <div class="field"><label>备注</label><input name="note" value="${esc(entity?.note || '')}"></div>
      <label class="check span-2"><input type="checkbox" name="litigation" ${entity?.litigation ? 'checked' : ''}><span>涉诉标记<small>仅作风险提示，不自动阻断抵销</small></span></label>
      <label class="check span-2"><input type="checkbox" name="enforced" ${entity?.enforced ? 'checked' : ''}><span>被执行标记<small>仅作风险提示，不自动阻断抵销</small></span></label>
    </form>`;
  openModal({
    title: editing ? '编辑主体' : '新增主体',
    subtitle: '主体信息只保存在本地数据库',
    body,
    footer: `<button class="btn" data-close>取消</button><button class="btn btn-primary" type="submit" form="entity-form">${editing ? '保存' : '新增主体'}</button>`,
    onMount(root) {
      const form = root.querySelector('#entity-form');
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submit = root.querySelector('[form="entity-form"]');
        setBusy(submit, true);
        try {
          const payload = {
            name: form.name.value,
            credit_code: form.credit_code.value,
            status: form.status.value,
            available_cash: Number(form.available_cash.value || 0),
            note: form.note.value,
            litigation: form.litigation.checked,
            enforced: form.enforced.checked,
          };
          if (editing) await api(`/api/entities/${entity.id}`, { method: 'PUT', body: JSON.stringify(payload) });
          else await api('/api/entities', { method: 'POST', body: JSON.stringify(payload) });
          closeModal();
          toast(editing ? '主体信息已更新。' : '主体已新增。');
          await refreshAfterMutation();
        } catch (error) {
          toast(error.message, 'err');
        } finally {
          setBusy(submit, false);
        }
      });
    },
  });
}

function showTrace(debtId) {
  const debt = state.debts.find((item) => item.id === debtId);
  if (!debt) return;
  const evaluation = debt.eligibility || {};
  const trace = evaluation.trace || [];
  const blocking = evaluation.blocking || [];
  const review = evaluation.review || [];
  const body = `
    <div class="row" style="margin-bottom:12px">
      ${badgeEligibility(debt)} ${statusBadge(debt.status)}
      <span class="badge badge-neutral">${esc(debt.priority_label)}</span>
      <span class="badge badge-navy">基准日 ${esc(state.bootstrap?.as_of_date || '')}</span>
    </div>
    <p style="font-size:12.5px;color:#475467;margin-bottom:14px">
      ${esc(debt.debtor_name)} → ${esc(debt.creditor_name)}，金额 <b>¥${fmtCents(debt.amount_cents)}</b>，到期日 ${fmtDate(debt.due_date)}。
      ${evaluation.eligible ? '本笔债务通过全部本体规则，可进入所属顺位分组的净额轧差。' : '本笔债务未通过本体校验，不进入自动轧差池。'}
    </p>
    ${blocking.length || review.length ? `<div class="notice ${blocking.length ? 'notice-danger' : 'notice-warn'}" style="margin-bottom:14px">
      <span>${blocking.length ? '⛔' : '⚠'}</span><div>
      ${blocking.length ? `<strong>阻断原因：</strong>${esc(blocking.map((item) => item.message).join('；'))}<br>` : ''}
      ${review.length ? `<strong>复核原因：</strong>${esc(review.map((item) => item.message).join('；'))}` : ''}
      </div></div>` : ''}
    <div class="mini-title">SWRL 规则命中明细（${trace.length} 条）</div>
    <div class="table-wrap" style="border:1px solid #e2e8f0;border-radius:10px">
      <table class="data">
        <thead><tr><th>规则</th><th>结论</th><th>说明</th></tr></thead>
        <tbody>
          ${trace.map((item) => `<tr>
            <td><span class="mono">${esc(item.rule_id)}</span></td>
            <td>${item.fired ? '<span class="badge badge-danger">命中</span>' : '<span class="badge badge-neutral">未命中</span>'}</td>
            <td><strong style="font-size:12px">${esc(item.name)}</strong><div class="tiny muted">${esc(item.message || '')}</div>
              ${item.legal_basis ? `<div class="tiny" style="color:#98a2b3;margin-top:2px">${esc(item.legal_basis)}</div>` : ''}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    <div class="mini-title" style="margin-top:16px">派生属性（本地引擎依据业务数据计算）</div>
    <div class="row">
      <span class="chip">已到期：${evaluation.derived?.hasMatured ? '是' : '否'}</span>
      <span class="chip">优先顺位：${evaluation.derived?.hasPriority ? '是' : '否'}</span>
      <span class="chip">债权债务同体：${evaluation.derived?.hasSelfDealing ? '是' : '否'}</span>
      <span class="chip">金额为正：${evaluation.derived?.hasAmountPositive ? '是' : '否'}</span>
    </div>`;
  openModal({ title: '抵销资格推理链', subtitle: `${shortId(debt.id)} · 可回溯到规则与法条`, body, wide: true, footer: '<button class="btn" data-close>关闭</button>' });
}

/* ------------------------------------------------------------------ 材料抽取 */
const SAMPLE_MATERIAL = `债权人：恒通建材有限公司
债务人：华远建设集团有限公司
债务金额：人民币 180 万元
到期日：2026年10月31日
是否存在争议：否
是否被查封冻结：否
是否约定禁止抵销：否
备注：补充材料款，双方已对账

债权人：安泰设备租赁有限公司
债务人：中鑫物流有限公司
本金：人民币 95 万元
利息：人民币 5 万元
到期日：2026年9月15日
是否存在争议：是
是否被查封冻结：否
是否约定禁止抵销：否
备注：金额存在争议，待核实`;

const COMPLEX_DEBT_CSV = `债务人,债权人,金额,到期日,争议,查封,禁止抵销,分组,备注
B公司,A公司,1200000,2026-01-01,否,否,否,ordinary,住宿费分摊
C公司,A公司,1200000,2026-01-01,否,否,否,ordinary,住宿费分摊
D公司,A公司,1200000,2026-01-01,否,否,否,ordinary,住宿费分摊
E公司,A公司,1200000,2026-01-01,否,否,否,ordinary,住宿费分摊
A公司,B公司,280000,2026-01-01,否,否,否,ordinary,超市采购分摊
C公司,B公司,280000,2026-01-01,否,否,否,ordinary,超市采购分摊
D公司,B公司,280000,2026-01-01,否,否,否,ordinary,超市采购分摊
E公司,B公司,280000,2026-01-01,否,否,否,ordinary,超市采购分摊
A公司,B公司,200000,2026-01-01,否,否,否,ordinary,聚餐分摊
C公司,B公司,200000,2026-01-01,否,否,否,ordinary,聚餐分摊
D公司,B公司,200000,2026-01-01,否,否,否,ordinary,聚餐分摊
E公司,B公司,200000,2026-01-01,否,否,否,ordinary,聚餐分摊
A公司,C公司,160000,2026-01-01,否,否,否,ordinary,打车分摊
B公司,C公司,160000,2026-01-01,否,否,否,ordinary,打车分摊
D公司,C公司,160000,2026-01-01,否,否,否,ordinary,打车分摊
E公司,C公司,160000,2026-01-01,否,否,否,ordinary,打车分摊
A公司,D公司,80000,2026-01-01,否,否,否,ordinary,门票分摊
B公司,D公司,80000,2026-01-01,否,否,否,ordinary,门票分摊
C公司,D公司,80000,2026-01-01,否,否,否,ordinary,门票分摊
E公司,D公司,80000,2026-01-01,否,否,否,ordinary,门票分摊
A公司,E公司,320000,2026-01-01,否,否,否,ordinary,租船分摊
B公司,E公司,320000,2026-01-01,否,否,否,ordinary,租船分摊
C公司,E公司,320000,2026-01-01,否,否,否,ordinary,租船分摊
D公司,E公司,320000,2026-01-01,否,否,否,ordinary,租船分摊
A公司,E公司,160000,2026-01-01,否,否,否,ordinary,早餐分摊
B公司,E公司,160000,2026-01-01,否,否,否,ordinary,早餐分摊
C公司,E公司,160000,2026-01-01,否,否,否,ordinary,早餐分摊
D公司,E公司,160000,2026-01-01,否,否,否,ordinary,早餐分摊`;

function viewMaterials() {
  const result = state.extraction;
  const file = state.materialFile;
  const left = `
    <section class="card">
      <div class="card-head"><div><h3>材料输入</h3><p>支持 txt / md / docx / 图片，也可以直接粘贴文本</p></div>
        <span class="badge badge-info">本地材料</span></div>
      <div class="card-body stack">
        <div class="dropzone" id="dropzone">
          <strong>${file ? esc(file.name) : '点击选择文件，或拖拽到此处'}</strong>
          <span>${file ? `${(file.size / 1024).toFixed(1)} KB · 已选择` : '扫描件 / 图片需要本地 OCR 支持'}</span>
          <input type="file" id="material-file" hidden accept=".txt,.md,.docx,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp">
          ${file ? '<div class="file-pill">已选择材料 · <a href="#" data-action="clear-file">移除</a></div>' : ''}
        </div>
        <div class="field">
          <label>材料文本（可由 OCR 或人工整理）</label>
          <textarea id="material-text" style="min-height:220px" placeholder="粘贴合同、欠条、对账函或判决书中的债务描述……">${esc(state.materialText)}</textarea>
        </div>
        <div class="row">
          <label class="check"><input type="checkbox" id="use-llm" checked><span>优先使用线上大模型抽取<small>未配置时自动回退本地规则抽取</small></span></label>
          <div class="spacer"></div>
          <button class="btn btn-sm btn-ghost" data-action="load-sample">填入示例材料</button>
          <button class="btn btn-primary" data-action="extract-material">抽取债务要素</button>
        </div>
        <div class="notice notice-info">
          <span>🔒</span><div>线上抽取仅回传结构化字段；可开启脱敏，主体名称与证件号码在本地替换为代号后再上传。原始合同文本默认不进入图谱与本体。</div>
        </div>
      </div>
    </section>`;

  const right = result ? renderExtractionResult(result) : `
    <section class="card">
      <div class="card-head"><div><h3>抽取结果</h3><p>材料 → 结构化字段 → 人工复核 → 入池</p></div></div>
      <div class="card-body">
        ${emptyState('↥', '等待抽取材料', '上传或粘贴材料后点击“抽取债务要素”。抽取结果会先进入人工复核，不会直接参与轧差。')}
      </div>
    </section>`;

  return `<div class="extract-layout">${left}${right}</div>
  ${materialsCardHtml()}
  <div class="notice notice-warn" style="margin-top:18px"><span>⚖</span><div>
    <strong>复核要求：</strong>线上模型只负责要素抽取，不参与抵销资格判定与金额分配。所有抽取结果在入库前必须经过本地本体校验，冲突或缺失字段会标记为待复核。
  </div></div>`;
}

function materialsCardHtml() {
  return `<section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>已存档材料</h3><p>${state.materials.length} 份文件 · 原始文件与抽取记录保存在本地 data/materials/</p></div></div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>文件名</th><th>大小</th><th>抽取引擎</th><th>上传时间</th><th>摘要</th></tr></thead>
        <tbody>
          ${state.materials.length ? state.materials.map((item) => `<tr>
            <td class="strong">${esc(item.filename)}</td>
            <td>${(Number(item.size || 0) / 1024).toFixed(1)} KB</td>
            <td>${item.meta?.engine === 'llm' ? '<span class="badge badge-info">线上大模型</span>' : '<span class="badge badge-neutral">本地规则</span>'}</td>
            <td>${fmtDateTime(item.created_at)}</td>
            <td class="mono">${esc((item.sha256 || '').slice(0, 16))}…</td>
          </tr>`).join('') : '<tr><td colspan="5" class="tiny muted" style="padding:16px">还没有上传过材料文件；粘贴文本抽取不会生成文件记录。</td></tr>'}
        </tbody>
      </table>
    </div>
  </section>`;
}

function renderExtractionResult(result) {
  const candidates = result.candidates || [];
  const selected = state.selectedCandidates;
  const warnings = (result.warnings || []).map((item) => `<div class="notice notice-warn" style="margin-bottom:8px"><span>⚠</span><div>${esc(item)}</div></div>`).join('');
  const cards = candidates.map((candidate, index) => {
    const issues = (candidate.issues || []).map((issue) => `<span class="chip chip-warn">${esc(issue)}</span>`).join('');
    return `<label class="candidate ${selected.has(index) ? 'selected' : ''}" data-candidate="${index}">
      <div class="candidate-head">
        <input type="checkbox" class="cand-check" data-index="${index}" ${selected.has(index) ? 'checked' : ''}>
        <div style="min-width:0">
          <div class="candidate-title">${esc(candidate.debtor_name || '（缺少债务人）')} <span class="muted">→</span> ${esc(candidate.creditor_name || '（缺少债权人）')}</div>
          <div class="tiny muted">${esc(candidate.note || '无备注')}</div>
        </div>
        <span class="badge ${candidate.source === 'ai' ? 'badge-info' : 'badge-neutral'}" style="margin-left:auto">${candidate.source === 'ai' ? 'AI抽取' : '本地抽取'}</span>
      </div>
      <div class="candidate-grid">
        <div><span>金额</span><b>¥${candidate.amount_cents ? fmtCents(candidate.amount_cents) : '—'}</b></div>
        <div><span>到期日</span><b>${candidate.due_date || '—'}</b></div>
        <div><span>顺位分组</span><b>${esc(candidate.priority_label || GROUP_LABELS[candidate.priority_group] || candidate.priority_group)}</b></div>
        <div><span>争议 / 查封 / 禁抵</span><b>${candidate.disputed ? '是' : '否'} / ${candidate.frozen ? '是' : '否'} / ${candidate.no_setoff_clause ? '是' : '否'}</b></div>
        <div><span>主体匹配</span><b>${candidate.debtor_id && candidate.creditor_id ? '已匹配' : '将新建主体'}</b></div>
        <div><span>置信度</span><b>${Math.round((candidate.confidence || 0) * 100)}%</b></div>
      </div>
      ${issues ? `<div class="issues">${issues}</div>` : ''}
    </label>`;
  }).join('');

  return `<section class="card">
    <div class="card-head"><div><h3>抽取结果</h3><p>${esc(result.engine_label)} · ${candidates.length} 条候选债务</p></div>
      <div class="row">
        <button class="btn btn-sm" data-action="select-all-candidates">全选</button>
        <button class="btn btn-sm btn-primary" data-action="import-candidates">导入选中（<span id="selected-count">${selected.size}</span>）</button>
      </div></div>
    <div class="card-body stack">
      ${warnings}
      ${candidates.length ? cards : emptyState('?', '没有识别到债务要素', '请检查文本是否包含债务人、债权人、金额和到期日，或改用人工录入。')}
      <div class="notice notice-info"><span>i</span><div>导入后，AI 抽取的债务默认标记为「待复核」，需在台账中确认后才会进入轧差池。</div></div>
    </div>
  </section>`;
}

function bindMaterialEvents() {
  const dropzone = $('#dropzone');
  const input = $('#material-file');
  const textarea = $('#material-text');
  if (textarea) textarea.addEventListener('input', () => { state.materialText = textarea.value; });
  if (dropzone && input) {
    dropzone.addEventListener('click', (event) => {
      if (event.target === input) return;
      input.click();
    });
    input.addEventListener('change', () => {
      state.materialFile = input.files && input.files[0] ? input.files[0] : null;
      VIEW.innerHTML = viewMaterials();
      bindMaterialEvents();
    });
    ['dragover', 'dragenter'].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add('drag');
    }));
    ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove('drag');
    }));
    dropzone.addEventListener('drop', (event) => {
      const file = event.dataTransfer?.files?.[0];
      if (file) {
        state.materialFile = file;
        VIEW.innerHTML = viewMaterials();
        bindMaterialEvents();
      }
    });
  }
}

function readFileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function extractMaterial(button) {
  const textarea = $('#material-text');
  const useLlm = $('#use-llm');
  const rawText = textarea ? textarea.value : '';
  const text = rawText.trim();
  state.materialText = rawText;
  if (!text && !state.materialFile) {
    toast('请先粘贴材料文本或选择文件。', 'warn');
    return;
  }
  setBusy(button, true);
  try {
    const payload = { text, use_llm: useLlm ? useLlm.checked : true };
    if (state.materialFile) {
      payload.filename = state.materialFile.name;
      payload.content_base64 = await readFileBase64(state.materialFile);
    }
    const result = await api('/api/materials/extract', { method: 'POST', body: JSON.stringify(payload) });
    state.extraction = result;
    state.selectedCandidates = new Set((result.candidates || []).map((_, index) => index));
    if (result.material_id) await loadMaterials();
    VIEW.innerHTML = viewMaterials();
    bindMaterialEvents();
    toast(`抽取完成：${result.candidates.length} 条候选债务。`);
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

function updateCandidateSelection() {
  $$('.candidate').forEach((card) => {
    const index = Number(card.dataset.candidate);
    card.classList.toggle('selected', state.selectedCandidates.has(index));
  });
  const counter = $('#selected-count');
  if (counter) counter.textContent = state.selectedCandidates.size;
}

async function importCandidates(button) {
  if (!state.extraction) return;
  const selected = Array.from(state.selectedCandidates).sort((a, b) => a - b)
    .map((index) => state.extraction.candidates[index])
    .filter(Boolean);
  if (!selected.length) {
    toast('请至少选择一条候选债务。', 'warn');
    return;
  }
  setBusy(button, true);
  try {
    const result = await api('/api/materials/import', {
      method: 'POST',
      body: JSON.stringify({ candidates: selected, material_id: state.extraction.material_id }),
    });
    state.extraction = null;
    state.selectedCandidates = new Set();
    state.materialText = '';
    state.materialFile = null;
    toast(`已导入 ${result.created} 笔债务${result.pending ? `，其中 ${result.pending} 笔待复核` : ''}。`);
    if (state.route === 'debts') {
      await renderView();
    } else {
      window.location.hash = '#/debts';
    }
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

/* ------------------------------------------------------------------ 图谱 */
/* ------------------------------------------------------------------ 图谱 */
const GRAPH_GROUP_COLORS = {
  ordinary: '#0E7C86',
  mortgage: '#B54708',
  wage: '#6941C6',
  tax: '#175CD3',
  custom: '#475467',
  mixed: '#7F56D9',
};

function buildGraphModel() {
  const graph = state.graph;
  const empty = { nodes: [], edges: [], nodeMap: new Map(), stats: new Map(), rawEdges: [], visibleDebtCount: 0 };
  if (!graph) return empty;
  const nodeMap = new Map((graph.nodes || []).map((node) => [node.id, node]));
  let rawEdges = (graph.edges || []).filter((edge) => nodeMap.has(edge.from) && nodeMap.has(edge.to) && edge.from !== edge.to);
  if (state.graphGroup !== 'all') rawEdges = rawEdges.filter((edge) => edge.group === state.graphGroup);

  const stats = new Map();
  const ensure = (id) => {
    if (!stats.has(id)) {
      stats.set(id, {
        receivable_cents: 0, payable_cents: 0,
        eligible_receivable_cents: 0, eligible_payable_cents: 0,
        degree: 0,
      });
    }
    return stats.get(id);
  };
  (graph.nodes || []).forEach((node) => ensure(node.id));
  rawEdges.forEach((edge) => {
    const amount = Number(edge.amount_cents || 0);
    const from = ensure(edge.from);
    const to = ensure(edge.to);
    from.payable_cents += amount;
    to.receivable_cents += amount;
    from.degree += 1;
    to.degree += 1;
    if (edge.eligible) {
      from.eligible_payable_cents += amount;
      to.eligible_receivable_cents += amount;
    }
  });

  const aggregates = new Map();
  rawEdges.forEach((edge) => {
    // 可抵销与不可抵销分开聚合，避免一条线同时代表两种法律状态
    const key = `${edge.from}|${edge.to}|${edge.eligible ? 'eligible' : 'ineligible'}`;
    let entry = aggregates.get(key);
    if (!entry) {
      entry = {
        from: edge.from, to: edge.to, eligible: Boolean(edge.eligible), amount_cents: 0, count: 0,
        eligibleCount: 0, debts: [], groups: new Set(),
      };
      aggregates.set(key, entry);
    }
    entry.amount_cents += Number(edge.amount_cents || 0);
    entry.count += 1;
    if (edge.eligible) entry.eligibleCount += 1;
    entry.debts.push(edge);
    entry.groups.add(edge.group);
  });
  const edges = Array.from(aggregates.values()).map((entry) => {
    const group = entry.groups.size === 1 ? Array.from(entry.groups)[0] : 'mixed';
    return { ...entry, mixed: false, group };
  });
  const parallelGroups = new Map();
  edges.forEach((edge) => {
    const key = `${edge.from}|${edge.to}`;
    if (!parallelGroups.has(key)) parallelGroups.set(key, []);
    parallelGroups.get(key).push(edge);
  });
  parallelGroups.forEach((items) => {
    items.sort((a, b) => Number(a.eligible) - Number(b.eligible));
    items.forEach((item, index) => {
      item.parallelIndex = index;
      item.parallelCount = items.length;
    });
  });

  const nodes = (graph.nodes || []).filter((node) => state.graphGroup === 'all' || (stats.get(node.id)?.degree || 0) > 0);
  return {
    nodes,
    edges,
    nodeMap,
    stats,
    rawEdges,
    visibleDebtCount: rawEdges.length,
  };
}

function graphNodeShortName(name) {
  const source = String(name || '');
  if (source.includes('工会')) return '工会';
  const cleaned = source
    .replace(/有限责任公司|有限公司|股份公司/g, '')
    .replace(/集团有限公司/g, '')
    .replace(/集团/g, '')
    .replace(/公司/g, '')
    .replace(/支行|分行/g, '')
    .replace(/委员会/g, '');
  return (cleaned || source).slice(0, 2) || '主体';
}

function graphEdgeAmount(cents) {
  const value = Number(cents || 0) / 100;
  const trim = (number) => {
    const rounded = Math.round(number * 100) / 100;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
  };
  const absolute = Math.abs(value);
  if (absolute >= 100000000) return `${trim(value / 100000000)}亿`;
  if (absolute >= 10000) return `${trim(value / 10000)}万`;
  return `${trim(value)}元`;
}

function graphNodeDisplayName(name) {
  const text = String(name || '');
  let cleaned = text.replace(/有限责任公司|股份有限公司|有限公司/g, '');
  if (text.includes('工会')) {
    cleaned = cleaned.replace(/工会委员会$/, '工会').replace(/委员会$/, '工会').replace(/集团/g, '');
  }
  return cleaned || text;
}

function graphVisibleCycles(model) {
  const graph = state.graph;
  const ids = new Set(model.nodes.map((node) => node.id));
  const edges = new Set(model.edges.map((edge) => `${edge.from}|${edge.to}`));
  return (graph?.cycles || []).filter((cycle) => {
    if (cycle.length < 2) return false;
    if (!cycle.every((id) => ids.has(id))) return false;
    return cycle.every((id, index) => edges.has(`${id}|${cycle[(index + 1) % cycle.length]}`));
  });
}

function graphSideHtml() {
  const graph = state.graph;
  if (!graph) return '';
  const model = state.graphModel || buildGraphModel();
  const nodeMap = model.nodeMap;
  const cycles = graphVisibleCycles(model);
  const activeCycle = state.graphActiveCycle != null ? cycles[state.graphActiveCycle] : null;
  const selectedNode = state.selectedNode ? nodeMap.get(state.selectedNode) : null;
  const selectedStats = selectedNode ? model.stats.get(selectedNode.id) : null;
  const visibleIds = new Set(model.nodes.map((node) => node.id));
  const hubs = model.nodes
    .filter((node) => node.is_hub)
    .sort((a, b) => (b.cycle_count || 0) - (a.cycle_count || 0) || (b.edge_count || 0) - (a.edge_count || 0))
    .slice(0, 6);
  const groups = Object.keys(GROUP_LABELS).filter((code) => model.edges.some((edge) => edge.group === code));
  const cycleFullNames = (cycle) => cycle.map((id) => nodeMap.get(id)?.name || id);
  const cycleNames = (cycle) => cycle.map((id) => graphNodeShortName(nodeMap.get(id)?.name || id));

  const cycleItems = cycles.slice(0, 7).map((cycle, index) => `
    <button class="side-item cycle-item ${state.graphActiveCycle === index ? 'active' : ''}" data-action="select-cycle" data-index="${index}" title="${esc(cycleFullNames(cycle).join(' → '))}">
      <span class="rank">${index + 1}</span>
      <span class="grow">${esc(cycleNames(cycle).join(' → '))}</span>
      <span class="val">${cycle.length} 环</span>
    </button>`).join('');

  const hubItems = hubs.map((hub) => `
    <button class="side-item" data-action="select-graph-node" data-id="${hub.id}">
      <span class="rank">◆</span>
      <span class="grow">${esc(hub.name)}</span>
      <span class="val">${hub.cycle_count || 0} 环</span>
    </button>`).join('');

  const links = selectedNode
    ? model.edges
      .filter((edge) => edge.from === selectedNode.id || edge.to === selectedNode.id)
      .sort((a, b) => (a.from === selectedNode.id ? 0 : 1) - (b.from === selectedNode.id ? 0 : 1) || b.amount_cents - a.amount_cents)
    : [];
  const linkItems = links.slice(0, 12).map((edge) => {
    const outgoing = edge.from === selectedNode.id;
    const other = nodeMap.get(outgoing ? edge.to : edge.from);
    const eligibility = edge.eligible ? '可抵销' : (edge.mixed ? '部分抵销' : '不入池');
    const eligibilityClass = edge.eligible ? 'badge-ok' : (edge.mixed ? 'badge-warn' : 'badge-neutral');
    return `<button class="side-link" data-action="select-graph-node" data-id="${other?.id || ''}">
      <span class="dir-badge ${outgoing ? 'out' : 'in'}">${outgoing ? '付 →' : '← 收'}</span>
      <span class="side-link-main"><strong>${esc(other?.name || '未知主体')}</strong>
        <span>${esc(GROUP_LABELS[edge.group] || '混合分组')} · <i class="badge ${eligibilityClass}">${eligibility}</i></span></span>
      <span class="side-link-amount">¥${fmtCents(edge.amount_cents)}</span>
    </button>`;
  }).join('');

  const selectedRole = selectedStats
    ? (selectedStats.eligible_receivable_cents - selectedStats.eligible_payable_cents)
    : 0;
  const roleLabel = selectedRole > 0 ? '净债权人' : selectedRole < 0 ? '净债务人' : '头寸平衡';

  return `
    <section class="card">
      <div class="card-head"><div><h3>关系金额</h3><p>图上看结构，这里核对每一条有向关系的金额</p></div>
        <span class="badge badge-neutral">${model.edges.length} 条</span></div>
      <div class="card-body">
        <div class="side-amount-list" style="max-height:420px">
          ${[...model.edges].sort((a, b) => b.amount_cents - a.amount_cents).map((edge) => `<div class="side-amount-row">
            <span class="grow">${esc(graphNodeDisplayName(nodeMap.get(edge.from)?.name))} <span class="dir">→</span> ${esc(graphNodeDisplayName(nodeMap.get(edge.to)?.name))}</span>
            <strong>${graphEdgeAmount(edge.amount_cents)}</strong>
            <span class="badge ${edge.eligible ? 'badge-ok' : 'badge-neutral'}">${edge.eligible ? '可抵销' : '不入池'}</span>
          </div>`).join('')}
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><div><h3>图谱概览</h3><p>节点为参与主体，箭头发起方为债务人</p></div></div>
      <div class="card-body stack">
        <div class="graph-stat-grid">
          <div><strong>${model.nodes.length}</strong><span>可见主体</span></div>
          <div><strong>${model.edges.length}</strong><span>聚合关系</span></div>
          <div><strong>${model.visibleDebtCount}</strong><span>债务笔数</span></div>
          <div><strong>${cycles.length}</strong><span>可见环路</span></div>
        </div>
        <div class="graph-legend-grid">
          ${groups.map((code) => `<span><i class="swatch" style="background:${GRAPH_GROUP_COLORS[code] || '#98a2b3'}"></i>${GROUP_LABELS[code] || code}</span>`).join('')}
          <span><i class="swatch" style="background:#12b76a"></i>净债权人</span>
          <span><i class="swatch" style="background:#f97066"></i>净债务人</span>
          <span><i class="swatch" style="background:#98a2b3"></i>头寸归零</span>
          <span><i class="legend-line dashed"></i>不入池</span>
        </div>
        <p class="graph-tip">滚轮缩放、拖拽平移。点击主体查看关联债务，点击环路高亮债务链条。</p>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><div><h3>债务环路</h3><p>点击一条环路，在图中高亮完整链条</p></div></div>
      <div class="card-body">
        ${activeCycle ? `<div class="active-cycle"><span>${esc(cycleNames(activeCycle).join(' → '))}</span><button class="btn btn-sm" data-action="clear-graph-highlight">清除</button></div>` : ''}
        ${cycleItems ? `<div class="side-list">${cycleItems}</div>` : '<p class="tiny muted">当前视图没有长度为 2～6 的有向环路。</p>'}
      </div>
    </section>

    <section class="card">
      <div class="card-head"><div><h3>枢纽主体</h3><p>多个债务环的交汇点</p></div></div>
      <div class="card-body">
        ${hubItems ? `<div class="side-list">${hubItems}</div>` : '<p class="tiny muted">当前视图暂无枢纽主体。</p>'}
      </div>
    </section>

    ${selectedNode ? `<section class="card selected-node-card">
      <div class="card-head"><div><h3>${esc(selectedNode.name)}</h3><p>${roleLabel} · 点击“付/收”可跳转对方主体</p></div>
        <button class="btn btn-sm" data-action="clear-graph-highlight">取消</button></div>
      <div class="card-body stack">
        <div class="row">
          <span class="badge badge-neutral">合格应收 ¥${fmtCents(selectedStats?.eligible_receivable_cents || 0)}</span>
          <span class="badge badge-neutral">合格应付 ¥${fmtCents(selectedStats?.eligible_payable_cents || 0)}</span>
          <span class="badge ${selectedRole > 0 ? 'badge-ok' : selectedRole < 0 ? 'badge-danger' : 'badge-neutral'}">${roleLabel} ${selectedRole > 0 ? '+' : ''}¥${fmtCents(selectedRole)}</span>
          ${selectedNode.cycle_count ? `<span class="badge badge-warn">${selectedNode.cycle_count} 个环路</span>` : ''}
        </div>
        <p class="tiny muted">整体头寸（含全部债务）¥${fmtCents(selectedNode.net_cents)}；上方为当前视图的合格债务口径。</p>
        <div class="mini-title">关联债务（按对手方聚合）</div>
        <div class="side-links">
          ${linkItems || '<p class="tiny muted">当前视图没有关联债务。</p>'}
          ${links.length > 12 ? `<p class="tiny muted">另有 ${links.length - 12} 条关联关系。</p>` : ''}
        </div>
        ${!visibleIds.has(selectedNode.id) ? '<p class="tiny muted">该主体已被当前分组筛选隐藏。</p>' : ''}
      </div>
    </section>` : ''}`;
}

function viewGraph() {
  const graph = state.graph;
  if (!graph) return '';
  const groupCodes = [...new Set((graph.edges || []).map((edge) => edge.group))];
  if (state.graphGroup !== 'all' && !groupCodes.includes(state.graphGroup)) state.graphGroup = 'all';
  state.graphModel = buildGraphModel();
  const model = state.graphModel;
  const groups = Object.keys(GROUP_LABELS).filter((code) => groupCodes.includes(code));
  const cycles = graphVisibleCycles(model);
  const dense = model.edges.length > 12;
  const matrix = state.graphView === 'matrix' || (state.graphView === 'auto' && dense);
  const highlightActive = Boolean(state.selectedNode) || state.graphActiveCycle != null;
  const groupOptions = ['all', ...groups];
  const legendGroups = groups.map((code) => `<span><i class="legend-line" style="background:${GRAPH_GROUP_COLORS[code]}"></i>${GROUP_LABELS[code]}</span>`).join('');

  return `
  <div class="card graph-toolbar">
    <div class="row">
      <span class="badge badge-navy" id="graph-visible-stats">${model.nodes.length} 个主体 · ${model.edges.length} 条聚合边</span>
      <span class="badge badge-info" id="graph-debt-count">${model.visibleDebtCount} 笔债务</span>
      <span class="badge badge-warn" id="graph-cycle-count">${cycles.length} 个环路</span>
      <span class="badge badge-neutral">${graph.stats.scc_count} 个强连通分量</span>
    </div>
    <div class="spacer"></div>
    <div class="graph-view-switch" role="group" aria-label="图谱视图">
      <button class="btn btn-sm ${matrix ? '' : 'btn-primary'}" data-action="graph-view" data-view="graph">关系图</button>
      <button class="btn btn-sm ${matrix ? 'btn-primary' : ''}" data-action="graph-view" data-view="matrix">矩阵表</button>
    </div>
    ${dense && !matrix ? '<span class="tiny muted graph-dense-hint">关系较密，矩阵表更清楚</span>' : ''}
    ${dense && matrix ? '<span class="tiny muted graph-dense-hint">关系较密，已自动使用矩阵表</span>' : ''}
    ${!matrix ? '<span class="tiny muted">金额标签已直接标在关系线上</span>' : ''}
    <label class="graph-control">分组
      <select id="graph-group">
        ${groupOptions.map((code) => `<option value="${code}" ${state.graphGroup === code ? 'selected' : ''}>${code === 'all' ? '全部顺位' : (GROUP_LABELS[code] || code)}</option>`).join('')}
      </select>
    </label>
    <label class="check"><input type="checkbox" id="graph-ineligible" ${state.graphIneligible ? 'checked' : ''}><span>显示不可抵销债务</span></label>
    ${highlightActive ? '<button class="btn btn-sm" data-action="clear-graph-highlight">清除高亮</button>' : ''}
    <button class="btn btn-sm" data-action="reload-graph">刷新图谱</button>
  </div>

  <div class="graph-layout">
    <section class="card graph-canvas ${matrix ? 'graph-canvas-matrix' : ''}">
      ${matrix ? graphMatrixHtml(model) : `<div class="graph-stage">
        <div id="graph-svg-wrap"></div>
        <div class="graph-zoom">
          <button data-action="graph-zoom-in" title="放大">＋</button>
          <button data-action="graph-zoom-out" title="缩小">−</button>
          <button data-action="graph-fit" title="适应画布">⤢</button>
        </div>
        <div class="graph-hint" id="graph-hint">拖拽平移 · 滚轮缩放 · 点击主体查看关联债务</div>
      </div>
      <div class="graph-legend">
        ${legendGroups}
        <span><i class="legend-line dashed"></i>灰色虚线 = 不可抵销（单独成线）</span>
        <span><i class="legend-dot" style="background:#f79009"></i>枢纽主体（琥珀外环）</span>
      </div>`}
    </section>
    <aside class="graph-side" id="graph-side">${graphSideHtml()}</aside>
  </div>

  <div class="notice notice-info" style="margin-top:16px"><span>i</span><div>
    ${matrix
      ? '行是欠钱的一方，列是收钱的一方；单元格金额是这一对主体之间多笔债务的合计。空单元格表示没有直接债务，斜线表示自己欠自己，已忽略。'
      : '箭头由债务人指向债权人；同一对主体之间的多笔债务聚合为一条边，金额为合计值，悬停可查看明细。环路仅用于展示债务链条与风险传导路径，最终清偿方案仍以净头寸为依据。'}
  </div></div>`;
}

function graphEdgeTableHtml(model) {
  const rows = [...model.edges].sort((a, b) => b.amount_cents - a.amount_cents).map((edge) => `<tr>
    <td>${esc(model.nodeMap.get(edge.from)?.name || edge.from)} <span class="dir">→</span> ${esc(model.nodeMap.get(edge.to)?.name || edge.to)}</td>
    <td class="num"><strong>¥${fmtCents(edge.amount_cents)}</strong></td>
    <td>${esc(GROUP_LABELS[edge.group] || '混合分组')}</td>
    <td>${edge.eligible ? '<span class="badge badge-ok">可抵销</span>' : '<span class="badge badge-neutral">不入池</span>'}</td>
    <td class="num">${edge.count}</td>
  </tr>`).join('');
  return `<section class="card graph-edge-table">
    <div class="card-head"><div><h3>关系金额</h3><p>图中每条有向关系的金额；关系较多时不把标签硬塞到线上</p></div>
      <span class="badge badge-neutral">${model.edges.length} 条</span></div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>谁欠谁</th><th class="num">金额</th><th>分组</th><th>状态</th><th class="num">笔数</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </section>`;
}

function graphMatrixHtml(model) {
  const nodes = [...model.nodes].sort((a, b) => graphNodeDisplayName(a.name).localeCompare(graphNodeDisplayName(b.name), 'zh-CN'));
  if (!nodes.length) return '<div class="empty"><div class="empty-icon">∅</div><h3>当前视图没有可展示的主体</h3></div>';
  const edgesAt = new Map();
  model.edges.forEach((edge) => {
    const key = `${edge.from}|${edge.to}`;
    if (!edgesAt.has(key)) edgesAt.set(key, []);
    edgesAt.get(key).push(edge);
  });
  const groups = [...new Set(model.edges.map((edge) => edge.group))];
  const name = (node) => graphNodeDisplayName(node.name);
  const tint = (hex, alpha) => {
    const value = String(hex || '#98a2b3').replace('#', '');
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };
  const rowTotals = new Map();
  const colTotals = new Map();
  model.edges.forEach((edge) => {
    rowTotals.set(edge.from, (rowTotals.get(edge.from) || 0) + edge.amount_cents);
    colTotals.set(edge.to, (colTotals.get(edge.to) || 0) + edge.amount_cents);
  });
  const header = nodes.map((node) => `<th title="${esc(node.name)}">${esc(name(node))}</th>`).join('');
  const body = nodes.map((from) => {
    const cells = nodes.map((to) => {
      if (from.id === to.id) return '<td class="matrix-diagonal">—</td>';
      const cellEdges = edgesAt.get(`${from.id}|${to.id}`) || [];
      if (!cellEdges.length) return '<td class="matrix-empty">·</td>';
      const eligibleEdge = cellEdges.find((item) => item.eligible);
      const color = GRAPH_GROUP_COLORS[eligibleEdge?.group] || '#98a2b3';
      const title = cellEdges.map((item) => `${from.name} → ${to.name} · ${item.eligible ? '可抵销' : '不入池'}：${item.count} 笔，合计 ¥${fmtCents(item.amount_cents)}`).join('\n');
      const amounts = cellEdges.map((item) => `<span class="matrix-amount ${item.eligible ? 'ok' : 'no'}">${graphEdgeAmount(item.amount_cents)}${item.count > 1 ? `<small>×${item.count}</small>` : ''}${item.eligible ? '' : '<em>不入池</em>'}</span>`).join('');
      return `<td class="matrix-cell ${eligibleEdge ? '' : 'matrix-ineligible'}" style="background:${tint(color, eligibleEdge ? 0.09 : 0.04)};border-color:${tint(color, 0.28)}" title="${esc(title)}">
        ${amounts}
      </td>`;
    }).join('');
    return `<tr><th title="${esc(from.name)}">${esc(name(from))}</th>${cells}<td class="matrix-total">${graphEdgeAmount(rowTotals.get(from.id) || 0)}</td></tr>`;
  }).join('');
  const footer = nodes.map((node) => `<td class="matrix-total">${graphEdgeAmount(colTotals.get(node.id) || 0)}</td>`).join('');
  const legend = groups.map((code) => `<span><i class="swatch" style="background:${GRAPH_GROUP_COLORS[code]}"></i>${GROUP_LABELS[code] || code}</span>`).join('');
  return `<div class="graph-matrix-wrap">
    <div class="graph-matrix-head">
      <div><h3>债务关系矩阵</h3><p>行 = 欠钱的人，列 = 收钱的人；金额已按同一对主体合并</p></div>
      <span class="badge badge-neutral">${model.nodes.length} × ${model.nodes.length}</span>
    </div>
    <div class="table-wrap graph-matrix-scroll">
      <table class="matrix">
        <thead><tr><th class="matrix-corner">债务人 ↓<br>债权人 →</th>${header}<th class="matrix-total-head">合计应付</th></tr></thead>
        <tbody>${body}</tbody>
        <tfoot><tr><th class="matrix-total-head">合计应收</th>${footer}<td class="matrix-corner">—</td></tr></tfoot>
      </table>
    </div>
    <div class="graph-matrix-foot">
      <div class="graph-legend">${legend}<span><i class="legend-dot" style="background:#98a2b3"></i>空单元格表示无直接债务</span></div>
      <span class="tiny muted">悬停单元格可查看笔数；虚线框表示该笔不入池或仅部分可抵销。</span>
    </div>
  </div>`;
}

function drawClassicGraph() {
  const root = document.getElementById('graph-echarts');
  if (!root) return;
  if (!window.echarts) {
    root.innerHTML = '<div class="empty"><div class="empty-icon">!</div><h3>图谱引擎未加载</h3><p>请刷新页面重试。</p></div>';
    return;
  }
  const model = buildGraphModel();
  state.graphModel = model;
  const focus = graphFocus(model);
  if (state.graphChart) {
    state.graphChart.dispose();
    state.graphChart = null;
  }
  const nodes = model.nodes.map((node, index) => {
    const stats = model.stats.get(node.id) || {
      receivable_cents: 0, payable_cents: 0,
      eligible_receivable_cents: 0, eligible_payable_cents: 0, degree: 0,
    };
    const net = stats.eligible_receivable_cents - stats.eligible_payable_cents;
    const selected = state.selectedNode === node.id;
    const dim = focus.active && !focus.nodes.has(node.id);
    const display = graphNodeDisplayName(node.name);
    const angle = (Math.PI * 2 * index) / Math.max(1, model.nodes.length) - Math.PI / 2;
    return {
      id: node.id,
      name: display,
      value: stats.degree,
      x: 430 + Math.cos(angle) * 190,
      y: 280 + Math.sin(angle) * 150,
      symbolSize: 34 + Math.min(12, (stats.degree || 0) * 1.6),
      itemStyle: {
        color: net > 0 ? '#12a36f' : net < 0 ? '#e2605a' : '#8d9ba8',
        borderColor: selected ? '#0E7C86' : '#ffffff',
        borderWidth: selected ? 3.5 : 1.8,
        opacity: dim ? 0.18 : 1,
        shadowBlur: 8,
        shadowColor: 'rgba(15,23,42,.15)',
      },
      label: {
        show: true,
        position: 'inside',
        formatter: () => graphNodeShortName(node.name),
        color: dim ? '#e2e8f0' : '#ffffff',
        fontSize: 11,
        fontWeight: 700,
      },
      _raw: node,
      _stats: stats,
      _net: net,
    };
  });
  const links = model.edges.map((edge) => {
    const focused = focus.active && focus.edges.has(`${edge.from}|${edge.to}`);
    return {
      source: edge.from,
      target: edge.to,
      value: edge.amount_cents,
      lineStyle: {
        color: edge.eligible ? (GRAPH_GROUP_COLORS[edge.group] || '#98a2b3') : '#7c8b99',
        width: edge.eligible ? 1.7 : 1.35,
        opacity: focus.active && !focused ? 0.06 : (edge.eligible ? 0.68 : 0.52),
        type: edge.eligible ? 'solid' : 'dashed',
        curveness: (edge.parallelCount || 1) > 1 ? 0.2 : 0.08,
      },
      _edge: edge,
    };
  });
  const option = {
    animationDuration: 280,
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (params) => {
        if (params.dataType === 'edge') {
          const edge = params.data._edge;
          if (!edge) return '';
          const from = model.nodeMap.get(edge.from)?.name || edge.from;
          const to = model.nodeMap.get(edge.to)?.name || edge.to;
          return `<b>${esc(from)} → ${esc(to)}</b><br>${edge.count} 笔债务 · 合计 ¥${fmtCents(edge.amount_cents)}<br>${GROUP_LABELS[edge.group] || '混合分组'} · ${edge.eligible ? '可抵销' : '不可抵销'}`;
        }
        const data = params.data;
        if (!data?._raw) return '';
        return `<b>${esc(data._raw.name)}</b><br>应收 ¥${fmtCents(data._stats.receivable_cents)} · 应付 ¥${fmtCents(data._stats.payable_cents)}<br>合格债务净头寸 ${data._net > 0 ? '+' : ''}¥${fmtCents(data._net)}`;
      },
    },
    series: [{
      type: 'graph',
      layout: 'none',
      roam: true,
      draggable: true,
      data: nodes,
      links,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: 4.5,
      edgeLabel: { show: false },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  };
  const chart = window.echarts.init(root, null, { renderer: 'canvas' });
  chart.setOption(option);
  state.graphChart = chart;
  chart.on('click', (params) => {
    if (params.dataType === 'node' && params.data?.id) {
      state.selectedNode = params.data.id;
      state.graphActiveCycle = null;
      const side = document.getElementById('graph-side');
      if (side) side.innerHTML = graphSideHtml();
      drawClassicGraph();
    }
  });
  window.setTimeout(() => chart.resize(), 30);
}

function drawGraph() {
  if (document.getElementById('graph-echarts')) {
    drawClassicGraph();
    return;
  }
  if (state.graphChart) {
    state.graphChart.dispose();
    state.graphChart = null;
  }
  const graph = state.graph;
  const wrap = $('#graph-svg-wrap');
  if (!graph || !wrap) return;
  const model = buildGraphModel();
  state.graphModel = model;
  const hint = $('#graph-hint');
  if (hint) {
    hint.textContent = model.edges.length > 12
      ? '金额标签默认只显示选中主体的边，悬停边可看完整金额；滚轮缩放 / 拖拽平移'
      : '滚轮缩放 · 拖拽平移 · 点击主体查看关联债务';
  }
  const stat = $('#graph-visible-stats');
  if (stat) stat.textContent = `${model.nodes.length} 个主体 · ${model.edges.length} 条聚合边`;
  const debtCount = $('#graph-debt-count');
  if (debtCount) debtCount.textContent = `${model.visibleDebtCount} 笔债务`;
  const cycleCount = $('#graph-cycle-count');
  if (cycleCount) cycleCount.textContent = `${graphVisibleCycles(model).length} 个环路`;

  if (!model.nodes.length) {
    wrap.innerHTML = `<div class="empty"><div class="empty-icon">∅</div><h3>当前视图没有可展示的主体</h3><p>尝试切换顺位分组，或取消筛选条件。</p></div>`;
    const side = $('#graph-side');
    if (side) side.innerHTML = graphSideHtml();
    return;
  }

  const width = 640;
  const height = 450;
  const layout = model.nodes.length <= 10
    ? circleLayout(model.nodes, model.edges, width, height)
    : forceLayout(model.nodes, model.edges, width, height);
  const positions = new Map(layout.map((item) => [item.id, item]));
  const maxDegree = Math.max(1, ...Array.from(model.stats.values()).map((item) => item.degree));
  const radii = new Map(model.nodes.map((node) => {
    const degree = model.stats.get(node.id)?.degree || 0;
    return [node.id, 25 + Math.round((degree / maxDegree) * 9)];
  }));
  const focus = graphFocus(model);
  const directed = new Set(model.edges.map((edge) => `${edge.from}|${edge.to}`));
  const showFullLabels = model.nodes.length <= 24;
  const labelDense = model.edges.length > 12;

  const edgeGeometry = model.edges.map((edge, index) => {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) return null;
    const r1 = (radii.get(edge.from) || 28) + 4;
    const r2 = (radii.get(edge.to) || 28) + 10;
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const startX = from.x + (dx / distance) * r1;
    const startY = from.y + (dy / distance) * r1;
    const endX = to.x - (dx / distance) * r2;
    const endY = to.y - (dy / distance) * r2;
    const normalX = -dy / distance;
    const normalY = dx / distance;
    const anchorShift = (edge.parallelCount || 1) > 1
      ? ((edge.parallelIndex || 0) - ((edge.parallelCount || 1) - 1) / 2) * 5
      : 0;
    const anchorStartX = startX + normalX * anchorShift;
    const anchorStartY = startY + normalY * anchorShift;
    const anchorEndX = endX + normalX * anchorShift;
    const anchorEndY = endY + normalY * anchorShift;
    const reverse = directed.has(`${edge.to}|${edge.from}`);
    const parallelOffset = ((edge.parallelIndex || 0) - ((edge.parallelCount || 1) - 1) / 2) * 20;
    const bend = (reverse ? (edge.from < edge.to ? 34 : -34) : 0) + parallelOffset;
    const midX = (startX + endX) / 2 + normalX * bend;
    const midY = (startY + endY) / 2 + normalY * bend;
    const color = edge.eligible ? (GRAPH_GROUP_COLORS[edge.group] || '#98a2b3') : '#7c8b99';
    const widthScale = edge.eligible
      ? 1.1 + Math.min(2.4, Math.log10(1 + edge.amount_cents / 10000) * 0.55)
      : 1.35;
    const dash = edge.eligible ? '' : 'stroke-dasharray="5 5"';
    const key = `${edge.from}|${edge.to}`;
    const dim = focus.active && !focus.edges.has(key);
    const focused = focus.active && focus.edges.has(key);
    const labelText = `${graphEdgeAmount(edge.amount_cents)}${edge.count > 1 ? ` ×${edge.count}` : ''}`;
    const labelWidth = Math.max(52, labelText.length * 8.8 + 20);
    const title = `${model.nodeMap.get(edge.from)?.name} → ${model.nodeMap.get(edge.to)?.name}\n`
      + `${edge.count} 笔债务，合计 ¥${fmtCents(edge.amount_cents)}\n`
      + `${GROUP_LABELS[edge.group] || '混合分组'} · ${edge.eligible ? '全部可抵销' : '不入池'}\n`
      + edge.debts.map((debt) => `${debt.eligible ? '✓' : '×'} ¥${fmtCents(debt.amount_cents)}${debt.note ? `（${debt.note}）` : ''}`).join('\n');
    return {
      edge, index, startX: anchorStartX, startY: anchorStartY, midX, midY, endX: anchorEndX, endY: anchorEndY,
      color, widthScale, dash, dim, focused, labelText, labelWidth, title, key,
    };
  }).filter(Boolean);
  // 先画不可抵销的虚线，再画可抵销的实线，避免实线盖住虚线
  edgeGeometry.sort((a, b) => Number(a.edge.eligible) - Number(b.edge.eligible) || a.index - b.index);

  const nodeGeometry = model.nodes.map((node) => {
    const position = positions.get(node.id);
    if (!position) return null;
    const radius = radii.get(node.id) || 28;
    const nodeStats = model.stats.get(node.id) || {
      receivable_cents: 0, payable_cents: 0,
      eligible_receivable_cents: 0, eligible_payable_cents: 0,
    };
    const net = nodeStats.eligible_receivable_cents - nodeStats.eligible_payable_cents;
    const fill = net > 0 ? '#12a36f' : net < 0 ? '#e2605a' : '#8d9ba8';
    const dim = focus.active && !focus.nodes.has(node.id);
    const selected = state.selectedNode === node.id;
    const stroke = selected ? '#0E7C86' : '#ffffff';
    const shortName = graphNodeShortName(node.name);
    const labelName = graphNodeDisplayName(node.name);
    const labelWidth = Math.max(56, labelName.length * 10.8 + 18);
    const below = position.y + radius + 34 < height - 6;
    const labelY = below ? position.y + radius + 9 : position.y - radius - 30;
    const title = `${node.name}\n应收 ¥${fmtCents(nodeStats.receivable_cents)} · 应付 ¥${fmtCents(nodeStats.payable_cents)}\n合格债务净头寸 ${net > 0 ? '+' : ''}¥${fmtCents(net)}`
      + `${node.cycle_count ? `\n位于 ${node.cycle_count} 个环路` : ''}`;
    return {
      node, x: position.x, y: position.y, radius, net, fill, dim, selected, stroke,
      shortName, labelName, labelWidth, labelY, title,
    };
  }).filter(Boolean);
  const topHubs = new Set(
    [...nodeGeometry]
      .sort((a, b) => (b.node.cycle_count || 0) - (a.node.cycle_count || 0))
      .slice(0, 3)
      .map((item) => item.node.id),
  );

  // 先占据节点与节点标签的位置，再为边标签寻找不重叠的落点
  const occupied = [];
  nodeGeometry.forEach((item) => {
    occupied.push({ x: item.x - item.radius - 4, y: item.y - item.radius - 4, w: item.radius * 2 + 8, h: item.radius * 2 + 8 });
    if (showFullLabels) {
      occupied.push({ x: item.x - item.labelWidth / 2 - 4, y: item.labelY - 2, w: item.labelWidth + 8, h: 26 });
    }
  });
  const labelPoints = new Map();
  if (state.graphShowAmounts) {
    edgeGeometry.forEach((geometry) => {
      const visible = !labelDense || (focus.active && focus.edges.has(geometry.key));
      if (!visible) return;
      const point = pickEdgeLabelPosition(geometry, occupied, width, height, edgeGeometry);
      labelPoints.set(geometry.index, point);
      occupied.push({ x: point.x - geometry.labelWidth / 2 - 4, y: point.y - 15, w: geometry.labelWidth + 8, h: 30 });
    });
  }

  const markers = edgeGeometry.map((geometry) => {
    return `<marker id="garrow-${geometry.index}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4.4" markerHeight="4.4" orient="auto-start-reverse">
      <path d="M 1 1 L 9 5 L 1 9 z" fill="${geometry.color}"/></marker>`;
  }).join('');

  const edgePathMarkup = edgeGeometry.map((geometry) => {
    return `<g class="graph-edge-group ${geometry.dim ? 'graph-dim' : ''}">
      <path class="graph-edge ${geometry.focused ? 'graph-focus' : ''}" d="M ${geometry.startX.toFixed(1)} ${geometry.startY.toFixed(1)} Q ${geometry.midX.toFixed(1)} ${geometry.midY.toFixed(1)} ${geometry.endX.toFixed(1)} ${geometry.endY.toFixed(1)}"
        fill="none" stroke="${geometry.color}" stroke-width="${geometry.widthScale.toFixed(2)}" stroke-linecap="round" ${geometry.dash}
        marker-end="url(#garrow-${geometry.index})" opacity="${geometry.edge.eligible ? '0.66' : '0.5'}">
        <title>${esc(geometry.title)}</title>
      </path>
    </g>`;
  }).join('');

  const edgeLabelMarkup = edgeGeometry.map((geometry) => {
    const labelPoint = labelPoints.get(geometry.index);
    if (!labelPoint) return '';
    return `<g class="edge-label" transform="translate(${labelPoint.x.toFixed(1)} ${labelPoint.y.toFixed(1)})" opacity="${geometry.edge.eligible ? '1' : '0.82'}">
      <rect x="${(-geometry.labelWidth / 2).toFixed(1)}" y="-11" width="${geometry.labelWidth.toFixed(1)}" height="22" rx="5" fill="#ffffff" stroke="${geometry.color}" stroke-opacity="0.35" ${geometry.edge.eligible ? '' : 'stroke-dasharray="3 2"'} />
      <text text-anchor="middle" y="4" fill="${geometry.color}" font-size="11.5" font-weight="600">${esc(geometry.labelText)}</text>
    </g>`;
  }).join('');

  const nodeMarkup = nodeGeometry.map((item) => {
    const hub = topHubs.has(item.node.id);
    return `<g class="graph-node ${item.dim ? 'graph-dim' : ''} ${item.selected ? 'selected' : ''}" data-action="select-graph-node" data-id="${item.node.id}">
      <title>${esc(item.title)}</title>
      ${hub ? `<circle cx="${item.x.toFixed(1)}" cy="${item.y.toFixed(1)}" r="${(item.radius + 4.5).toFixed(1)}" fill="none" stroke="${item.selected ? '#0E7C86' : '#F79009'}" stroke-width="1.1" opacity="${item.selected ? '0.75' : '0.32'}"/>` : ''}
      <circle cx="${item.x.toFixed(1)}" cy="${item.y.toFixed(1)}" r="${item.radius}" fill="${item.fill}" stroke="${item.stroke}" stroke-width="${item.selected ? 3.5 : 2}" filter="url(#node-shadow)"/>
      <text x="${item.x.toFixed(1)}" y="${(item.y + 4.5).toFixed(1)}" text-anchor="middle" fill="#ffffff" font-size="${item.shortName.length > 2 ? 10.5 : 12.5}" font-weight="700">${esc(item.shortName)}</text>
      ${showFullLabels ? `<g class="node-label">
        <rect x="${(item.x - item.labelWidth / 2).toFixed(1)}" y="${item.labelY.toFixed(1)}" width="${item.labelWidth.toFixed(1)}" height="22" rx="7" fill="${item.selected ? '#E7F4F5' : '#ffffff'}" stroke="${item.selected ? '#0E7C86' : '#e4e9ef'}" stroke-width="1"/>
        <text x="${item.x.toFixed(1)}" y="${(item.labelY + 15).toFixed(1)}" text-anchor="middle" fill="#344054" font-size="12" font-weight="500">${esc(item.labelName)}</text>
      </g>` : ''}
    </g>`;
  }).join('');

  wrap.innerHTML = `<svg id="graph-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="债务网络图">
    <defs>
      <pattern id="graph-dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="#e3e9ef"/></pattern>
      <filter id="node-shadow" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="2.2" stdDeviation="2.4" flood-color="#0f172a" flood-opacity="0.2"/>
      </filter>
      ${markers}
    </defs>
    <rect width="${width}" height="${height}" fill="url(#graph-dots)"/>
    <g id="graph-viewport">${edgePathMarkup}${edgeLabelMarkup}${nodeMarkup}</g>
  </svg>`;

  applyGraphTransform();
  bindGraphInteractions();
}

function pickEdgeLabelPosition(geometry, occupied, width, height, allEdges = []) {
  const candidates = [0.5, 0.38, 0.62, 0.28, 0.72, 0.18, 0.82];
  const offsets = [0, 18, -18, 36, -36, 54, -54, 72, -72];
  let best = null;
  let bestScore = Infinity;
  const otherEdges = allEdges.filter((item) => item.index !== geometry.index);
  candidates.forEach((t) => {
    const one = 1 - t;
    const baseX = one * one * geometry.startX + 2 * one * t * geometry.midX + t * t * geometry.endX;
    const baseY = one * one * geometry.startY + 2 * one * t * geometry.midY + t * t * geometry.endY;
    const dx = geometry.endX - geometry.startX;
    const dy = geometry.endY - geometry.startY;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const normalX = -dy / distance;
    const normalY = dx / distance;
    offsets.forEach((offset) => {
      const x = baseX + normalX * offset;
      const y = baseY + normalY * offset;
      const box = {
        x: x - geometry.labelWidth / 2,
        y: y - 11,
        w: geometry.labelWidth,
        h: 22,
      };
      let score = 0;
      if (box.x < 8 || box.y < 8 || box.x + box.w > width - 8 || box.y + box.h > height - 8) {
        score += 100000;
      }
      occupied.forEach((other) => {
        const overlapX = Math.max(0, Math.min(box.x + box.w + 4, other.x + other.w + 4) - Math.max(box.x - 4, other.x - 4));
        const overlapY = Math.max(0, Math.min(box.y + box.h + 4, other.y + other.h + 4) - Math.max(box.y - 4, other.y - 4));
        if (overlapX > 0 && overlapY > 0) {
          score += 1000000 + overlapX * overlapY * 100;
        }
      });
      // 避免标签压到其他关系线上
      otherEdges.forEach((other) => {
        for (let step = 1; step < 20; step += 1) {
          const s = step / 20;
          const o = 1 - s;
          const px = o * o * other.startX + 2 * o * s * other.midX + s * s * other.endX;
          const py = o * o * other.startY + 2 * o * s * other.midY + s * s * other.endY;
          if (px > box.x - 5 && px < box.x + box.w + 5 && py > box.y - 5 && py < box.y + box.h + 5) {
            score += 900;
          }
        }
      });
      if (score < bestScore) {
        bestScore = score;
        best = { x, y };
      }
    });
  });
  return best || { x: geometry.midX, y: geometry.midY };
}

function graphFocus(model) {
  if (state.graphActiveCycle != null) {
    const cycles = graphVisibleCycles(model);
    const cycle = cycles[state.graphActiveCycle];
    if (cycle && cycle.length >= 2) {
      const nodes = new Set(cycle);
      const edges = new Set();
      for (let index = 0; index < cycle.length; index += 1) {
        edges.add(`${cycle[index]}|${cycle[(index + 1) % cycle.length]}`);
      }
      return { active: true, nodes, edges };
    }
  }
  if (state.selectedNode) {
    const nodes = new Set([state.selectedNode]);
    const edges = new Set();
    model.edges.forEach((edge) => {
      if (edge.from === state.selectedNode || edge.to === state.selectedNode) {
        edges.add(`${edge.from}|${edge.to}`);
        nodes.add(edge.from);
        nodes.add(edge.to);
      }
    });
    return { active: true, nodes, edges };
  }
  return { active: false, nodes: new Set(), edges: new Set() };
}

function circleLayout(nodes, edges, width, height) {
  const ordered = orderNodesForCircle(nodes, edges);
  const count = ordered.length;
  if (count === 1) return [{ id: ordered[0].id, x: width / 2, y: height / 2 }];
  const radiusX = Math.min(width * 0.34, 390);
  const radiusY = Math.min(height * 0.30, 230);
  return ordered.map((node, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / count;
    return {
      id: node.id,
      x: width / 2 + Math.cos(angle) * radiusX,
      y: height / 2 + Math.sin(angle) * radiusY,
    };
  });
}

function orderNodesForCircle(nodes, edges) {
  const ids = new Set(nodes.map((node) => node.id));
  const degree = new Map(nodes.map((node) => [node.id, 0]));
  const weights = new Map();
  edges.forEach((edge) => {
    if (!ids.has(edge.from) || !ids.has(edge.to)) return;
    degree.set(edge.from, (degree.get(edge.from) || 0) + 1);
    degree.set(edge.to, (degree.get(edge.to) || 0) + 1);
    const key = `${edge.from}|${edge.to}`;
    weights.set(key, (weights.get(key) || 0) + edge.amount_cents);
  });
  const remaining = new Set(ids);
  const order = [];
  while (order.length < nodes.length) {
    let next = null;
    let bestWeight = -1;
    if (order.length) {
      const last = order[order.length - 1];
      edges.forEach((edge) => {
        const key = `${edge.from}|${edge.to}`;
        if (edge.from === last && remaining.has(edge.to)) {
          const weight = weights.get(key) || 0;
          if (weight > bestWeight) { bestWeight = weight; next = edge.to; }
        } else if (edge.to === last && remaining.has(edge.from)) {
          const weight = weights.get(key) || 0;
          if (weight > bestWeight) { bestWeight = weight; next = edge.from; }
        }
      });
    }
    if (!next) {
      next = nodes
        .filter((node) => remaining.has(node.id))
        .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0))[0]?.id;
    }
    if (!next) break;
    order.push(next);
    remaining.delete(next);
  }
  return order.map((id) => nodes.find((node) => node.id === id)).filter(Boolean);
}

function forceLayout(nodes, edges, width, height) {
  const count = nodes.length;
  const positions = nodes.map((node, index) => {
    const angle = (index / Math.max(1, count)) * Math.PI * 2;
    const radius = Math.min(width, height) * 0.31;
    return {
      x: width / 2 + Math.cos(angle) * radius * (0.75 + (index % 3) * 0.1),
      y: height / 2 + Math.sin(angle) * radius * (0.75 + (index % 4) * 0.08),
      vx: 0,
      vy: 0,
    };
  });
  const indexMap = new Map(nodes.map((node, index) => [node.id, index]));
  const ideal = Math.sqrt((width * height) / Math.max(1, count)) * 0.62;
  let temperature = width / 5;
  const iterations = count > 80 ? 180 : count > 40 ? 240 : 320;
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const displacement = positions.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < count; i += 1) {
      for (let j = i + 1; j < count; j += 1) {
        let dx = positions[i].x - positions[j].x;
        let dy = positions[i].y - positions[j].y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.5) { dx = 0.5 + i * 0.1; dy = 0.5; distance = Math.hypot(dx, dy); }
        const force = (ideal * ideal) / distance;
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        displacement[i].x += fx; displacement[i].y += fy;
        displacement[j].x -= fx; displacement[j].y -= fy;
      }
    }
    edges.forEach((edge) => {
      const from = indexMap.get(edge.from);
      const to = indexMap.get(edge.to);
      if (from == null || to == null) return;
      const dx = positions[to].x - positions[from].x;
      const dy = positions[to].y - positions[from].y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const force = (distance * distance) / ideal * 0.35;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      displacement[from].x += fx; displacement[from].y += fy;
      displacement[to].x -= fx; displacement[to].y -= fy;
    });
    positions.forEach((position, index) => {
      displacement[index].x += (width / 2 - position.x) * 0.01;
      displacement[index].y += (height / 2 - position.y) * 0.01;
      const length = Math.hypot(displacement[index].x, displacement[index].y);
      const limit = Math.max(0.5, temperature);
      if (length > limit) {
        displacement[index].x = (displacement[index].x / length) * limit;
        displacement[index].y = (displacement[index].y / length) * limit;
      }
      position.x += displacement[index].x;
      position.y += displacement[index].y;
      position.x = Math.max(60, Math.min(width - 60, position.x));
      position.y = Math.max(60, Math.min(height - 60, position.y));
    });
    temperature *= 0.985;
  }
  const minX = Math.min(...positions.map((position) => position.x));
  const maxX = Math.max(...positions.map((position) => position.x));
  const minY = Math.min(...positions.map((position) => position.y));
  const maxY = Math.max(...positions.map((position) => position.y));
  const paddingX = 100;
  const paddingY = 90;
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((width - paddingX * 2) / spanX, (height - paddingY * 2) / spanY, 1.45);
  return positions.map((position, index) => ({
    id: nodes[index].id,
    x: (position.x - minX) * scale + paddingX + (width - paddingX * 2 - spanX * scale) / 2,
    y: (position.y - minY) * scale + paddingY + (height - paddingY * 2 - spanY * scale) / 2,
  }));
}

function applyGraphTransform() {
  const viewport = $('#graph-viewport');
  if (!viewport) return;
  const transform = state.graphTransform;
  viewport.setAttribute('transform', `translate(${transform.x} ${transform.y}) scale(${transform.k})`);
}

function zoomGraphAt(worldX, worldY, factor) {
  const transform = state.graphTransform;
  const scale = Math.min(3.2, Math.max(0.55, transform.k * factor));
  const ratio = scale / transform.k;
  transform.x = worldX - (worldX - transform.x) * ratio;
  transform.y = worldY - (worldY - transform.y) * ratio;
  transform.k = scale;
  applyGraphTransform();
}

function changeGraphZoom(factor) {
  zoomGraphAt(320, 225, factor);
}

function resetGraphView() {
  state.graphTransform = { x: 0, y: 0, k: 1 };
  applyGraphTransform();
}

function bindGraphInteractions() {
  const svg = $('#graph-svg');
  if (!svg) return;
  const width = 640;
  const height = 450;
  svg.addEventListener('wheel', (event) => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    const worldX = ((event.clientX - rect.left) / rect.width) * width;
    const worldY = ((event.clientY - rect.top) / rect.height) * height;
    zoomGraphAt(worldX, worldY, Math.exp(-event.deltaY * 0.0012));
  }, { passive: false });

  let panning = null;
  svg.addEventListener('pointerdown', (event) => {
    if (event.target.closest('.graph-node')) return;
    panning = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: state.graphTransform.x,
      originY: state.graphTransform.y,
    };
    svg.setPointerCapture(event.pointerId);
    svg.classList.add('panning');
  });
  svg.addEventListener('pointermove', (event) => {
    if (!panning || panning.pointerId !== event.pointerId) return;
    const rect = svg.getBoundingClientRect();
    const dx = ((event.clientX - panning.startX) / rect.width) * width;
    const dy = ((event.clientY - panning.startY) / rect.height) * height;
    state.graphTransform.x = panning.originX + dx;
    state.graphTransform.y = panning.originY + dy;
    applyGraphTransform();
  });
  const endPan = (event) => {
    if (!panning) return;
    panning = null;
    svg.classList.remove('panning');
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
  };
  svg.addEventListener('pointerup', endPan);
  svg.addEventListener('pointercancel', endPan);
}

function selectGraphNode(nodeId) {
  state.selectedNode = nodeId;
  state.graphActiveCycle = null;
  drawGraph();
  const side = $('#graph-side');
  if (side) side.innerHTML = graphSideHtml();
}

function selectGraphCycle(index) {
  if (state.graphActiveCycle === Number(index)) {
    clearGraphHighlight();
    return;
  }
  state.graphActiveCycle = Number(index);
  state.selectedNode = null;
  drawGraph();
  const side = $('#graph-side');
  if (side) side.innerHTML = graphSideHtml();
}

function clearGraphHighlight() {
  state.selectedNode = null;
  state.graphActiveCycle = null;
  drawGraph();
  const side = $('#graph-side');
  if (side) side.innerHTML = graphSideHtml();
}


/* ------------------------------------------------------------------ 方案 */
function viewPlan() {
  const plan = state.plan;
  if (!plan) {
    return `<div class="card">${emptyState('↻', '还没有清偿方案',
      '台账中已有合格的债务后，运行净额轧差，系统会按主体汇总净头寸，并求解交易笔数最少的清偿安排。',
      '<div class="row" style="justify-content:center"><button class="btn btn-primary" data-action="run-netting">运行净额轧差</button><a class="btn" href="#/debts">查看债务台账</a></div>')}</div>
      ${planHistoryHtml()}`;
  }
  const summary = plan.summary || {};
  const isPure = (plan.mode || summary.mode) === 'pure';
  const modeLabel = plan.mode_label || summary.mode_label || (isPure ? '纯数学口径（忽略法规限制）' : '法律合规口径');
  const comparisonMarkup = state.comparison ? comparisonHtml(state.comparison, plan.mode || 'legal') : '';
  const optimality = summary.optimality === 'proven'
    ? `<div class="notice notice-ok"><span>✓</span><div><strong>已证明最优：</strong>${summary.transaction_count} 笔交易 = 参与主体数 − 最大零和划分数，金额全部结清。${summary.doc_lower_bound !== summary.transaction_count ? `低于单组下界 ${summary.doc_lower_bound} 笔，原因是存在金额可直接对冲的独立子组。` : ''}</div></div>`
    : `<div class="notice notice-warn"><span>!</span><div><strong>启发式近优：</strong>参与主体较多，求解器在时间预算内未完成全局最优性证明；当前方案金额完全结清，交易笔数为近优解。</div></div>`;

  return `
  <div class="plan-hero">
    <div>
      <div class="row" style="margin-bottom:6px"><span class="badge badge-ok">方案已生成</span>
        <span class="badge badge-navy">${esc(plan.name || `核算 #${plan.seq || '—'}`)}</span>
        <span class="badge ${isPure ? 'badge-warn' : 'badge-info'}">${esc(modeLabel)}</span>
        <span class="badge badge-navy">基准日 ${esc(plan.as_of_date)}</span>
        <span class="badge badge-neutral">${esc(plan.id)}</span></div>
      <h2>${summary.transaction_count} 笔交易，覆盖 ${summary.included_count} 笔${isPure ? '台账' : '原始'}债务</h2>
      <p>生成于 ${fmtDateTime(plan.created_at)} · ${isPure ? '全部债务合并计算（不区分顺位）' : `覆盖 ${summary.group_count} 个顺位分组`} · 清偿总额 ¥${fmtMoney(summary.transaction_amount)}</p>
    </div>
    <div class="row">
      <a class="btn btn-ghost" href="#/records">← 核算记录</a>
      ${isPure ? '' : `<button class="btn" data-action="generate-narrative" data-id="${plan.id}">AI 解读</button>`}
      <a class="btn" href="/api/export/plan_xlsx?plan_id=${encodeURIComponent(plan.id)}">导出 Excel</a>
      <a class="btn" href="/api/export/plan_docx?plan_id=${encodeURIComponent(plan.id)}">方案报告</a>
      ${isPure ? '' : `<a class="btn btn-primary" href="/api/export/agreement_docx?plan_id=${encodeURIComponent(plan.id)}">协议草稿</a>`}
    </div>
  </div>

  ${isPure ? `<div class="notice notice-danger" style="margin-top:14px"><span>!</span><div>
    <strong>纯数学口径：</strong>本方案忽略争议、查封冻结、到期状态、禁止抵销约定与优先顺位分组，全部非人工排除债务合并计算。仅用于测算理论最少交易笔数与资金规模，<strong>不能生成抵销协议，也不能作为实际清偿依据</strong>；落地请使用法律合规口径方案并交法务审核。
  </div></div>` : ''}

  ${plainSummaryHtml(plan)}

  ${comparisonMarkup}

  <div class="plan-detail-toggle">
    <button class="btn" data-action="toggle-plan-detail">${state.planDetailOpen ? '收起专业明细' : '查看专业明细（分组 / 净头寸 / 校验）'}</button>
    <span>普通用户看上面的“谁给谁钱”即可；专业明细供财务与法务复核。</span>
  </div>

  <div class="plan-detail ${state.planDetailOpen ? '' : 'hidden'}">
  ${optimality}

  ${plan.ai_narrative ? `<section class="card" style="margin-top:16px">
    <div class="card-head"><div><h3>方案解读</h3><p>由线上模型基于本地已算出的数字方案生成，未回传原始合同文本</p></div>
      <span class="badge badge-info">AI 辅助 · ${esc(plan.ai_narrative.model || '')}</span></div>
    <div class="card-body" style="white-space:pre-wrap;font-size:13px;line-height:1.85;color:#344054">${esc(plan.ai_narrative.content)}</div>
  </section>` : ''}

  <div class="summary-strip" style="margin-top:16px">
    <div class="summary-cell"><span>清偿交易</span><strong>${summary.transaction_count}<small>笔</small></strong></div>
    <div class="summary-cell"><span>清偿总额</span><strong>${fmtCompact(summary.transaction_amount_cents)}</strong></div>
    <div class="summary-cell"><span>净债务人</span><strong>${summary.debtor_count}<small>个</small></strong></div>
    <div class="summary-cell"><span>净债权人</span><strong>${summary.creditor_count}<small>个</small></strong></div>
    <div class="summary-cell"><span>头寸归零出局</span><strong>${summary.zero_out_count}<small>个</small></strong></div>
    <div class="summary-cell"><span>纳入 / 未入池债务</span><strong>${summary.included_count}<small>/ ${summary.excluded_count}</small></strong></div>
  </div>

  <div class="stack" style="margin-top:18px">
    ${(plan.groups || []).map((group) => groupCardHtml(group)).join('')}
  </div>

  <div class="grid-2" style="margin-top:18px">
    <section class="card">
      <div class="card-head"><div><h3>方案校验</h3><p>金额守恒、分组隔离与最优性检查</p></div></div>
      <div class="card-body check-list">
        ${(plan.checks || []).map((check) => `<div class="check-item">
          <span class="check-icon ${check.ok ? 'check-ok' : 'check-bad'}">${check.ok ? '✓' : '!'}</span>
          <div><strong>${esc(check.name)}</strong><span>${esc(check.detail || '')}</span></div>
        </div>`).join('')}
      </div>
    </section>
    <section class="card">
      <div class="card-head"><div><h3>未入池债务</h3><p>被规则阻断或待复核，不参与本次轧差</p></div></div>
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>债务关系</th><th class="num">金额</th><th>原因</th></tr></thead>
          <tbody>
            ${(plan.excluded || []).length ? plan.excluded.map((item) => `<tr>
              <td>${esc(item.debtor_name)} <span class="dir">→</span> ${esc(item.creditor_name)}<div class="tiny muted">${esc(item.status_label)}</div></td>
              <td class="num">¥${fmtCents(item.amount_cents)}</td>
              <td class="tiny">${esc(item.reasons.join('；'))}<div style="margin-top:3px">${item.rule_ids.map((id) => `<span class="chip">${esc(id)}</span>`).join(' ')}</div></td>
            </tr>`).join('') : '<tr><td colspan="3" class="tiny muted" style="padding:16px">全部债务均已入池。</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
  </div>

  ${liquidityHtml(plan)}
  ${riskNotesHtml(plan)}
  ${planHistoryHtml()}
  </div>`;
}

function plainMoney(cents) {
  const value = Number(cents || 0) / 100;
  if (Math.abs(value) >= 10000) {
    return `${Number((value / 10000).toFixed(2))} 万`;
  }
  return `${Number(value.toFixed(2))} 元`;
}

function plainGroupName(code) {
  const names = {
    ordinary: '普通货款',
    mortgage: '抵押贷款',
    wage: '职工工资',
    tax: '税款',
    custom: '其他优先款',
    all: '全部合并',
    mixed: '混合',
  };
  return names[code] || GROUP_LABELS[code] || '欠款';
}

function plainReason(item) {
  const text = (item.reasons || []).join('；');
  if (text.includes('争议')) return '有争议，先不算';
  if (text.includes('查封') || text.includes('冻结')) return '被法院查封/冻结，先不算';
  if (text.includes('未到期')) return '还没到还款日，先不算';
  if (text.includes('禁止抵销')) return '合同写明不能互相抵，先不算';
  if (text.includes('待人工复核') || text.includes('尚未确认')) return '还没确认，先不算';
  if (text.includes('人为排除')) return '已经被人为排除';
  if (text.includes('优先顺位分组未启用')) return '优先顺位分组没有启用';
  return '法律上暂时不能算';
}

function plainSummaryHtml(plan) {
  const summary = plan.summary || {};
  const isPure = (plan.mode || summary.mode) === 'pure';
  const transactions = plan.transactions || [];
  const payers = new Map();
  const receivers = new Map();
  transactions.forEach((tx) => {
    payers.set(tx.from_name, (payers.get(tx.from_name) || 0) + Number(tx.amount_cents || 0));
    receivers.set(tx.to_name, (receivers.get(tx.to_name) || 0) + Number(tx.amount_cents || 0));
  });
  const sortTotals = (map) => Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  const payerRows = sortTotals(payers);
  const receiverRows = sortTotals(receivers);
  const included = plan.included_debts || [];
  const excluded = plan.excluded || [];
  const adjusted = state.comparison?.adjusted_debts || [];
  const constrained = (plan.liquidity || {}).constrained || [];
  const totalCents = Number(summary.transaction_amount_cents || 0);

  const paymentRows = transactions.map((tx) => `<tr>
    <td><strong>${esc(graphNodeDisplayName(tx.from_name))}</strong></td>
    <td>${esc(graphNodeDisplayName(tx.to_name))}</td>
    <td class="num"><strong>${plainMoney(tx.amount_cents)}</strong></td>
    <td class="muted">${esc(plainGroupName(tx.group_code))}</td>
  </tr>`).join('');

  const payerList = payerRows.map(([name, amount]) => `<div class="plain-party-line">
    <span class="plain-party-tag pay">付钱</span>
    <span class="grow">${esc(graphNodeDisplayName(name))}</span>
    <strong>${plainMoney(amount)}</strong>
  </div>`).join('');
  const receiverList = receiverRows.map(([name, amount]) => `<div class="plain-party-line">
    <span class="plain-party-tag receive">收钱</span>
    <span class="grow">${esc(graphNodeDisplayName(name))}</span>
    <strong>${plainMoney(amount)}</strong>
  </div>`).join('');

  const includedList = included.map((item) => `<li>
    ${esc(graphNodeDisplayName(item.debtor_name))} 欠 ${esc(graphNodeDisplayName(item.creditor_name))}
    <strong>${plainMoney(item.amount_cents)}</strong>
    <span class="muted">（${esc(plainGroupName(item.group_code))}）</span>
  </li>`).join('');

  const unresolvedRows = excluded.map((item) => `<li>
    ${esc(graphNodeDisplayName(item.debtor_name))} 欠 ${esc(graphNodeDisplayName(item.creditor_name))}
    <strong>${plainMoney(item.amount_cents)}</strong>
    <span class="plain-unresolved-reason">${esc(plainReason(item))}</span>
  </li>`).join('');

  const pureExtraRows = isPure && adjusted.length ? adjusted.map((item) => `<li>
    ${esc(graphNodeDisplayName(item.debtor_name))} 欠 ${esc(graphNodeDisplayName(item.creditor_name))}
    <strong>${plainMoney(item.amount_cents)}</strong>
    <span class="plain-unresolved-reason">${esc((item.legal_reasons || []).join('；') || '法律口径未入池')}</span>
  </li>`).join('') : '';

  const liquidity = constrained.length ? `<div class="plain-alert">
    <strong>钱可能不够：</strong>
    ${constrained.map((item) => `${esc(graphNodeDisplayName(item.name))} 手头只有 ${plainMoney(item.available_cash_cents)}，
      这次要付 ${plainMoney(item.payable_cents)}，还差 ${plainMoney(item.shortfall_cents)}`).join('；')}。
    系统已生成分期建议，实际付款前要先把资金安排落实。
  </div>` : '';

  return `<section class="card plain-card">
    <div class="card-head">
      <div><h3>大白话：谁给谁钱</h3><p>${isPure
        ? '把全部欠条放一起纯算账，只用于看“最少几笔”，不能拿去执行'
        : '只算法律上能互相冲的欠条；抵押和工资单独还'}</p></div>
      <span class="badge ${isPure ? 'badge-warn' : 'badge-ok'}">${isPure ? '仅供测算' : '可以拿去谈'}</span>
    </div>
    <div class="card-body">
      <div class="plain-lead">这次一共 <strong>${transactions.length}</strong> 笔付款，合计 <strong>${plainMoney(totalCents)}</strong>。</div>

      <div class="plain-grid">
        <div>
          <div class="mini-title">谁给谁钱</div>
          <div class="table-wrap plain-table-wrap">
            <table class="plain-table">
              <thead><tr><th>谁付钱</th><th>给谁</th><th class="num">多少钱</th><th>什么钱</th></tr></thead>
              <tbody>${paymentRows || '<tr><td colspan="4" class="muted">不需要付款。</td></tr>'}</tbody>
            </table>
          </div>
          ${isPure ? '<p class="plain-note">例如“中鑫给工会 80 万”只是数学上刚好配对，不代表中鑫欠工资；现实里工资仍是华远欠的。</p>' : ''}
        </div>
        <div>
          <div class="mini-title">谁出钱、谁收钱</div>
          <div class="plain-party-group">
            <div class="plain-party-heading">出钱的一方</div>
            ${payerList || '<p class="tiny muted">没有付款方。</p>'}
            <div class="plain-party-heading" style="margin-top:10px">收钱的一方</div>
            ${receiverList || '<p class="tiny muted">没有收款方。</p>'}
          </div>
        </div>
      </div>

      <details class="plain-details">
        <summary>这次算进来的欠条（${included.length} 笔）</summary>
        <ul>${includedList || '<li>无</li>'}</ul>
      </details>

      ${isPure ? `
        ${adjusted.length ? `<details class="plain-details" open>
          <summary>纯算账时多算进来的欠条（${adjusted.length} 笔）</summary>
          <ul>${pureExtraRows}</ul>
        </details>` : '<p class="plain-note">这是单次纯算账结果；点“两口径对比”可以看到具体多算了哪些欠条。</p>'}
        <div class="plain-alert">
          <strong>重要：</strong>这个版本把有争议、被查封、没到期、合同禁止抵销、还没确认的欠条全部算进来了，
          还把工资和普通货款混在一起。它只能用来算“理论上最少几笔”，<strong>不能签协议，也不能要求别人按这个付钱</strong>。
        </div>
      ` : `
        <details class="plain-details" ${excluded.length ? 'open' : ''}>
          <summary>这次没算的欠条（${excluded.length} 笔）——不是不用还，是要另外处理</summary>
          <ul>${unresolvedRows || '<li>没有未入池债务。</li>'}</ul>
        </details>
        <div class="plain-alert">
          <strong>提醒：</strong>这个版本要所有欠钱的人和收钱的人一起签字确认后才生效，不是法院自动判决。
          抵押贷款和工资是单独算的，没有和普通货款混在一起。
        </div>
      `}

      ${liquidity}
    </div>
  </section>`;
}


function viewRecords() {
  const plans = (state.plans || []).slice().sort((a, b) => (Number(a.seq) || 0) - (Number(b.seq) || 0));
  const latestSeq = plans.reduce((max, item) => Math.max(max, Number(item.seq) || 0), 0);
  const legalCount = plans.filter((item) => (item.summary?.mode || 'legal') === 'legal').length;
  const pureCount = plans.filter((item) => item.summary?.mode === 'pure').length;
  const rows = plans.map((item) => {
    const summary = item.summary || {};
    const isLatest = Number(item.seq) === latestSeq;
    return `<tr>
      <td><span class="record-seq">#${esc(item.seq ?? '—')}</span></td>
      <td>
        <strong>${esc(item.name || `核算 #${item.seq || ''}`)}</strong>
        ${isLatest ? '<span class="badge badge-ok" style="margin-left:6px">最新</span>' : ''}
        <div class="tiny muted mono">${esc(item.id)}</div>
      </td>
      <td>${fmtDateTime(item.created_at)}</td>
      <td><span class="badge ${summary.mode === 'pure' ? 'badge-warn' : 'badge-info'}">${summary.mode === 'pure' ? '纯数学口径' : '法律合规口径'}</span></td>
      <td class="num">${summary.debt_count ?? '—'}</td>
      <td class="num">${summary.included_count ?? '—'} <span class="muted">/</span> ${summary.excluded_count ?? '—'}</td>
      <td class="num"><strong>${summary.transaction_count ?? '—'}</strong><div class="tiny muted">${summary.optimality === 'proven' ? '已证明最优' : '启发式'}</div></td>
      <td class="num">¥${fmtCents(summary.transaction_amount_cents)}</td>
      <td>
        <div class="row" style="gap:4px;flex-wrap:nowrap">
          <button class="btn btn-sm btn-primary" data-action="open-plan" data-id="${esc(item.id)}">查看</button>
          <button class="btn btn-sm btn-ghost" data-action="show-batch-debts" data-id="${esc(item.id)}">清单</button>
          <button class="btn btn-sm btn-ghost" data-action="delete-plan" data-id="${esc(item.id)}">删除</button>
        </div>
      </td>
    </tr>`;
  }).join('');

  return `<section class="card">
    <div class="card-head">
      <div><h3>核算记录</h3><p>当前工作记录：<b>${esc(state.activeCase?.name || '—')}</b> · 这里只列出本记录内的核算，可回看或开始新的核算</p></div>
      <div class="row">
        <button class="btn btn-sm btn-ghost" data-action="rerender">刷新</button>
      </div>
    </div>
    <div class="card-body">
      <div class="records-kpis">
        <div><strong>${plans.length}</strong><span>累计核算次数</span></div>
        <div><strong>#${latestSeq || '—'}</strong><span>最新编号</span></div>
        <div><strong>${legalCount}</strong><span>法律合规口径</span></div>
        <div><strong>${pureCount}</strong><span>纯数学口径</span></div>
      </div>
      ${plans.length ? `<div class="table-wrap" style="margin-top:16px">
        <table class="data records-table">
          <thead><tr><th>编号</th><th>核算名称</th><th>生成时间</th><th>口径</th><th class="num">债务总数</th><th class="num">入池 / 未入池</th><th class="num">付款笔数</th><th class="num">付款总额</th><th>操作</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>` : `<div class="empty" style="padding:40px 10px">
        <div class="empty-icon">↻</div>
        <p>还没有核算记录。台账准备好后，点“新建核算”开始第一次债务核算。</p>
        <button class="btn btn-primary" data-action="run-netting">新建第一次核算</button>
      </div>`}
    </div>
  </section>`;
}

async function showBatchDebts(planId) {
  try {
    const plan = await api(`/api/plans/${planId}`);
    const snapshot = plan.debts_snapshot || [];
    const rows = snapshot.length ? snapshot.map((item, index) => `<tr>
      <td class="num">${index + 1}</td>
      <td>${esc(item.debtor_name)} <span class="dir">→</span> ${esc(item.creditor_name)}</td>
      <td class="num">¥${fmtCents(item.amount_cents)}</td>
      <td>${esc(item.due_date || '—')}</td>
      <td><span class="chip">${esc(item.group_label || '—')}</span><div class="tiny muted">${esc(item.status_label || '')}</div></td>
      <td>${item.included ? '<span class="badge badge-ok">已入池</span>' : '<span class="badge badge-warn">未入池</span>'}</td>
      <td class="tiny">${item.included && plan.mode === 'pure'
        ? '纯数学口径纳入'
        : esc((item.reasons && item.reasons.length ? item.reasons : item.legal_reasons || []).join('；') || '—')}</td>
    </tr>`).join('') : (() => {
      const fallback = [
        ...(plan.included_debts || []).map((item) => ({ ...item, included: true, group_label: item.group_label, reasons: [] })),
        ...(plan.excluded || []).map((item) => ({ ...item, included: false, group_label: '', reasons: item.reasons })),
      ];
      if (!fallback.length) return '<tr><td colspan="7" class="muted">这份历史记录没有保存债务快照。</td></tr>';
      return fallback.map((item, index) => `<tr>
        <td class="num">${index + 1}</td>
        <td>${esc(item.debtor_name)} <span class="dir">→</span> ${esc(item.creditor_name)}</td>
        <td class="num">¥${fmtCents(item.amount_cents)}</td>
        <td>—</td><td>${esc(item.group_label || '—')}</td>
        <td>${item.included ? '<span class="badge badge-ok">已入池</span>' : '<span class="badge badge-warn">未入池</span>'}</td>
        <td class="tiny">${esc((item.reasons || []).join('；') || '—')}</td>
      </tr>`).join('');
    })();
    openModal({
      title: `${plan.name || `核算 #${plan.seq}`} · 债务清单`,
      subtitle: `${fmtDateTime(plan.created_at)} · 共 ${snapshot.length || plan.summary?.debt_count || ((plan.included_debts || []).length + (plan.excluded || []).length)} 笔债务 · ${plan.mode_label || ''}`,
      wide: true,
      body: `<div class="table-wrap" style="border:1px solid #e2e8f0;border-radius:10px">
        <table class="data">
          <thead><tr><th class="num">#</th><th>债务关系</th><th class="num">金额</th><th>到期日</th><th>分组 / 状态</th><th>是否入池</th><th>说明</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`,
      footer: `<button class="btn" data-close>关闭</button>
               <button class="btn btn-primary" data-action="open-plan" data-id="${esc(plan.id)}">打开这次方案</button>`,
    });
  } catch (error) {
    toast(error.message, 'err');
  }
}

async function deletePlan(planId) {
  const plan = (state.plans || []).find((item) => item.id === planId);
  const label = plan ? (plan.name || `核算 #${plan.seq}`) : planId;
  const yes = await confirmDialog('删除核算记录', `确认删除“${label}”？债务台账本身不会删除，只删除这次核算的快照和方案。`, '删除', true);
  if (!yes) return;
  try {
    await api(`/api/plans/${planId}`, { method: 'DELETE' });
    toast('核算记录已删除。');
    await loadPlans();
    if (state.plan?.id === planId) await loadPlan();
    await renderView();
  } catch (error) {
    toast(error.message, 'err');
  }
}

function comparisonHtml(comparison, selectedMode) {
  const legal = comparison.transaction_count?.legal ?? 0;
  const pure = comparison.transaction_count?.pure ?? 0;
  const legalAmount = comparison.amount_cents?.legal ?? 0;
  const pureAmount = comparison.amount_cents?.pure ?? 0;
  const diffTx = comparison.transaction_count?.difference ?? (pure - legal);
  const diffAmount = comparison.amount_cents?.difference ?? (pureAmount - legalAmount);
  const adjusted = comparison.adjusted_debts || [];
  const legalIncluded = comparison.included_count?.legal ?? 0;
  const pureIncluded = comparison.included_count?.pure ?? 0;
  const legalExcluded = comparison.excluded_count?.legal ?? 0;
  const pureExcluded = comparison.excluded_count?.pure ?? 0;
  const diffText = diffTx === 0
    ? '两种口径交易笔数相同'
    : `纯数学口径${diffTx < 0 ? '少' : '多'} ${Math.abs(diffTx)} 笔交易`;
  const amountText = diffAmount === 0
    ? '支付总额相同'
    : `支付总额${diffAmount < 0 ? '少' : '多'} ¥${fmtCents(Math.abs(diffAmount))}`;

  return `<section class="card compare-card">
    <div class="card-head"><div><h3>两种口径对比</h3><p>法律合规口径用于实际落地；纯数学口径只用于测算理论边界</p></div>
      <span class="badge badge-neutral">同一批台账债务</span></div>
    <div class="card-body">
      <div class="compare-grid">
        <div class="compare-option ${selectedMode === 'legal' ? 'active' : ''}">
          <div class="row"><span class="badge badge-ok">推荐落地</span><span class="badge badge-neutral">法律合规口径</span></div>
          <div class="compare-stats">
            <div><strong>${legal}</strong><span>交易笔数</span></div>
            <div><strong>${fmtCompact(legalAmount)}</strong><span>支付总额</span></div>
            <div><strong>${legalIncluded}</strong><span>纳入债务</span></div>
            <div><strong>${legalExcluded}</strong><span>未入池</span></div>
          </div>
          <p>逐笔通过本体规则校验；排除争议、查封、未到期、禁止抵销与待复核债务；抵押、工资等优先分组独立轧差。</p>
          <button class="btn btn-sm ${selectedMode === 'legal' ? 'btn-primary' : ''}" data-action="show-plan-mode" data-mode="legal">查看法律方案</button>
        </div>
        <div class="compare-option ${selectedMode === 'pure' ? 'active' : ''}">
          <div class="row"><span class="badge badge-warn">仅测算</span><span class="badge badge-neutral">纯数学口径</span></div>
          <div class="compare-stats">
            <div><strong>${pure}</strong><span>交易笔数</span></div>
            <div><strong>${fmtCompact(pureAmount)}</strong><span>支付总额</span></div>
            <div><strong>${pureIncluded}</strong><span>纳入债务</span></div>
            <div><strong>${pureExcluded}</strong><span>未入池</span></div>
          </div>
          <p>忽略法规限制、到期状态与优先分组，全部非人工排除债务合并计算，只求数学上的最少交易笔数。</p>
          <button class="btn btn-sm ${selectedMode === 'pure' ? 'btn-primary' : ''}" data-action="show-plan-mode" data-mode="pure">查看纯数学方案</button>
        </div>
      </div>
      <div class="compare-summary">
        <span class="badge badge-info">${esc(diffText)}</span>
        <span class="badge badge-info">${esc(amountText)}</span>
        <span class="badge badge-neutral">纯口径纳入 ${adjusted.length} 笔法律口径未入池债务</span>
      </div>
      ${adjusted.length ? `<div class="compare-adjusted">
        <div class="mini-title">纯数学口径额外纳入的债务</div>
        <div class="compare-debt-list">
          ${adjusted.slice(0, 8).map((item) => `<div class="compare-debt">
            <span class="grow">${esc(item.debtor_name)} <span class="dir">→</span> ${esc(item.creditor_name)}</span>
            <span class="val">¥${fmtCents(item.amount_cents)}</span>
            <span class="tiny muted">${esc((item.legal_reasons || []).join('；') || '法律口径未入池')}</span>
          </div>`).join('')}
          ${adjusted.length > 8 ? `<p class="tiny muted">另有 ${adjusted.length - 8} 笔。</p>` : ''}
        </div>
      </div>` : ''}
      <div class="notice notice-warn" style="margin-top:12px"><span>!</span><div>
        纯数学口径合并了优先顺位分组，并忽略争议、查封、到期与禁止抵销约定；其结果<strong>不能生成协议，也不能直接执行</strong>。
      </div></div>
    </div>
  </section>`;
}


function groupCardHtml(group) {
  const txHtml = group.transactions.length
    ? group.transactions.map((tx) => `<div class="flow-row">
        <span class="from">${esc(truncate(tx.from_name, 14))}</span>
        <span class="flow-arrow">→</span>
        <span class="to">${esc(truncate(tx.to_name, 14))}</span>
        <span class="flow-amount">¥${fmtCents(tx.amount_cents)}</span>
      </div>`).join('')
    : '<p class="tiny muted">本组头寸全部归零，无需资金流转。</p>';
  const positionHtml = group.participants.map((item) => `<div class="flow-row">
      <span class="from">${esc(truncate(item.name, 14))}</span>
      <span class="badge ${item.role === 'debtor' ? 'badge-danger' : item.role === 'creditor' ? 'badge-ok' : 'badge-neutral'}">${esc(item.role_label)}</span>
      <span class="to">${item.net_cents > 0 ? '+' : ''}¥${fmtCents(item.net_cents)}</span>
      <span class="flow-amount tiny muted">${item.zero_out ? '出局' : ''}</span>
    </div>`).join('');
  return `<section class="group-card">
    <div class="group-head">
      <h3>${esc(group.label)}</h3>
      <span class="group-meta">${group.debt_count} 笔债务 · ${group.m} 个净债务人 / ${group.n} 个净债权人</span>
      <div class="spacer"></div>
      <span class="badge badge-info">${group.transactions.length} 笔交易</span>
      <span class="badge ${group.optimality === 'proven' ? 'badge-ok' : 'badge-warn'}">${group.optimality === 'proven' ? '已证明最优' : '启发式'}</span>
    </div>
    <div class="group-body">
      <div class="group-pane">
        <div class="mini-title">最简清偿清单</div>
        ${txHtml}
      </div>
      <div class="group-pane">
        <div class="mini-title">净头寸（应收 − 应付）</div>
        ${positionHtml}
      </div>
    </div>
  </section>`;
}

function liquidityHtml(plan) {
  const liquidity = plan.liquidity || {};
  if (!liquidity.constrained || !liquidity.constrained.length) return '';
  return `<section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>资金约束与分期建议</h3><p>净债务人可动用资金不足以覆盖应付净额，建议在协议中安排分期</p></div>
      <span class="badge badge-warn">缺口 ¥${fmtCents(liquidity.total_shortfall_cents)}</span></div>
    <div class="card-body stack">
      ${liquidity.constrained.map((item) => `<div class="notice notice-warn"><span>¥</span><div>
        <strong>${esc(item.name)}</strong> 应付出 ¥${fmtCents(item.payable_cents)}，可动用资金 ¥${fmtCents(item.available_cash_cents)}，
        资金缺口 <strong>¥${fmtCents(item.shortfall_cents)}</strong>。
      </div></div>`).join('')}
      ${(liquidity.schedule || []).length ? `<div class="table-wrap" style="border:1px solid #e2e8f0;border-radius:10px">
        <table class="data"><thead><tr><th>期次</th><th>付款方</th><th>收款方</th><th class="num">金额</th><th>建议付款日</th></tr></thead>
        <tbody>${liquidity.schedule.map((item) => `<tr>
          <td>第 ${item.period} 期</td><td>${esc(item.payer_name)}</td><td>${esc(item.payee_name)}</td>
          <td class="num">¥${fmtCents(item.amount_cents)}</td><td>${fmtDate(item.due_date)}</td></tr>`).join('')}
        </tbody></table></div>` : ''}
      <p class="tiny muted">分期建议不改变净额轧差的最小交易笔数，仅供签约时参考；是否接受由各方协商确定。</p>
    </div>
  </section>`;
}

function riskNotesHtml(plan) {
  const notes = plan.risk_notes || [];
  if (!notes.length) return '';
  return `<section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>法律边界与风险提示</h3><p>方案性质：多方清偿安排，非法定自动抵销</p></div></div>
    <div class="card-body"><ul style="margin:0;padding-left:18px;color:#475467;font-size:12.5px;line-height:1.8">
      ${notes.map((note) => `<li>${esc(note)}</li>`).join('')}
    </ul></div>
  </section>`;
}

function planHistoryHtml() {
  if (!state.plans.length) return '';
  const recent = state.plans.slice(0, 8);
  return `<section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>核算记录</h3><p>每次运行都会按编号保存；当前显示最近 ${recent.length} 条</p></div>
      <a class="btn btn-sm" href="#/records">查看全部 ${state.plans.length} 条 →</a></div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>编号</th><th>核算名称</th><th>生成时间</th><th>计算口径</th><th class="num">付款笔数</th><th class="num">付款总额</th><th>操作</th></tr></thead>
        <tbody>${recent.map((item) => `<tr>
          <td><span class="record-seq">#${esc(item.seq ?? '—')}</span></td>
          <td><strong>${esc(item.name || `核算 #${item.seq || ''}`)}</strong><div class="tiny muted mono">${esc(item.id)}</div></td>
          <td>${fmtDateTime(item.created_at)}</td>
          <td>${item.summary?.mode === 'pure'
            ? '<span class="badge badge-warn">纯数学口径</span>'
            : '<span class="badge badge-info">法律合规口径</span>'}</td>
          <td class="num">${item.summary?.transaction_count ?? '—'}</td>
          <td class="num">¥${fmtCents(item.summary?.transaction_amount_cents)}</td>
          <td><div class="row" style="gap:5px;flex-wrap:nowrap">
            <button class="btn btn-sm btn-ghost" data-action="open-plan" data-id="${esc(item.id)}">查看</button>
            <button class="btn btn-sm btn-ghost" data-action="show-batch-debts" data-id="${esc(item.id)}">债务清单</button>
          </div></td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 审计 */
function viewAudit() {
  const items = state.audit;
  return `<section class="card">
    <div class="card-head"><div><h3>操作与推理留痕</h3><p>最近 ${items.length} 条记录，按时间倒序</p></div>
      <span class="badge badge-info">本地存储</span></div>
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>时间</th><th>操作</th><th>操作人</th><th>明细</th></tr></thead>
        <tbody>
          ${items.length ? items.map((item) => `<tr>
            <td class="nowrap">${fmtDateTime(item.ts)}</td>
            <td><span class="badge badge-neutral">${esc(ACTION_LABELS[item.action] || item.action)}</span></td>
            <td>${esc(item.actor || '本地用户')}</td>
            <td class="tiny muted" style="max-width:520px;word-break:break-all">${esc(JSON.stringify(item.detail || {}))}</td>
          </tr>`).join('') : '<tr><td colspan="4" class="tiny muted" style="padding:18px">暂无记录。</td></tr>'}
        </tbody>
      </table>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 设置 */
function viewSettings() {
  const settings = state.settings || {};
  const ontology = state.bootstrap?.ontology || {};
  const rules = state.bootstrap?.rules || [];
  const llm = settings.llm || {};
  const providers = settings.providers || {};
  return `
  <div class="grid-2">
    <section class="card">
      <div class="card-head"><div><h3>计算口径</h3><p>影响抵销资格判定与求解精度</p></div></div>
      <div class="card-body">
        <form id="settings-form" class="stack">
          <div class="form-grid">
            <div class="field"><label>基准日</label><input name="as_of_date" type="date" value="${esc(settings.as_of_date || '')}"><div class="hint">留空表示当天；当前生效：${esc(state.bootstrap?.as_of_date || '当天')}</div></div>
            <div class="field"><label>精确求解时间预算（秒）</label><input name="exact_solver_seconds" type="number" min="0.2" max="30" step="0.1" value="${settings.exact_solver_seconds || 3}"><div class="hint">超出预算自动回退启发式并标注</div></div>
          </div>
          <div class="switch-row">
            <div class="switch-copy"><strong>优先顺位分组独立轧差</strong><span>抵押、工资、税款等分组各自计算，不与普通债权混算</span></div>
            <label class="check"><input type="checkbox" name="include_priority_groups" ${settings.include_priority_groups ? 'checked' : ''}></label>
          </div>
          <div class="switch-row">
            <div class="switch-copy"><strong>允许上传原始材料文本</strong><span>关闭后，材料抽取只能使用本地规则，不向线上模型发送任何文本</span></div>
            <label class="check"><input type="checkbox" name="allow_text_upload" ${settings.allow_text_upload ? 'checked' : ''}></label>
          </div>
          <div class="switch-row">
            <div class="switch-copy"><strong>上传前脱敏</strong><span>主体名称、证件号码、账号与联系方式替换为代号</span></div>
            <label class="check"><input type="checkbox" name="masking" ${settings.masking ? 'checked' : ''}></label>
          </div>
          <div class="switch-row">
            <div class="switch-copy"><strong>AI 抽取结果须人工复核</strong><span>线上抽取的债务先进入待复核，不直接参与轧差</span></div>
            <label class="check"><input type="checkbox" name="review_required_for_ai" ${settings.review_required_for_ai ? 'checked' : ''}></label>
          </div>
          <div class="row"><div class="spacer"></div><button class="btn btn-primary" type="submit">保存设置</button></div>
        </form>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><div><h3>线上大模型</h3><p>仅承担要素抽取与文案生成，不参与规则判定与金额分配</p></div>
        <span class="badge ${llm.has_api_key ? 'badge-ok' : 'badge-neutral'}">${llm.has_api_key ? '已配置密钥' : '未配置密钥'}</span></div>
      <div class="card-body">
        <form id="llm-form" class="stack">
          <div class="switch-row">
            <div class="switch-copy"><strong>启用线上模型</strong><span>关闭或未配置时自动使用本地规则抽取</span></div>
            <label class="check"><input type="checkbox" name="llm_enabled" ${llm.enabled ? 'checked' : ''}></label>
          </div>
          <div class="form-grid">
            <div class="field"><label>模型厂商</label><select name="provider">
              ${Object.entries(providers).map(([key, preset]) => `<option value="${key}" ${llm.provider === key ? 'selected' : ''}>${esc(preset.label)}</option>`).join('')}
            </select></div>
            <div class="field"><label>模型名称</label><input name="model" value="${esc(llm.model || '')}" placeholder="deepseek-chat"></div>
            <div class="field span-2"><label>接口地址</label><input name="base_url" value="${esc(llm.base_url || '')}" placeholder="https://api.deepseek.com/v1"></div>
            <div class="field span-2"><label>API Key</label><input name="api_key" type="password" placeholder="${llm.has_api_key ? '已保存，留空不修改' : '仅保存在本机 config/settings.json'}" autocomplete="off"></div>
            <div class="field"><label>温度</label><input name="temperature" type="number" min="0" max="1" step="0.05" value="${llm.temperature ?? 0.1}"></div>
            <div class="field"><label>超时（秒）</label><input name="timeout" type="number" min="5" max="300" step="5" value="${llm.timeout ?? 60}"></div>
          </div>
          <p class="tiny muted">密钥只写入本地配置文件，不进入本体、图谱与审计明细；可用环境变量 DEBT_LLM_API_KEY 覆盖。</p>
          <div class="row">
            <button class="btn" type="submit">保存模型配置</button>
            <button class="btn" type="button" data-action="test-llm">测试连通性</button>
            <div class="spacer"></div>
            <span class="tiny muted">当前：${esc(llm.provider_label || providers[llm.provider]?.label || '自定义')}</span>
          </div>
        </form>
      </div>
    </section>
  </div>

  <section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>本体与 SWRL 规则</h3><p>${esc(ontology.title || '')} · V${esc(ontology.version || '1.0')} · ${ontology.rules || 0} 条规则</p></div>
      <div class="row"><span class="badge badge-neutral">${esc(ontology.path || '')}</span>
      <button class="btn btn-sm" data-action="reload-ontology">重新加载本体</button></div></div>
    <div class="card-body">
      <div class="grid-4" style="margin-bottom:14px">
        <div class="kpi" style="box-shadow:none"><div class="kpi-label">实体类</div><div class="kpi-value" style="font-size:22px">${ontology.classes || 0}</div></div>
        <div class="kpi" style="box-shadow:none"><div class="kpi-label">对象属性</div><div class="kpi-value" style="font-size:22px">${ontology.object_properties || 0}</div></div>
        <div class="kpi" style="box-shadow:none"><div class="kpi-label">数据属性</div><div class="kpi-value" style="font-size:22px">${ontology.datatype_properties || 0}</div></div>
        <div class="kpi" style="box-shadow:none"><div class="kpi-label">SWRL 规则</div><div class="kpi-value" style="font-size:22px">${ontology.rules || 0}</div></div>
      </div>
      <div class="table-wrap" style="border:1px solid #e2e8f0;border-radius:10px">
        <table class="data">
          <thead><tr><th>编号</th><th>规则</th><th>严重度</th><th>SWRL 条件</th><th>法律依据</th></tr></thead>
          <tbody>${rules.map((rule) => `<tr>
            <td><span class="mono">${esc(rule.id)}</span></td>
            <td><strong style="font-size:12px">${esc(rule.name)}</strong></td>
            <td>${severityBadge(rule.severity)}</td>
            <td class="tiny muted">${esc(rule.body)}</td>
            <td class="tiny muted">${esc(rule.legal_basis || '—')}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>
      <p class="tiny muted" style="margin-top:10px">规则维护在 <span class="mono">ontology/debt_ontology.owl</span>，可直接用 Protégé 打开编辑；保存后点击“重新加载本体”即可生效，无需改动求解与前端代码。</p>
    </div>
  </section>

  <section class="card" style="margin-top:18px">
    <div class="card-head"><div><h3>本地数据</h3><p>当前工作记录：${esc(state.activeCase?.name || '—')}；不同工作记录的数据相互独立</p></div></div>
    <div class="card-body">
      <div class="row">
        <button class="btn" data-action="seed-demo-force">重置当前工作记录并载入示例</button>
        <button class="btn btn-danger" data-action="reset-data">清空当前工作记录</button>
        <button class="btn" data-action="stop-server">停止本地服务</button>
        <div class="spacer"></div>
        <span class="tiny muted">导出文件保存在 data/exports/，也可直接从方案页下载。</span>
      </div>
      <div class="notice notice-warn" style="margin-top:14px"><span>!</span><div>只影响当前工作记录，不影响其他工作记录。重置不可撤销，执行前建议先导出债务台账与最近方案。</div></div>
    </div>
  </section>`;
}

function bindSettingsEvents() {
  const form = $('#settings-form');
  if (form) form.addEventListener('submit', saveSettings);
  const llmForm = $('#llm-form');
  if (llmForm) {
    llmForm.addEventListener('submit', saveSettings);
    const provider = llmForm.querySelector('[name=provider]');
    if (provider) provider.addEventListener('change', () => {
      const preset = (state.settings?.providers || {})[provider.value];
      if (preset) {
        llmForm.querySelector('[name=base_url]').value = preset.base_url || '';
        llmForm.querySelector('[name=model]').value = preset.model || '';
      }
    });
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const form = event.target;
  const submit = form.querySelector('[type=submit]');
  setBusy(submit, true);
  try {
    const payload = {};
    if (form.as_of_date) payload.as_of_date = form.as_of_date.value || null;
    if (form.exact_solver_seconds) payload.exact_solver_seconds = Number(form.exact_solver_seconds.value || 3);
    ['include_priority_groups', 'allow_text_upload', 'masking', 'review_required_for_ai'].forEach((name) => {
      if (form[name]) payload[name] = form[name].checked;
    });
    if (form.querySelector('[name=provider]')) {
      const llm = {
        enabled: form.llm_enabled.checked,
        provider: form.provider.value,
        base_url: form.base_url.value,
        model: form.model.value,
        temperature: Number(form.temperature.value || 0.1),
        timeout: Number(form.timeout.value || 60),
      };
      if (form.api_key.value.trim()) llm.api_key = form.api_key.value.trim();
      payload.llm = llm;
    }
    const settings = await api('/api/settings', { method: 'PUT', body: JSON.stringify(payload) });
    state.settings = settings;
    await loadBootstrap();
    toast('设置已保存，新的基准日与求解参数将在下次轧差时生效。');
    await renderView();
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(submit, false);
  }
}

/* ------------------------------------------------------------------ 操作 */
function showNettingOptions() {
  openModal({
    title: '选择计算口径',
    subtitle: '法律合规口径用于实际落地；纯数学口径用于测算理论边界',
    wide: true,
    body: `<div class="netting-options">
      <button class="netting-option" data-action="netting-mode" data-mode="legal">
        <span class="badge badge-ok">推荐落地</span>
        <h3>法律合规口径</h3>
        <p>逐笔执行本体规则：排除争议、查封冻结、未到期、约定禁止抵销与待复核债务；抵押、工资、税款等优先顺位分组独立计算。</p>
        <ul>
          <li>可生成方案报告、Excel 与多方抵销协议草稿</li>
          <li>当前示例台账将纳入合格债务，未入池债务单独列明</li>
        </ul>
        <span class="netting-option-cta">按法律口径计算 →</span>
      </button>
      <button class="netting-option netting-option-pure" data-action="netting-mode" data-mode="pure">
        <span class="badge badge-warn">仅测算</span>
        <h3>纯数学口径</h3>
        <p>暂时不考虑法规限制：全部非人工排除债务合并入池，忽略争议、查封、到期、禁止抵销约定与优先分组，只求最少交易笔数。</p>
        <ul>
          <li>用于测算理论最少笔数、最大抵销空间</li>
          <li>不能生成协议，不能直接作为清偿依据</li>
        </ul>
        <span class="netting-option-cta">按纯数学口径计算 →</span>
      </button>
      <button class="netting-option netting-option-compare" data-action="netting-compare">
        <span class="badge badge-info">推荐分析</span>
        <h3>两种口径对比</h3>
        <p>同时计算法律合规口径与纯数学口径，并列展示交易笔数、支付总额、入池债务差异与额外纳入的债务。</p>
        <ul>
          <li>一次看清“法律允许的方案”和“数学最优的方案”差多少</li>
          <li>两个方案分别保存，可随时切换查看</li>
        </ul>
        <span class="netting-option-cta">生成对比 →</span>
      </button>
    </div>`,
    footer: '<button class="btn" data-close>取消</button>',
  });
}

async function runNetting(button, mode = 'legal') {
  const startedRoute = state.route;
  setBusy(button, true);
  try {
    const plan = await api('/api/netting/run', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
    state.plan = plan;
    state.comparison = null;
    state.comparePlans = null;
    toast(
      `${plan.mode_label || '方案'}已生成：${plan.summary.transaction_count} 笔交易，覆盖 ${plan.summary.included_count} 笔债务。`,
      plan.mode === 'pure' ? 'warn' : 'ok',
    );
    await loadBootstrap();
    if (startedRoute === 'plan') {
      if (currentRoute() === 'plan') await renderView();
    } else if (currentRoute() === startedRoute && currentRoute() !== 'plan') {
      window.location.hash = '#/plan';
    }
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

async function compareNetting(button) {
  const startedRoute = state.route;
  setBusy(button, true);
  try {
    const result = await api('/api/netting/compare', { method: 'POST', body: '{}' });
    state.comparison = result.comparison;
    state.comparePlans = { legal: result.legal, pure: result.pure };
    state.plan = result.legal;
    state.plans = (await api('/api/plans')).items || [];
    await loadBootstrap();
    toast(`对比完成：法律口径 ${result.legal.summary.transaction_count} 笔；纯数学口径 ${result.pure.summary.transaction_count} 笔。`);
    if (startedRoute === 'plan' && currentRoute() === 'plan') {
      await renderView();
    } else {
      window.location.hash = '#/plan';
    }
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

function showPlanMode(mode) {
  const plan = state.comparePlans?.[mode];
  if (!plan) return;
  state.plan = plan;
  VIEW.innerHTML = viewPlan();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function seedDemo(button, force = false) {
  if (force) {
    const yes = await confirmDialog('重置当前工作记录并载入示例', '当前工作记录的主体、债务、材料与方案将被清空，然后载入示例数据。其他工作记录不受影响，但本操作不可撤销。', '重置并载入', true);
    if (!yes) return;
  }
  setBusy(button, true);
  try {
    const result = await api('/api/seed', { method: 'POST', body: JSON.stringify({ force }) });
    toast(result.message || '示例数据已载入。');
    state.extraction = null;
    if (state.route === 'dashboard') {
      await loadBootstrap();
      await renderView();
    } else {
      window.location.hash = '#/dashboard';
    }
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

async function resetData(button) {
  const yes = await confirmDialog('清空当前工作记录', `“${state.activeCase?.name || '当前工作记录'}”的主体、债务、材料、方案与审计记录都将被删除，其他工作记录不受影响，且无法恢复。`, '确认清空', true);
  if (!yes) return;
  setBusy(button, true);
  try {
    await api('/api/reset', { method: 'POST', body: '{}' });
    state.plan = null;
    state.extraction = null;
    state.debts = [];
    state.entities = [];
    await loadBootstrap();
    toast('本地业务数据已清空。');
    await renderView();
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

async function openPlan(planId) {
  try {
    state.comparison = null;
    state.comparePlans = null;
    state.plan = await api(`/api/plans/${planId}`);
    if (state.route === 'plan') {
      VIEW.innerHTML = viewPlan();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      state.pendingPlanId = planId;
      window.location.hash = '#/plan';
    }
  } catch (error) {
    toast(error.message, 'err');
  }
}

async function setDebtStatus(debtId, status, button) {
  setBusy(button, true);
  try {
    await api(`/api/debts/${debtId}/${status}`, { method: 'POST' });
    toast(status === 'confirm' ? '债务已确认，可进入轧差池。' : '债务已排除，不参与轧差。');
    await refreshAfterMutation();
  } catch (error) {
    toast(error.message, 'err');
  } finally {
    setBusy(button, false);
  }
}

/* ------------------------------------------------------------------ 全局事件 */
document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  const id = target.dataset.id;
  try {
    switch (action) {
      case 'add-debt': await showDebtForm(); break;
      case 'new-case': showCaseForm(); break;
      case 'open-case': await openCase(id); break;
      case 'import-debts': showDebtImport(); break;
      case 'load-complex-debts': {
        const textarea = document.querySelector('#debt-import-text');
        if (textarea) textarea.value = COMPLEX_DEBT_CSV;
        break;
      }
      case 'edit-debt': {
        const debt = state.debts.find((item) => item.id === id);
        if (debt) showDebtForm(debt);
        break;
      }
      case 'trace': showTrace(id); break;
      case 'add-entity': showEntityForm(); break;
      case 'edit-entity': {
        const entity = state.entities.find((item) => item.id === id);
        if (entity) showEntityForm(entity);
        break;
      }
      case 'delete-debt': {
        const debt = state.debts.find((item) => item.id === id);
        if (!debt) break;
        const yes = await confirmDialog('删除债务', `确认删除 ${debt.debtor_name} → ${debt.creditor_name} 的债务记录？`, '删除', true);
        if (!yes) break;
        await api(`/api/debts/${id}`, { method: 'DELETE' });
        toast('债务已删除。');
        await refreshAfterMutation();
        break;
      }
      case 'delete-entity': {
        const entity = state.entities.find((item) => item.id === id);
        const yes = await confirmDialog('删除主体', `确认删除「${entity?.name || id}」及其关联债务？`, '删除', true);
        if (!yes) break;
        await api(`/api/entities/${id}?cascade=1`, { method: 'DELETE' });
        toast('主体及关联债务已删除。');
        await refreshAfterMutation();
        break;
      }
      case 'confirm-debt': await setDebtStatus(id, 'confirm', target); break;
      case 'reject-debt': await setDebtStatus(id, 'reject', target); break;
      case 'recheck': {
        setBusy(target, true);
        const result = await api('/api/eligibility/recheck', { method: 'POST', body: '{}' });
        toast(`已重新校验 ${result.total} 笔：可抵销 ${result.eligible} 笔，阻断 ${result.blocked} 笔，待复核 ${result.review} 笔。`);
        await loadDebts();
        await loadBootstrap();
        await renderView();
        setBusy(target, false);
        break;
      }
      case 'run-netting': showNettingOptions(); break;
      case 'netting-mode':
        closeModal();
        await runNetting(target, target.dataset.mode || 'legal');
        break;
      case 'netting-compare':
        closeModal();
        await compareNetting(target);
        break;
      case 'show-plan-mode': showPlanMode(target.dataset.mode || 'legal'); break;
      case 'toggle-plan-detail':
        state.planDetailOpen = !state.planDetailOpen;
        VIEW.innerHTML = viewPlan();
        break;
      case 'seed-demo': await seedDemo(target, false); break;
      case 'seed-demo-force': await seedDemo(target, true); break;
      case 'reset-data': await resetData(target); break;
      case 'load-sample': {
        const textarea = $('#material-text');
        if (textarea) textarea.value = SAMPLE_MATERIAL;
        break;
      }
      case 'clear-file': {
        event.preventDefault();
        state.materialFile = null;
        VIEW.innerHTML = viewMaterials();
        bindMaterialEvents();
        break;
      }
      case 'extract-material': await extractMaterial(target); break;
      case 'import-candidates': await importCandidates(target); break;
      case 'select-all-candidates': {
        const all = (state.extraction?.candidates || []).map((_, index) => index);
        const allSelected = all.every((index) => state.selectedCandidates.has(index));
        state.selectedCandidates = allSelected ? new Set() : new Set(all);
        $$('.cand-check').forEach((input) => { input.checked = !allSelected; });
        updateCandidateSelection();
        break;
      }
      case 'reload-graph': await loadGraph(); await renderView(); break;
      case 'graph-view':
        state.graphView = target.dataset.view === 'matrix' ? 'matrix' : 'graph';
        await renderView();
        break;
      case 'select-graph-node': selectGraphNode(id); break;
      case 'select-cycle': selectGraphCycle(Number(target.dataset.index)); break;
      case 'clear-graph-highlight': clearGraphHighlight(); break;
      case 'graph-zoom-in': changeGraphZoom(1.2); break;
      case 'graph-zoom-out': changeGraphZoom(1 / 1.2); break;
      case 'graph-fit': resetGraphView(); break;
      case 'open-plan':
        closeModal();
        await openPlan(id);
        break;
      case 'show-batch-debts': await showBatchDebts(id); break;
      case 'delete-plan': await deletePlan(id); break;
      case 'generate-narrative': {
        const planId = id || state.plan?.id;
        if (!planId) break;
        setBusy(target, true);
        await api(`/api/plans/${planId}/narrative`, { method: 'POST', body: '{}' });
        state.plan = await api(`/api/plans/${planId}`);
        VIEW.innerHTML = viewPlan();
        toast('AI 解读已生成，随方案一并保存。');
        break;
      }
      case 'reload-ontology': {
        setBusy(target, true);
        const health = await api('/api/ontology/reload', { method: 'POST', body: '{}' });
        toast(`本体已重新加载：${health.rules} 条规则，${health.classes} 个实体类。`);
        await loadBootstrap();
        await renderView();
        break;
      }
      case 'test-llm': {
        setBusy(target, true);
        const result = await api('/api/llm/test', { method: 'POST', body: '{}' });
        toast(result.message || (result.ok ? '连通正常。' : '连通失败。'), result.ok ? 'ok' : 'err');
        setBusy(target, false);
        break;
      }
      case 'stop-server': {
        const yes = await confirmDialog(
          '停止本地服务',
          '停止后本页面将无法继续访问，已保存的数据不会丢失。下次使用时双击桌面快捷方式即可重新启动。',
          '停止服务',
          true,
        );
        if (!yes) break;
        try {
          await api('/api/shutdown', { method: 'POST', body: '{}' });
        } catch (error) {
          // 服务停止时连接被关闭属于正常现象
        }
        closeModal();
        VIEW.innerHTML = `<div class="card">${emptyState('■', '本地服务已停止',
          '数据库、本体与导出文件都已保留。双击桌面上的“三角债智能轧差系统”即可重新启动。')}</div>`;
        TOPBAR.innerHTML = '';
        break;
      }
      case 'rerender': await renderView(); break;
      default: break;
    }
  } catch (error) {
    toast(error.message, 'err');
    setBusy(target, false);
  }
});

document.addEventListener('change', (event) => {
  const target = event.target;
  if (target.classList && target.classList.contains('cand-check')) {
    const index = Number(target.dataset.index);
    if (target.checked) state.selectedCandidates.add(index);
    else state.selectedCandidates.delete(index);
    updateCandidateSelection();
  }
  if (target.id === 'graph-ineligible') {
    state.graphIneligible = target.checked;
    renderView().catch((error) => toast(error.message, 'err'));
  }
  if (target.id === 'graph-group') {
    state.graphGroup = target.value || 'all';
    state.selectedNode = null;
    state.graphActiveCycle = null;
    state.graphTransform = { x: 0, y: 0, k: 1 };
    drawGraph();
    const side = $('#graph-side');
    if (side) side.innerHTML = graphSideHtml();
  }
  if (target.id === 'graph-amounts') {
    state.graphShowAmounts = target.checked;
    drawGraph();
  }
});

/* ------------------------------------------------------------------ 启动 */
window.addEventListener('hashchange', renderView);

(async function init() {
  try {
    await loadBootstrap();
    await renderView();
  } catch (error) {
    VIEW.innerHTML = `<div class="card">${emptyState('!', '系统未启动或接口不可用', error.message)}</div>`;
  }
})();
