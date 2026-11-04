const SPEECH_LANG = { vi: 'vi-VN', en: 'en-US', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR' }

async function playUrl(audio, url) {
  audio.src = url
  await audio.play()
  return new Promise((resolve, reject) => {
    audio.onended = resolve
    audio.onerror = () => reject(new Error('audio error'))
  })
}

async function postJson(url, body, signal) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  if (!res.ok) throw new Error(`${url} ${res.status}`)
  return res
}

/**
 * Phát thuyết minh theo 4 tầng (single-slot: yêu cầu mới thay thế yêu cầu cũ):
 *  1 pre-gen audio_url → 1.5 on-demand → 2 cloud TTS → 3 speechSynthesis
 * Kết quả on-demand cũ bị bỏ nếu người dùng đã đổi ngôn ngữ trong lúc chờ.
 */
export class NarrationEngine {
  constructor({ getLang, onTier, onFinished } = {}) {
    this.getLang = getLang
    this.onTier = onTier
    this.onFinished = onFinished
    this.audio = new Audio()
    this.ticket = 0
    this.abort = null
  }

  stop() {
    this.ticket++
    this.abort?.abort()
    this.audio.pause()
    window.speechSynthesis?.cancel()
  }

  async narrate(poi) {
    this.stop()
    const ticket = this.ticket
    const lang = this.getLang()
    this.abort = new AbortController()
    const { signal } = this.abort
    const stale = () => ticket !== this.ticket || lang !== this.getLang()
    const tiers = [
      ['1', async () => {
        if (!poi.audio_url || poi.is_fallback) throw new Error('no pregen')
        await playUrl(this.audio, poi.audio_url)
      }],
      ['1.5', async () => {
        const res = await postJson('/api/v1/localizations/on-demand', { poi_id: poi.id, lang }, signal)
        const data = await res.json()
        if (stale()) return
        await playUrl(this.audio, data.audio_url)
      }],
      ['2', async () => {
        const res = await postJson('/api/v1/audio/tts', { text: `${poi.name}. ${poi.description}`, lang: poi.lang || lang }, signal)
        const blob = await res.blob()
        if (stale()) return
        const url = URL.createObjectURL(blob)
        try { await playUrl(this.audio, url) } finally { URL.revokeObjectURL(url) }
      }],
      ['3', async () => {
        await new Promise((resolve, reject) => {
          const u = new SpeechSynthesisUtterance(`${poi.name}. ${poi.description}`)
          u.lang = SPEECH_LANG[poi.lang || lang] || 'vi-VN'
          u.onend = resolve
          u.onerror = reject
          window.speechSynthesis.speak(u)
        })
      }],
    ]
    for (const [tier, run] of tiers) {
      if (stale()) return
      try {
        this.onTier?.(tier)
        await run()
        if (!stale()) this.onFinished?.(poi)
        return
      } catch (e) {
        if (e.name === 'AbortError' || stale()) return
      }
    }
  }
}
