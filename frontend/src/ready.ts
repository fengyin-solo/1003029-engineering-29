/**
 * 后端就绪门：探到 /api/ready 通过才放行挂载，没通过就把缺的项摆出来等重试。
 *
 * 后端会缓存已通过的检查项（断点续探），这里每次重试只会从未通过的那项接着探，
 * 重复探测不会重复拉起依赖。等待页用纯 DOM 渲染，不经过 Vue——Vue 应用要等就绪后才挂载。
 */

export interface ReadyCheck {
  name: string
  ok: boolean | null
  detail: string
  cached: boolean
}

export interface ReadyReport {
  ready: boolean
  checks: ReadyCheck[]
  failed: string[]
  hint: string
}

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const APP_NAME = import.meta.env.VITE_APP_NAME ?? '后端服务'
const RETRY_INTERVAL_MS = 2000

const CHECK_LABELS: Record<string, string> = {
  port: '后端端口',
  deps: '后端依赖',
  proxy: '前端代理',
}

function escapeHtml(text: string): string {
  const entities: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }
  return text.replace(/[&<>"']/g, (ch) => entities[ch] ?? ch)
}

function renderCheck(item: ReadyCheck): string {
  const state = item.ok === null ? 'pending' : item.ok ? 'pass' : 'fail'
  const icon = item.ok === null ? '…' : item.ok ? '✓' : '✗'
  const label = CHECK_LABELS[item.name] ?? item.name
  return (
    `<li class="ready-item ${state}">` +
    `<span class="ready-icon">${icon}</span>` +
    `<span class="ready-name">${escapeHtml(label)}</span>` +
    `<span class="ready-detail">${escapeHtml(item.detail)}</span>` +
    `</li>`
  )
}

function renderWaiting(container: HTMLElement, report: ReadyReport | null, error?: unknown): void {
  const rows = report
    ? report.checks.map(renderCheck).join('')
    : renderCheck({
        name: 'ready',
        ok: false,
        detail: `就绪地址探测未送达：${error instanceof Error ? error.message : '未知错误'}（后端没起？）`,
        cached: false,
      })
  const hint = report ? report.hint : '确认后端已启动，页面会自动重试，无需手动刷新'
  container.innerHTML =
    `<div class="ready-gate">` +
    `<h1 class="ready-title">${escapeHtml(APP_NAME)} · 等待后端就绪</h1>` +
    `<ul class="ready-list">${rows}</ul>` +
    `<p class="ready-hint">${escapeHtml(hint)}</p>` +
    `<p class="ready-retry">${RETRY_INTERVAL_MS / 1000} 秒后自动重试（已通过的项不会重复探测）</p>` +
    `</div>`
}

async function probe(): Promise<ReadyReport> {
  // 未就绪时后端回 503，body 里同样带逐项明细，照常解析
  const response = await fetch(`${API_BASE}/api/ready`, {
    headers: { Accept: 'application/json' },
  })
  return (await response.json()) as ReadyReport
}

/** 轮询就绪地址，就绪后才返回；没就绪时把逐项状态画到挂载点上。 */
export async function waitForBackend(container: HTMLElement): Promise<void> {
  for (;;) {
    try {
      const report = await probe()
      if (report.ready) {
        return
      }
      renderWaiting(container, report)
    } catch (error) {
      renderWaiting(container, null, error)
    }
    await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL_MS))
  }
}
