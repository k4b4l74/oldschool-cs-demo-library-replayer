export const clock = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

export const duration = (s: number) => (s ? clock(s) : '–')

/** CSS class for a side as stored in the database ('CT' / 'TERRORIST'). */
export const sideClass = (side?: string | null) => (side === 'CT' ? 'ct' : side === 'TERRORIST' ? 't' : '')

export const sideShort = (side?: string | null) => (side === 'CT' ? 'CT' : side === 'TERRORIST' ? 'T' : side ?? '')

/** Seconds of lead before a round start or a kill when jumping into a demo. */
export const ROUND_LEAD = 1
export const KILL_LEAD = 5


export const reason = (r?: string | null) => (r ?? '').replace(/_/g, ' ')
