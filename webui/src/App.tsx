/**
 * Root dashboard shell: tab navigation, live status polling, and alerts.
 *
 * Polls GET /api/status every 2 s for the camera-online badge, holds a
 * persistent /api/ws WebSocket (auto-reconnect) that surfaces person/face/
 * doorbell detections as toast popups, and switches between the Live,
 * Events, Faces and Settings pages. The header also links the installable
 * Android APK served from /downloads/app-release.apk.
 */
import { useEffect, useRef, useState } from 'react'
import { api, HubStatus, EventItem } from './api'
import Dashboard from './pages/Dashboard'
import Events from './pages/Events'
import Faces from './pages/Faces'
import Settings from './pages/Settings'

type Tab = 'dashboard' | 'events' | 'faces' | 'settings'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Live', icon: '📷' },
  { id: 'events', label: 'Events', icon: '🔔' },
  { id: 'faces', label: 'Faces', icon: '🙂' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [status, setStatus] = useState<HubStatus | null>(null)
  const [wsOnline, setWsOnline] = useState(false)
  const [toast, setToast] = useState<EventItem | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Poll status
  useEffect(() => {
    let alive = true
    const tick = () =>
      api.status().then(s => alive && setStatus(s)).catch(() => alive && setStatus(null))
    tick()
    const t = setInterval(tick, 2000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  // WebSocket: live events + toast
  useEffect(() => {
    let closed = false
    let ws: WebSocket | null = null
    const connect = () => {
      ws = new WebSocket(api.wsUrl)
      wsRef.current = ws
      ws.onopen = () => setWsOnline(true)
      ws.onclose = () => {
        setWsOnline(false)
        if (!closed) setTimeout(connect, 2000)
      }
      ws.onmessage = ev => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.kind && msg.ts) {
            setToast(msg)
            setTimeout(() => setToast(null), 6000)
          }
        } catch { /* ignore */ }
      }
    }
    connect()
    return () => { closed = true; ws?.close() }
  }, [])

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-ink-700 bg-ink-900/90 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-accent-500 to-indigo-600 text-lg shadow-lg shadow-accent-500/20">
            🔔
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">DoorbellCam</h1>
            <p className="text-xs text-slate-400">Self-hosted smart doorbell</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs">
          <span
            className={`chip ${status?.camera_online ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${status?.camera_online ? 'bg-emerald-400' : 'bg-red-400'}`} />
            {status?.camera_online ? `Camera ${status.camera_ip ?? ''}` : 'Camera offline'}
          </span>
          <span className={`chip ${wsOnline ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${wsOnline ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            {wsOnline ? 'Live' : 'Reconnecting…'}
          </span>
          <a
            href="/downloads/app-release.apk"
            download
            title="Install the DoorbellCam Android app on your phone"
            className="chip bg-accent-500/15 text-accent-400 hover:bg-accent-500/25"
          >
            📱 Get the app
          </a>
        </div>
      </header>

      {/* Body */}
      <main className="flex-1 overflow-y-auto px-6 py-5">
        {tab === 'dashboard' && <Dashboard status={status} />}
        {tab === 'events' && <Events onOpenFaces={() => setTab('faces')} />}
        {tab === 'faces' && <Faces />}
        {tab === 'settings' && <Settings status={status} />}
      </main>

      {/* Nav */}
      <nav className="flex items-center justify-center gap-1 border-t border-ink-700 bg-ink-900/90 px-4 py-2">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${
              tab === t.id ? 'bg-accent-500/15 text-accent-400' : 'text-slate-400 hover:bg-ink-800 hover:text-white'
            }`}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-20 right-6 z-50 w-80 animate-[slidein_.3s_ease] rounded-2xl border border-accent-500/30 bg-ink-850/95 p-4 shadow-2xl shadow-black/50 backdrop-blur">
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-500/15 text-lg">🚨</div>
            <div className="min-w-0">
              <p className="font-semibold text-white">
                {toast.kind === 'face' ? 'Known face detected' : toast.kind === 'doorbell' ? 'Doorbell pressed' : 'Person detected'}
              </p>
              <p className="truncate text-xs text-slate-400">
                {toast.label || 'Unrecognized'} · {new Date(toast.ts * 1000).toLocaleTimeString()}
              </p>
            </div>
            {toast.id && (
              <img
                src={api.eventSnapshotUrl(toast.id)}
                alt="snapshot"
                className="h-14 w-14 shrink-0 rounded-lg border border-ink-600 object-cover"
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
