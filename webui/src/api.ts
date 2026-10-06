// Typed API client for the DoorbellCam hub.

export interface EventItem {
  id: number
  ts: number
  kind: 'person' | 'face' | 'motion' | 'doorbell'
  confidence: number
  label: string
  snapshot: string
  boxes: number[][]
}

export interface FaceItem {
  id: number
  name: string
  created_at: number
  updated_at: number
}

export interface HubStatus {
  camera_ip: string | null
  camera_online: boolean
  person_count: number
  faces: { name?: string; box: number[] }[]
  motion_level: number
  fps?: number
  last_event: EventItem | null
  tuning: Record<string, number | boolean>
  camera?: Record<string, number> | null
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

export const api = {
  status: () => fetch('/api/status').then(r => j<HubStatus>(r)),
  events: (limit = 100) =>
    fetch(`/api/events?limit=${limit}`).then(r => j<EventItem[]>(r)),
  deleteEvent: (id: number) =>
    fetch(`/api/events/${id}`, { method: 'DELETE' }),
  clearEvents: () => fetch('/api/events', { method: 'DELETE' }),
  eventSnapshotUrl: (id: number) => `/api/events/${id}/snapshot`,

  faces: () => fetch('/api/faces').then(r => j<FaceItem[]>(r)),
  enrollFace: (name: string, image: File) => {
    const fd = new FormData()
    fd.append('name', name)
    fd.append('image', image)
    return fetch('/api/faces', { method: 'POST', body: fd })
  },
  deleteFace: (name: string) =>
    fetch(`/api/faces/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  settings: () =>
    fetch('/api/settings').then(r => j<Record<string, number | boolean>>(r)),
  setSettings: (patch: Record<string, number | boolean>) =>
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),

  cameraStatus: () =>
    fetch('/api/camera/status').then(r => j<Record<string, number>>(r)),
  cameraControl: (variable: string, val: number) =>
    fetch(`/api/camera/control?var=${variable}&val=${val}`, { method: 'POST' }),

  liveStreamUrl: '/api/camera/stream',
  wsUrl: (() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/api/ws`
  })(),
}
