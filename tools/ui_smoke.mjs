/**
 * 浏览器端冒烟测试：通过 Chrome DevTools Protocol 操作真实页面，
 * 覆盖新增债务、规则推理弹窗、材料抽取导入与方案重算。
 *
 * 用法：
 *   1. 启动 Chrome：chrome.exe --headless=new --remote-debugging-port=9223 about:blank
 *   2. node tools/ui_smoke.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
function resolveBase() {
  if (process.env.DEBT_BASE_URL) return process.env.DEBT_BASE_URL.replace(/\/$/, '');
  try {
    const url = readFileSync(resolve(HERE, '..', 'data', 'runtime.url'), 'utf8').trim();
    if (url.startsWith('http://')) return url;
  } catch (error) {
    // 未启动时回退默认端口
  }
  return 'http://127.0.0.1:8765';
}
const BASE = resolveBase();
const DEBUG_PORT = Number(process.env.CHROME_DEBUG_PORT || 9223);
const APP = `${BASE}/#/dashboard`;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function getPageTarget() {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)).json();
      const page = targets.find((target) => target.type === 'page');
      if (page) return page;
    } catch (error) {
      // Chrome 尚未就绪
    }
    await sleep(300);
  }
  throw new Error('无法连接 Chrome 调试端口');
}

function createClient(wsUrl) {
  const socket = new WebSocket(wsUrl);
  const pending = new Map();
  const events = [];
  let nextId = 0;
  let opened = false;

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      events.push({ type: 'exception', detail: message.params.exceptionDetails?.text });
    } else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') {
      events.push({ type: 'console', detail: message.params.args.map((arg) => arg.value || arg.description).join(' ') });
    }
  });

  const ready = new Promise((resolve, reject) => {
    socket.addEventListener('open', () => { opened = true; resolve(); });
    socket.addEventListener('error', () => reject(new Error('WebSocket 连接失败')));
  });

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      if (!opened) { reject(new Error('WebSocket 尚未连接')); return; }
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text + (result.exceptionDetails.exception?.description || ''));
    }
    return result.result?.value;
  }

  async function waitFor(expression, timeout = 12000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      try {
        if (await evaluate(expression)) return true;
      } catch (error) {
        // 页面重载过程中忽略
      }
      await sleep(200);
    }
    throw new Error(`等待超时：${expression}`);
  }

  return { socket, send, evaluate, waitFor, events, ready };
}

async function run() {
  const target = await getPageTarget();
  const client = createClient(target.webSocketDebuggerUrl);
  await client.ready;
  await client.send('Runtime.enable');
  await client.send('Page.enable');
  await client.send('Page.navigate', { url: APP });
  await client.waitFor(`document.querySelector('#view .hero') && document.body.innerText.includes('工作台')`);

  // 1. 新增债务
  await client.evaluate(`location.hash = '#/debts'`);
  await client.waitFor(`document.querySelector('[data-action="edit-debt"]') && document.querySelector('#debt-table-card')`);
  const before = await client.evaluate(`document.querySelectorAll('[data-action="edit-debt"]').length`);
  await client.evaluate(`document.querySelector('[data-action="add-debt"]').click()`);
  await client.waitFor(`document.querySelector('#debt-form')`);
  await client.evaluate(`(() => {
    const form = document.querySelector('#debt-form');
    const options = form.querySelectorAll('select[name="debtor_id"] option');
    form.querySelector('select[name="debtor_id"]').value = options[1].value;
    const creditors = form.querySelectorAll('select[name="creditor_id"] option');
    form.querySelector('select[name="creditor_id"]').value = creditors[2].value;
    form.querySelector('input[name="principal"]').value = '12345';
    form.querySelector('input[name="interest"]').value = '55';
    form.querySelector('input[name="due_date"]').value = '2020-01-01';
    form.querySelector('input[name="note"]').value = 'UI冒烟测试';
    form.requestSubmit();
    return true;
  })()`);
  await client.waitFor(`!document.querySelector('#modal-overlay')`);
  await client.waitFor(`document.querySelectorAll('[data-action="edit-debt"]').length >= ${before + 1}`, 15000);
  const after = await client.evaluate(`document.querySelectorAll('[data-action="edit-debt"]').length`);
  if (after !== before + 1) throw new Error(`新增债务前端行数异常：${before} -> ${after}`);
  console.log('✓ 新增债务：表单提交、规则推理、列表刷新正常');

  // 清理新增债务
  const created = await (await fetch(`${BASE}/api/debts?q=UI%E5%86%92%E7%83%9F%E6%B5%8B%E8%AF%95`)).json();
  for (const item of created.items) {
    await fetch(`${BASE}/api/debts/${item.id}`, { method: 'DELETE' });
  }

  // 2. 规则推理弹窗
  await client.evaluate(`location.hash = '#/debts'`);
  await client.waitFor(`document.querySelector('[data-action="trace"]')`);
  await client.evaluate(`document.querySelector('[data-action="trace"]').click()`);
  await client.waitFor(`document.querySelector('#modal-overlay') && document.body.innerText.includes('SWRL 规则命中明细')`);
  const traceText = await client.evaluate(`document.querySelector('#modal-overlay').innerText`);
  if (!traceText.includes('派生属性') || !traceText.includes('法律依据') && !traceText.includes('《民法典》')) {
    throw new Error('推理弹窗内容不完整');
  }
  await client.evaluate(`document.querySelector('#modal-overlay .modal-close').click()`);
  await client.waitFor(`!document.querySelector('#modal-overlay')`);
  console.log('✓ 规则推理弹窗：命中明细与法条可追溯');

  // 3. 材料抽取与导入
  await client.evaluate(`location.hash = '#/materials'`);
  await client.waitFor(`document.querySelector('[data-action="load-sample"]')`);
  await client.evaluate(`document.querySelector('[data-action="load-sample"]').click()`);
  await client.waitFor(`document.querySelector('#material-text').value.includes('恒通建材')`);
  await client.evaluate(`document.querySelector('[data-action="extract-material"]').click()`);
  await client.waitFor(`document.querySelectorAll('.candidate').length >= 2`, 15000);
  const candidates = await client.evaluate(`document.querySelectorAll('.candidate').length`);
  await client.evaluate(`document.querySelector('[data-action="import-candidates"]').click()`);
  await client.waitFor(`location.hash.includes('/debts')`, 15000);
  await client.waitFor(`document.querySelector('#debt-table-card')`, 15000);
  console.log(`✓ 材料抽取：本地规则抽取 ${candidates} 条并成功导入`);

  // 清理导入的债务（只删除材料导入产生的记录，避免误删示例台账）
  for (const keyword of ['补充材料款', '金额存在争议']) {
    const result = await (await fetch(`${BASE}/api/debts?q=${encodeURIComponent(keyword)}`)).json();
    for (const item of result.items.filter((debt) => debt.source !== 'manual' && debt.note.includes(keyword))) {
      await fetch(`${BASE}/api/debts/${item.id}`, { method: 'DELETE' });
    }
  }

  // 4. 方案重算
  await client.evaluate(`location.hash = '#/plan'`);
  await client.waitFor(`document.querySelector('[data-action="run-netting"]')`, 15000);
  await client.evaluate(`document.querySelector('[data-action="run-netting"]').click()`);
  await client.waitFor(`document.querySelector('.netting-options')`, 10000);
  await client.evaluate(`document.querySelector('[data-action="netting-mode"][data-mode="legal"]').click()`);
  await client.waitFor(`document.body.innerText.includes('笔交易，覆盖')`, 20000);
  const planText = await client.evaluate(`document.querySelector('#view').innerText`);
  for (const keyword of ['最简清偿清单', '方案校验', '未入池债务', '法律边界']) {
    if (!planText.includes(keyword)) throw new Error(`方案页缺少：${keyword}`);
  }
  console.log('✓ 轧差方案：重算、分组清单、校验与未入池清单渲染正常');

  // 5. 设置页读取与保存
  await client.evaluate(`location.hash = '#/settings'`);
  await client.waitFor(`document.querySelector('#settings-form')`, 15000);
  const settingsText = await client.evaluate(`document.querySelector('#view').innerText`);
  if (!settingsText.includes('本体与 SWRL 规则') || !settingsText.includes('R1')) {
    throw new Error('设置页本体规则未渲染');
  }
  await client.evaluate(`document.querySelector('[name="masking"]').click()`);
  await client.evaluate(`document.querySelector('#settings-form').requestSubmit()`);
  await client.waitFor(`document.body.innerText.includes('设置已保存')`, 15000);
  await client.waitFor(`document.querySelector('#settings-form')`, 15000);
  await client.evaluate(`document.querySelector('#settings-form') && document.querySelector('[name="masking"]').click()`);
  await client.evaluate(`document.querySelector('#settings-form').requestSubmit()`);
  await client.waitFor(`document.body.innerText.includes('设置已保存')`, 15000);
  console.log('✓ 系统设置：参数、模型、本体规则渲染与保存正常');

  const errors = client.events.filter((event) => event.type === 'exception');
  if (errors.length) {
    console.error('浏览器异常：', errors);
    throw new Error(`浏览器运行期间出现 ${errors.length} 个异常`);
  }
  client.socket.close();
  console.log('UI 冒烟测试全部通过');
}

run().catch((error) => {
  console.error('UI 冒烟测试失败：', error.message);
  process.exit(1);
});
