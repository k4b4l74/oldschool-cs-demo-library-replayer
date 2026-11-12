import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const LINKS = [
  { what: 'GitHub', handle: 'k4b4l74', url: 'https://github.com/k4b4l74' },
  { what: 'X', handle: '@the_kabal', url: 'https://x.com/the_kabal' },
  { what: 'YouTube', handle: '@k4b4l74', url: 'https://www.youtube.com/@k4b4l74' },
]
const REPO = 'https://github.com/k4b4l74/oldschool-cs-demo-library-replayer'

/** Who made the app and where to reach him. */
export default function Contact() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  return (
    <article className="contact">
      <h1>Contact</h1>
      <section className="panel">
        <header className="panel-head">
          <h2>Made by</h2>
        </header>
        <p className="author">Guillaume &lt;KabaL&gt; ETTORI</p>
        <ul className="contact-links">
          {LINKS.map((l) => (
            <li key={l.what}>
              <span className="what">{l.what}</span>
              <a href={l.url} target="_blank" rel="noopener noreferrer">
                {l.handle}
              </a>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <header className="panel-head">
          <h2>The app</h2>
        </header>
        <p>
          Oldschool CS Demos Library Replayer{health.data && ` v${health.data.version}`}. Source code, questions and bug reports:{' '}
          <a href={REPO} target="_blank" rel="noopener noreferrer">
            github.com/k4b4l74/oldschool-cs-demo-library-replayer
          </a>
          .
        </p>
        <p className="sub">Counter-Strike and Half-Life belong to Valve. This app ships none of their files.</p>
      </section>
    </article>
  )
}
