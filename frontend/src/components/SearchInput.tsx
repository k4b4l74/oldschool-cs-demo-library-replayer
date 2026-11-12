import { useEffect, useState } from 'react'

/** Search box that reports its text after a short pause, not on every key.
 * When ``value`` changes from outside (back button, reset), the box follows. */
export default function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  className = 'big-search',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  label: string
  className?: string
}) {
  const [text, setText] = useState(value)
  const [outside, setOutside] = useState(value)
  if (value !== outside) {
    setOutside(value)
    setText(value)
  }
  useEffect(() => {
    if (text === value) return
    const t = setTimeout(() => onChange(text), 300)
    return () => clearTimeout(t)
  }, [text, value, onChange])
  return <input type="search" aria-label={label} className={className} value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} />
}
