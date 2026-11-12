---
name: frontend-page
description: Build or change a page or component of the React frontend in the project's style (olive "old CS menus" theme, plain-English texts, URL-kept filters, React Query) with its tests. Use for any UI work.
---

# Frontend pages

React 19 + TypeScript + Vite, TanStack Query, React Router, Vitest + Testing Library, oxlint. Pages live in `frontend/src/pages/`, routes and the top menu in `src/App.tsx`, styles in `src/index.css` (one file).

## Look

- Theme tokens on `:root` in `index.css`: `--bg --panel --panel-2 --panel-3 --title --text --muted --line --hi --accent --on-accent --link --hud --ct --t --ok --warn --bad --font --mono`, redefined for the light "paper" theme. Use tokens, never raw colours.
- Building blocks: `section.panel` with `header.panel-head > h2` (a window with a title bar), `table.results`, `.pill.ok/.warning/.broken`, `.sub` (secondary text), `.mono`, `button.primary`, `button.ghost`, `button.link`, `.toolbar`, `.field`, `.add-row`.
- Colours and shapes only: **no Valve logos, fonts or images**, no brand logos.
- **Never upper-case player names, team tags or file names** (CSS `text-transform` included): literal spellings matter. Upper case is only for headings and labels.
- Must work at phone width (380 px): wrap, don't scroll sideways.

## Texts

Short, plain English for a player, not a developer: say what happens and what to do ("No working install for CS 1.5: add one in Settings"). Server error `detail` strings are shown as they are, so write those the same way.

## Data

- Read with `useQuery` and the typed `api` from `src/api/client.ts`; change with `useMutation`, then `invalidateQueries` what it affects and report with `useToast()` (`'ok' | 'error'`).
- Filters and search live in the URL (`useSearchParams`), so a search can be bookmarked or shared (see `Library.tsx`).
- Helpers and non-component exports go in `.ts` files (oxlint `only-export-components`).

## Tests

```tsx
mockApi({ '/api/settings': settings, '/api/engines': view })
renderAt('/settings', '/settings', <ToastProvider><Settings /></ToastProvider>)
expect(await screen.findByRole('button', { name: 'Save keys' })).toBeDisabled()
```

- Query by role and accessible name (`aria-label` on inputs and icon buttons); `<input list>` is a `combobox`, `type="search"` a `searchbox`.
- For changes, assert the `fetch` call: URL, method, JSON body.
- Keep fixtures complete for the generated types (TypeScript flags missing fields).

Look at the result in a browser before calling it done (see the check-and-ci skill for headless screenshots).
