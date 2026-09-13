/** Show the first delta immediately; coalesce subsequent renders per animation frame. */
export function createStreamTextBatcher(commit: (text: string) => void) {
  let frame: number | null = null
  let pending: string | null = null
  let first = true

  const flush = () => {
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    if (pending !== null) {
      const text = pending
      pending = null
      commit(text)
    }
  }

  return {
    push(text: string) {
      pending = text
      if (first) {
        first = false
        flush()
      } else if (frame === null) {
        frame = requestAnimationFrame(flush)
      }
    },
    flush,
    cancel() {
      if (frame !== null) cancelAnimationFrame(frame)
      frame = null
      pending = null
    },
  }
}
