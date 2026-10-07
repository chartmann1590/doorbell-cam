/**
 * Live page: MJPEG stream, recognition list, and recent-event side panel.
 *
 * Shows the camera feed via <MjpegStream /> with an offline overlay + manual
 * retry, the current motion % / person count from /api/status, named faces
 * in view, and the 8 latest events (auto-refreshed every 5 s and whenever a
 * new detection lands). A red badge overlays the video while a person is
 * in frame.
 */
import { useEffect, useState } from 'react'
import { api, HubStatus, EventItem } from '../api'
import MjpegStream from '../components/MjpegStream'

export default function Dashboard({ status }: { status: HubStatus | null }) {
  const [recent, setRecent] = useState<EventItem[]>([])
  const [manualRetry, setManualRetry] = useState(0)

  useEffect(() => {
    api.events(8).then(setRecent).catch(() => {})
    const t = setInterval(() => api.events(8).then(setRecent).catch(() => {}), 5000)
    return () => clearInterval(t)
  }, [status?.last_event?.id])

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      {/* Live view */}
      <section className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-ink-700 px-5 py-3">
          <h2 className="font-semibold text-white">Live view</h2>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            {status && (
              <>
                <span>Motion {status.motion_level?.toFixed(1)}%</span>
                <span>·</span>
                <span>{status.person_count} person{status.person_count === 1 ? '' : 's'}</span>
              </>
            )}
          </div>
        </div>
        <div className="relative aspect-[4/3] bg-black">
          <MjpegStream
            url={api.liveStreamUrl}
            online={Boolean(status?.camera_online)}
            key={`s${status?.camera_online}-${manualRetry}`}
          />
          {!status?.camera_online && (
            <div className="absolute inset-0 grid place-items-center bg-black/70 text-center">
              <div>
                <div className="text-5xl">📷</div>
                <p className="mt-3 text-sm text-slate-300">Waiting for the camera stream…</p>
                <p className="text-xs text-slate-500">
                  The hub reconnects automatically. Check power + WiFi on the ESP32-CAM.
                </p>
                <button
                  className="btn-ghost mt-4"
                  onClick={() => setManualRetry(n => n + 1)}
                >
                  Retry now
                </button>
              </div>
            </div>
          )}
          {status?.person_count ? (
            <span className="absolute left-4 top-4 chip bg-red-500/80 text-white shadow-lg">
              ● Person detected
            </span>
          ) : null}
        </div>
      </section>

      {/* Side column */}
      <aside className="flex flex-col gap-5">
        <section className="card p-5">
          <h3 className="mb-3 font-semibold text-white">Recognition</h3>
          {status?.faces?.length ? (
            <ul className="space-y-2">
              {status.faces.map((f, i) => (
                <li key={i} className="flex items-center justify-between rounded-xl bg-ink-800 px-3 py-2 text-sm">
                  <span>{f.name ?? 'Unknown face'}</span>
                  <span className="chip bg-accent-500/10 text-accent-400">
                    {(f as any).similarity ? `${Math.round((f as any).similarity * 100)}%` : 'face'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">
              No faces in view. Enroll people in the Faces tab to get named alerts.
            </p>
          )}
        </section>

        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-white">Recent events</h3>
            <button className="text-xs font-semibold text-accent-400 hover:underline" onClick={() => api.events(8).then(setRecent).catch(() => {})}>
              refresh
            </button>
          </div>
          {recent.length === 0 ? (
            <p className="text-sm text-slate-500">Nothing yet — walk in front of the camera.</p>
          ) : (
            <ul className="space-y-2">
              {recent.map(ev => (
                <li key={ev.id} className="flex items-center gap-3 rounded-xl bg-ink-800 p-2">
                  {ev.snapshot ? (
                    <img src={api.eventSnapshotUrl(ev.id)} className="h-11 w-11 rounded-lg object-cover" alt="" />
                  ) : (
                    <div className="grid h-11 w-11 place-items-center rounded-lg bg-ink-700">🔔</div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">
                      {ev.label || (ev.kind === 'person' ? 'Person' : ev.kind)}
                    </p>
                    <p className="text-xs text-slate-500">{new Date(ev.ts * 1000).toLocaleString()}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  )
}
