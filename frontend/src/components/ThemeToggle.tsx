import { useEffect, useState } from 'react'

const KEY = 'oldschool-theme'
type Theme = 'olive' | 'paper'

function read(): Theme {
  try {
    return localStorage.getItem(KEY) === 'paper' ? 'paper' : 'olive'
  } catch {
    return 'olive'
  }
}

/** Olive (the default, after the old in-game menus) or paper (light). */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(read)
  useEffect(() => {
    if (theme === 'paper') document.documentElement.dataset.theme = 'paper'
    else delete document.documentElement.dataset.theme
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* storage unavailable: the choice lasts for this visit */
    }
  }, [theme])
  return (
    <button
      type="button"
      className="ghost"
      aria-label={theme === 'olive' ? 'Switch to the light theme' : 'Switch to the olive theme'}
      title={theme === 'olive' ? 'Light theme' : 'Olive theme'}
      onClick={() => setTheme(theme === 'olive' ? 'paper' : 'olive')}
    >
      {theme === 'olive' ? '☀' : '☾'}
    </button>
  )
}
