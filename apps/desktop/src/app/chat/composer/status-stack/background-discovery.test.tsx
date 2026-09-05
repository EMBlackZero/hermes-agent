import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { $backgroundStatusBySession, resetBackgroundPollingGuard } from '@/store/composer-status'
import { $gateway } from '@/store/gateway'

import { ComposerStatusStack } from './index'

// The stack measures itself into a surface var — jsdom has no ResizeObserver.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverStub)

const SID = 'sess-discovery'

// Long enough to cross the idle discovery cadence whatever it is tuned to,
// short enough that the fake clock stays cheap.
const PAST_ONE_DISCOVERY_TICK_MS = 30_000

function renderStack() {
  return render(
    <MemoryRouter>
      <ComposerStatusStack queue={null} sessionId={SID} />
    </MemoryRouter>
  )
}

// A background process spawned through ANOTHER gateway client (a Telegram
// terminal(background=true) job) reaches this Desktop only through the shared
// registry — no gateway event is broadcast to us. If the mounted session had no
// background row at mount time, nothing ever asked the registry again, so the
// row never appeared until the user remounted the tile.
describe('ComposerStatusStack externally-created background discovery', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetBackgroundPollingGuard()
    $backgroundStatusBySession.set({})
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    $gateway.set(null as never)
    $backgroundStatusBySession.set({})
    resetBackgroundPollingGuard()
  })

  it('discovers a process that appears on a later poll, with no remount and no gateway event', async () => {
    let processes: Record<string, unknown>[] = []

    const request = vi.fn(async (method: string) => (method === 'process.list' ? { processes } : {}))

    $gateway.set({ request } as never)

    renderStack()

    // Mount seed: the registry is still empty, exactly like the reported bug
    // (the Desktop tile opened minutes before the Telegram job started).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(screen.queryByText('1 Background')).toBeNull()

    // The job starts elsewhere. Nothing notifies this window.
    processes = [{ command: 'sleep 600', session_id: 'proc_e99debacd2eb', status: 'running' }]

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PAST_ONE_DISCOVERY_TICK_MS)
    })

    expect(screen.getByText('1 Background')).toBeTruthy()
  })

  it('stops polling after unmount so no timer leaks', async () => {
    const request = vi.fn(async (method: string) => (method === 'process.list' ? { processes: [] } : {}))

    $gateway.set({ request } as never)

    const view = renderStack()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PAST_ONE_DISCOVERY_TICK_MS)
    })

    const callsWhileMounted = request.mock.calls.filter(([method]) => method === 'process.list').length

    expect(callsWhileMounted).toBeGreaterThan(1)

    view.unmount()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PAST_ONE_DISCOVERY_TICK_MS * 2)
    })

    expect(request.mock.calls.filter(([method]) => method === 'process.list').length).toBe(callsWhileMounted)
  })

  it('arms exactly one discovery timer per session and drops it on session switch', async () => {
    const request = vi.fn(async (method: string, _params?: { session_id?: string }) =>
      method === 'process.list' ? { processes: [] } : {}
    )

    const listCallsFor = (sid: string) =>
      request.mock.calls.filter(([method, params]) => method === 'process.list' && params?.session_id === sid).length

    $gateway.set({ request } as never)

    const view = render(
      <MemoryRouter>
        <ComposerStatusStack queue={null} sessionId={SID} />
      </MemoryRouter>
    )

    // A parent re-render with the SAME session must not stack a second timer.
    view.rerender(
      <MemoryRouter>
        <ComposerStatusStack queue={null} sessionId={SID} />
      </MemoryRouter>
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PAST_ONE_DISCOVERY_TICK_MS)
    })

    const firstSessionCalls = listCallsFor(SID)

    view.rerender(
      <MemoryRouter>
        <ComposerStatusStack queue={null} sessionId="sess-other" />
      </MemoryRouter>
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PAST_ONE_DISCOVERY_TICK_MS)
    })

    // The old session's timer is gone: its call count is frozen.
    expect(listCallsFor(SID)).toBe(firstSessionCalls)
  })
})
