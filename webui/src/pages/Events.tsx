/**
 * Events page: filterable history grid with snapshot zoom + delete.
 *
 * Loads up to 200 events, filters by kind (all/face/person/motion/doorbell),
 * renders snapshot thumbnails in a responsive grid, opens a full-size modal
 * on click (with per-event delete), and offers a guarded "Clear all".
 * Auto-refreshes every 4 s so new detections appear without reload.
 */
import { useCallback, useEffect, useState } from 'react'
import { api, EventItem } from '../api'

const KINDS = ['all', 'face', 'person', 'motion', 'doorbell'] as const

export default function Events({ onOpenFaces }: { onOpenFaces: () => void }) {
  const [events, setEvents] = useState<EventItem[]>([])
  const [kind, setKind] = useState<(typeof KINDS)[number]>('all')
  const [zoom, setZoom] = useState<EventItem | null>(null)

  const load = useCallback(() => {
    api.events(200).then(setEvents).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [load])

  const shown = events.filter(e => kind === 'all' || e.kind === kind)

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-bold text-white">Event history</h2>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {KINDS.map(k => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={`chip ${kind === k ? 'bg-accent-500 text-white' : 'bg-ink-800 text-slate-400 hover:text-white'}`}
            >
              {k}
            </button>
          ))}
          <button className="btn-ghost" onClick={onOpenFaces}>Manage faces</button>
          <button
            className="btn-danger"
            onClick={async () => { if (confirm('Delete ALL events?')) { await api.clearEvents(); load() } }}
          >
            Clear all
          </button>
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="card grid place-items-center p-16 text-center">
          <div className="text-5xl">🗂️</div>
          <p className="mt-4 text-slate-400">No events recorded yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {shown.map(ev => (
            <button
              key={ev.id}
              onClick={() => setZoom(ev)}
              className="card group overflow-hidden text-left transition-transform hover:-translate-y-0.5"
            >
              <div className="relative aspect-[4/3] bg-ink-800">
                {ev.snapshot ? (
                  <img
                    src={api.eventSnapshotUrl(ev.id)}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                    alt=""
                  />
                ) : (
                  <div className="grid h-full place-items-center text-3xl">🔔</div>
                )}
                <span
                  className={`absolute left-2 top-2 chip ${
                    ev.kind === 'face' ? 'bg-emerald-500/90 text-white'
                    : ev.kind === 'person' ? 'bg-amber-500/90 text-black'
                    : 'bg-ink-700 text-slate-300'
                  }`}
                >
                  {ev.kind}
                </span>
              </div>
              <div className="p-3">
                <p className="truncate text-sm font-semibold text-white">{ev.label || ev.kind}</p>
                <p className="text-xs text-slate-500">
                  {new Date(ev.ts * 1000).toLocaleString()} · {Math.round(ev.confidence * 100)}%
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Zoom modal */}
      {zoom && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-6" onClick={() => setZoom(null)}>
          <div className="card max-w-3xl overflow-hidden" onClick={e => e.stopPropagation()}>
            <img src={api.eventSnapshotUrl(zoom.id)} className="max-h-[70vh] w-full object-contain" alt="" />
            <div className="flex items-center justify-between p-4">
              <div>
                <p className="font-semibold text-white">{zoom.label || zoom.kind}</p>
                <p className="text-xs text-slate-500">{new Date(zoom.ts * 1000).toLocaleString()}</p>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn-danger"
                  onClick={async () => { await api.deleteEvent(zoom.id); setZoom(null); load() }}
                >
                  Delete
                </button>
                <button className="btn-ghost" onClick={() => setZoom(null)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
