/**
 * Faces page: enroll household members so alerts greet them by name.
 *
 * Upload a clear front-facing photo with a name — the hub computes an SFace
 * embedding via POST /api/faces and matches future detections against it.
 * Lists enrolled faces with creation dates and per-person remove buttons.
 * Enrollment errors (no face found, bad image) surface inline.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, FaceItem } from '../api'

export default function Faces() {
  const [faces, setFaces] = useState<FaceItem[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => api.faces().then(setFaces).catch(() => {}), [])
  useEffect(() => { load() }, [load])

  const enroll = async () => {
    const file = fileRef.current?.files?.[0]
    if (!name.trim() || !file) {
      setMsg('Pick a name and a clear photo of the face.')
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const r = await api.enrollFace(name.trim(), file)
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? `HTTP ${r.status}`)
      }
      setMsg(`Enrolled ${name.trim()} ✔`)
      setName('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (e: any) {
      setMsg(e.message ?? 'Enrollment failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h2 className="mb-5 text-xl font-bold text-white">Faces</h2>

      <div className="card mb-6 p-5">
        <h3 className="mb-1 font-semibold text-white">Enroll a person</h3>
        <p className="mb-4 text-sm text-slate-400">
          Upload a clear, front-facing photo. The hub computes a face embedding and will
          greet this person by name in alerts and the live view.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input className="input max-w-xs" placeholder="Name (e.g. Alice)" value={name}
                 onChange={e => setName(e.target.value)} />
          <input ref={fileRef} type="file" accept="image/*" className="input max-w-xs py-1.5" />
          <button className="btn-primary" onClick={enroll} disabled={busy}>
            {busy ? 'Working…' : 'Enroll'}
          </button>
        </div>
        {msg && <p className="mt-3 text-sm text-slate-300">{msg}</p>}
      </div>

      <div className="card divide-y divide-ink-700">
        {faces.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">No faces enrolled yet.</p>
        ) : (
          faces.map(f => (
            <div key={f.id} className="flex items-center gap-4 p-4">
              <div className="grid h-10 w-10 place-items-center rounded-full bg-accent-500/15 text-accent-400">
                {(f.name[0] ?? '?').toUpperCase()}
              </div>
              <div className="flex-1">
                <p className="font-semibold text-white">{f.name}</p>
                <p className="text-xs text-slate-500">added {new Date(f.created_at * 1000).toLocaleDateString()}</p>
              </div>
              <button
                className="btn-ghost text-red-400 hover:text-red-300"
                onClick={async () => { if (confirm(`Remove ${f.name}?`)) { await api.deleteFace(f.name); load() } }}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
