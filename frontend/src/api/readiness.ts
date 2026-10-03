/** 就绪探测：页面挂载前先确认后端"端口、依赖、代理"三项全通。
 *
 * 探测走和业务接口相同的入口（默认相对路径，经 vite 代理到后端），
 * 所以这里探到的结论和页面跑起来之后看到的一致。
 */

export type CheckStatus = 'ok' | 'failed' | 'pending'

export interface ReadyCheck {
  status: CheckStatus
  detail: string
}

export interface ReadyReport {
  ready: boolean
  /** 没就绪时，后端下次会从这一项接着探（已通过的项不会重跑） */
  retryFrom: string | null
  checks: Record<string, ReadyCheck>
  /** 传输层错误（后端没起来、地址不对等），此时 checks 全是 pending */
  transportError?: string
}

const CHECK_NAMES = ['port', 'deps', 'proxy'] as const

export const CHECK_LABELS: Record<string, string> = {
  port: '端口监听',
  deps: '依赖安装',
  proxy: '前端代理',
}

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const READY_URL = `${API_BASE}/api/ready`

export async function probeReadiness(): Promise<ReadyReport> {
  let response: Response
  try {
    response = await fetch(READY_URL, { headers: { Accept: 'application/json' } })
  } catch (error) {
    const detail = error instanceof Error ? error.message : '请求未送达'
    return unreachable(`就绪地址不可达：${detail}`)
  }
  if (response.status === 404) {
    return unreachable('后端没有就绪地址 /api/ready，后端版本可能太旧')
  }
  try {
    const payload = await response.json()
    return {
      ready: Boolean(payload.ready),
      retryFrom: payload.retry_from ?? null,
      checks: payload.checks ?? {},
    }
  } catch {
    return unreachable(`就绪地址返回的不是 JSON（HTTP ${response.status}），代理可能指错了`)
  }
}

function unreachable(detail: string): ReadyReport {
  const checks: Record<string, ReadyCheck> = {}
  for (const name of CHECK_NAMES) {
    checks[name] = { status: 'pending', detail: '待探测' }
  }
  return { ready: false, retryFrom: null, checks, transportError: detail }
}

/** 轮询直到就绪；每次探测结果都回调一次，用来刷新启动页。 */
export function waitUntilReady(
  onUpdate: (report: ReadyReport) => void,
  intervalMs = 1500,
): Promise<ReadyReport> {
  return new Promise((resolve) => {
    const tick = async () => {
      const report = await probeReadiness()
      onUpdate(report)
      if (report.ready) {
        resolve(report)
        return
      }
      setTimeout(tick, intervalMs)
    }
    void tick()
  })
}
