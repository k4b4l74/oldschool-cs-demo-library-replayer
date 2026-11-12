export default function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null
  const shown = [...new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2])].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b)
  const out: React.ReactNode[] = []
  let last = 0
  for (const n of shown) {
    if (n - last > 1) out.push(<span key={`gap${n}`} className="sub">…</span>)
    out.push(
      <button key={n} type="button" className={n === page ? 'on' : ''} aria-current={n === page ? 'page' : undefined} onClick={() => onPage(n)}>
        {n}
      </button>,
    )
    last = n
  }
  return (
    <nav className="pager" aria-label="Pages">
      {page > 1 && (
        <button type="button" onClick={() => onPage(page - 1)}>
          ‹ prev
        </button>
      )}
      {out}
      {page < pages && (
        <button type="button" onClick={() => onPage(page + 1)}>
          next ›
        </button>
      )}
    </nav>
  )
}
