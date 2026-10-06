import { useEffect, useRef, useState } from 'react'

/**
 * Self-healing MJPEG viewer. Native <img src=mjpeg> stalls forever when the
 * upstream rotates or hiccups (browsers never retry multipart streams), so we
 * detect a silent stream and force a reload.
 */
export default function MjpegStream({ url, online }: { url: string; online: boolean }) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [key, setKey] = useState(0)
  const lastBytes = useRef(0)
  const lastChange = useRef(Date.now())

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    const tick = () => {
      // naturalWidth > 0 means the current multipart stream delivered frames;
      // decode() completing repeatedly is our "bytes are flowing" signal.
      img.decode().then(() => {
        lastChange.current = Date.now()
      }).catch(() => { /* decoding between frames */ })
    }
    const iv = setInterval(tick, 3000)
    return () => clearInterval(iv)
  }, [key])

  useEffect(() => {
    const iv = setInterval(() => {
      if (Date.now() - lastChange.current > 12000) {
        lastChange.current = Date.now()
        setKey(k => k + 1)   // force <img> remount -> fresh multipart connection
      }
    }, 3000)
    return () => clearInterval(iv)
  }, [])

  // Also remount whenever the camera transitions offline -> online
  useEffect(() => {
    if (online) setKey(k => k + 1)
  }, [online])

  return (
    <img
      key={key}
      ref={imgRef}
      src={`${url}?t=${key}`}
      alt="live stream"
      className="h-full w-full object-contain"
    />
  )
}
