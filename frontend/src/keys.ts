/** Key names of the Half-Life engine, from the browser's key position (KeyboardEvent.code).
 * Before the 2013 Steam versions the game reads positions with a US layout: the key labelled
 * Z on a French keyboard is "w" for the game. Labels shown in the page use the player's layout. */
const NAMED: Record<string, string> = {
  Space: 'space', Enter: 'enter', Tab: 'tab', Backspace: 'backspace',
  ArrowUp: 'uparrow', ArrowDown: 'downarrow', ArrowLeft: 'leftarrow', ArrowRight: 'rightarrow',
  ShiftLeft: 'shift', ShiftRight: 'shift', ControlLeft: 'ctrl', ControlRight: 'ctrl', AltLeft: 'alt', AltRight: 'alt',
  Insert: 'ins', Delete: 'del', PageUp: 'pgup', PageDown: 'pgdn', Home: 'home', End: 'end', Pause: 'pause', CapsLock: 'capslock',
  Semicolon: 'semicolon', BracketLeft: '[', BracketRight: ']', Backslash: '\\', Quote: "'", Comma: ',', Period: '.', Slash: '/',
  Minus: '-', Equal: '=', Backquote: '`',
  Numpad7: 'kp_home', Numpad8: 'kp_uparrow', Numpad9: 'kp_pgup', Numpad4: 'kp_leftarrow', Numpad5: 'kp_5', Numpad6: 'kp_rightarrow',
  Numpad1: 'kp_end', Numpad2: 'kp_downarrow', Numpad3: 'kp_pgdn', Numpad0: 'kp_ins', NumpadDecimal: 'kp_del', NumpadEnter: 'kp_enter',
  NumpadDivide: 'kp_slash', NumpadSubtract: 'kp_minus', NumpadAdd: 'kp_plus', NumpadMultiply: '*',
}

export function gameKey(code: string): string | null {
  let m = /^Key([A-Z])$/.exec(code)
  if (m) return m[1].toLowerCase()
  m = /^Digit(\d)$/.exec(code)
  if (m) return m[1]
  m = /^F(\d{1,2})$/.exec(code)
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 12) return `f${m[1]}`
  return NAMED[code] ?? null
}

/** The key position (KeyboardEvent.code) of a game key name, for layout labels. */
export function codeOf(key: string): string | null {
  if (/^[a-z]$/.test(key)) return `Key${key.toUpperCase()}`
  if (/^\d$/.test(key)) return `Digit${key}`
  return Object.entries(NAMED).find(([, v]) => v === key)?.[0] ?? null
}

/** MouseEvent.button → game name. */
export function gameMouse(button: number): string | null {
  return ({ 0: 'mouse1', 1: 'mouse3', 2: 'mouse2', 3: 'mouse4', 4: 'mouse5' } as Record<number, string>)[button] ?? null
}

const PRETTY: Record<string, string> = {
  uparrow: '↑', downarrow: '↓', leftarrow: '←', rightarrow: '→', space: 'Space', ctrl: 'Ctrl', shift: 'Shift', alt: 'Alt', tab: 'Tab',
  enter: 'Enter', backspace: 'Backspace', ins: 'Insert', del: 'Delete', pgup: 'Page up', pgdn: 'Page down', home: 'Home', end: 'End',
  pause: 'Pause', capslock: 'Caps lock', semicolon: ';',
  mouse1: 'Left click', mouse2: 'Right click', mouse3: 'Middle click', mouse4: 'Mouse 4', mouse5: 'Mouse 5', mwheelup: 'Wheel up', mwheeldown: 'Wheel down',
  kp_home: 'Num 7', kp_uparrow: 'Num 8', kp_pgup: 'Num 9', kp_leftarrow: 'Num 4', kp_5: 'Num 5', kp_rightarrow: 'Num 6', kp_end: 'Num 1',
  kp_downarrow: 'Num 2', kp_pgdn: 'Num 3', kp_ins: 'Num 0', kp_del: 'Num .', kp_enter: 'Num Enter', kp_slash: 'Num /', kp_minus: 'Num −',
  kp_plus: 'Num +', '*': 'Num *',
}

/** What the player sees on their keyboard for a game key. `layout` is the browser's keyboard map (code → character) when known. */
export function keyLabel(key: string, layout?: Map<string, string> | null): string {
  if (PRETTY[key]) return PRETTY[key]
  if (/^f\d+$/.test(key)) return key.toUpperCase()
  const code = codeOf(key)
  const printed = code && layout?.get(code)
  return (printed || key).toUpperCase()
}
