/**
 * Settings page: camera-sensor controls + hub detection tuning.
 *
 * Left card proxies CameraWebServer-compatible vars (resolution, quality,
 * brightness/contrast/saturation, effects, flips, auto-modes) live to the
 * ESP32 via POST /api/camera/control. Right card tunes hub-side detection
 * (motion sensitivity, cooldown, person confidence, face threshold —
 * debounced 400 ms to /api/settings) plus WebSocket/FCM notification
 * toggles, with an explainer of hub↔camera auto-discovery.
 */
import { useEffect, useRef, useState } from 'react'
import { api, HubStatus } from '../api'

interface SliderDef {
  varName: string
  label: string
  min: number
  max: number
  step?: number
  camera: boolean
}

// Camera sensor controls (CameraWebServer-compatible vars, proxied by the hub)
const CAM_SLIDERS: SliderDef[] = [
  { varName: 'quality',        label: 'JPEG quality',   min: 4,  max: 63, camera: true },
  { varName: 'brightness',     label: 'Brightness',     min: -2, max: 2,  camera: true },
  { varName: 'contrast',       label: 'Contrast',       min: -2, max: 2,  camera: true },
  { varName: 'saturation',     label: 'Saturation',     min: -2, max: 2,  camera: true },
  { varName: 'special_effect', label: 'Effect',         min: 0,  max: 6,  camera: true },
]

const CAM_TOGGLES = [
  { varName: 'vflip',   label: 'Flip vertical' },
  { varName: 'hmirror', label: 'Mirror horizontal' },
  { varName: 'awb',     label: 'Auto white balance' },
  { varName: 'agc',     label: 'Auto gain' },
  { varName: 'aec',     label: 'Auto exposure' },
]

const FRAMESIZES = [
  { v: 5, label: 'SVGA 800×600' },
  { v: 6, label: 'XGA 1024×768' },
  { v: 7, label: 'HD 1280×720' },
  { v: 8, label: 'SXGA 1280×1024' },
  { v: 10, label: 'UXGA 1600×1200' },
]

const HUB_TUNING = [
  { key: 'motion_sensitivity',  label: 'Motion sensitivity', min: 1, max: 100 },
  { key: 'cooldown_seconds',    label: 'Alert cooldown (s)', min: 2, max: 120 },
  { key: 'person_confidence',   label: 'Person confidence',  min: 0.1, max: 0.95, step: 0.05 },
  { key: 'face_match_threshold',label: 'Face match threshold', min: 0.2, max: 0.8, step: 0.02 },
] as const

export default function Settings({ status }: { status: HubStatus | null }) {
  const [cam, setCam] = useState<Record<string, number>>({})
  const [tuning, setTuning] = useState<Record<string, number | boolean>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const debounce = useRef<Record<string, number>>({})

  useEffect(() => {
    api.cameraStatus().then(setCam).catch(() => {})
    api.settings().then(setTuning).catch(() => {})
  }, [])

  const pushCam = async (variable: string, val: number) => {
    setSaving(variable)
    try {
      await api.cameraControl(variable, val)
      setCam(c => ({ ...c, [variable]: val }))
    } catch { /* camera offline */ } finally { setSaving(null) }
  }

  const pushTuning = (key: string, val: number) => {
    setTuning(t => ({ ...t, [key]: val }))
    clearTimeout(debounce.current[key])
    debounce.current[key] = window.setTimeout(() => {
      api.setSettings({ [key]: val })
    }, 400)
  }

  const resolution = cam.framesize ?? 7

  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-2">
      {/* Camera hardware settings — written straight to the ESP32 sensor */}
      <section className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-white">Camera sensor</h3>
          <span className="text-xs text-slate-500">
            {saving ? `setting ${saving}…` : 'live on device'}
          </span>
        </div>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm text-slate-400">Resolution</span>
          <select
            className="input"
            value={FRAMESIZES.find(f => f.v === resolution)?.v ?? 7}
            onChange={e => pushCam('framesize', Number(e.target.value))}
          >
            {FRAMESIZES.map(f => <option key={f.v} value={f.v}>{f.label}</option>)}
          </select>
        </label>

        {CAM_SLIDERS.filter(s => s.varName !== 'special_effect').map(s => (
          <label key={s.varName} className="mb-4 block">
            <span className="mb-1 flex justify-between text-sm text-slate-400">
              {s.label}
              <span className="font-mono text-slate-300">{cam[s.varName] ?? '–'}</span>
            </span>
            <input
              type="range" min={s.min} max={s.max} step={s.step ?? 1}
              value={cam[s.varName] ?? 0}
              onChange={e => pushCam(s.varName, Number(e.target.value))}
              className="w-full accent-sky-500"
            />
          </label>
        ))}

        <label className="mb-4 block">
          <span className="mb-1 block text-sm text-slate-400">Effect</span>
          <select className="input" value={cam.special_effect ?? 0}
                  onChange={e => pushCam('special_effect', Number(e.target.value))}>
            <option value={0}>No effect</option><option value={1}>Negative</option>
            <option value={2}>Grayscale</option><option value={3}>Red tint</option>
            <option value={4}>Green tint</option><option value={5}>Blue tint</option>
            <option value={6}>Sepia</option>
          </select>
        </label>

        <div className="grid grid-cols-2 gap-2">
          {CAM_TOGGLES.map(t => (
            <button
              key={t.varName}
              onClick={() => pushCam(t.varName, cam[t.varName] ? 0 : 1)}
              className={`btn text-sm ${cam[t.varName] ? 'bg-accent-500/20 text-accent-400' : 'bg-ink-800 text-slate-400'}`}
            >
              {t.label} {cam[t.varName] ? '✔' : ''}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {status?.camera_online
            ? 'These controls talk to the ESP32-CAM sensor over WiFi, live.'
            : 'Camera offline — controls will apply once it reconnects.'}
        </p>
      </section>

      {/* Hub-side detection tuning */}
      <section className="card p-5">
        <h3 className="mb-4 font-semibold text-white">Detection & alerts</h3>
        {HUB_TUNING.map(t => (
          <label key={t.key} className="mb-4 block">
            <span className="mb-1 flex justify-between text-sm text-slate-400">
              {t.label}
              <span className="font-mono text-slate-300">{tuning[t.key] ?? '–'}</span>
            </span>
            <input
              type="range" min={t.min} max={t.max} step={'step' in t ? (t as any).step : 1}
              value={Number(tuning[t.key] ?? t.min)}
              onChange={e => pushTuning(t.key, Number(e.target.value))}
              className="w-full accent-sky-500"
            />
          </label>
        ))}

        {(['notify_websocket', 'notify_fcm'] as const).map(k => (
          <label key={k} className="mb-3 flex items-center gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(tuning[k])}
              onChange={e => pushTuning(k, e.target.checked ? 1 : 0)}
              className="h-4 w-4 accent-sky-500"
            />
            {k === 'notify_websocket' ? 'Push to connected apps (WebSocket)' : 'Firebase push (FCM, if configured)'}
          </label>
        ))}

        <div className="mt-6 rounded-xl bg-ink-800 p-4 text-xs leading-relaxed text-slate-400">
          <p className="mb-1 font-semibold text-slate-300">How auto-connection works</p>
          The hub finds the camera via mDNS (<code>doorbellcam.local</code>), falls back to
          scanning the local network, then to the manual IP in <code>.env</code>.
          The Flutter app finds this hub the same way (<code>doorbellhub.local</code>).
        </div>
      </section>
    </div>
  )
}
