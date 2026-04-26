export function playNotificationChime() {
  try {
    const ctx = new AudioContext()

    const notes = [
      { freq: 1047, start: 0,    dur: 0.5 },  // C6
      { freq: 1319, start: 0.12, dur: 0.5 },  // E6
      { freq: 1568, start: 0.24, dur: 0.7 },  // G6
    ]

    notes.forEach(({ freq, start, dur }) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, ctx.currentTime + start)

      gain.gain.setValueAtTime(0, ctx.currentTime + start)
      gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + start + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + dur)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start(ctx.currentTime + start)
      osc.stop(ctx.currentTime + start + dur)
    })

    setTimeout(() => ctx.close(), 1500)
  } catch {
    // AudioContext not available in this environment
  }
}
