/** 启动页：后端就绪之前不挂载应用，只把探测进度画进挂载容器。 */
import type { CheckStatus, ReadyReport } from './api/readiness'
import { CHECK_LABELS } from './api/readiness'

const STATUS_ICON: Record<CheckStatus, string> = {
  ok: '✓',
  failed: '✗',
  pending: '…',
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function renderBootStatus(container: HTMLElement, report: ReadyReport): void {
  const rows = Object.entries(report.checks)
    .map(([name, check]) => {
      const label = CHECK_LABELS[name] ?? name
      return `<li class="boot-item boot-${check.status}">
        <span class="boot-icon">${STATUS_ICON[check.status]}</span>
        <span class="boot-label">${escapeHtml(label)}</span>
        <span class="boot-detail">${escapeHtml(check.detail)}</span>
      </li>`
    })
    .join('')
  const error = report.transportError
    ? `<p class="boot-error">${escapeHtml(report.transportError)}</p>`
    : ''
  container.innerHTML = `
    <div class="boot-screen">
      <h1 class="boot-title">通信基站运维管理平台</h1>
      <p class="boot-tip">正在等待后端就绪：探测会自动重试，已通过的项不会重复探测。</p>
      ${error}
      <ul class="boot-list">${rows}</ul>
    </div>`
}
