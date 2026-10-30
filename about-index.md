# Frontend — Change Log & Backend Pending Items

## What was built here (frontend project)

### Visual design
- Dark theme: `#111113` surface, `#1c1c1f` card, `#242428` raised — warm charcoal, not pure black
- Brand accent color `#04AA6D` applied throughout (header wordmark, active chips, eq bars, heart icons, player controls)
- All emojis replaced with inline SVGs — consistent `1.8px` stroke weight throughout
- Tailwind CDN config extended with custom color tokens (`surface`, `card`, `raised`, `accent`)

### Layout
- Fixed header: waveform wordmark + centered search + desktop nav
- Fixed player footer: desktop = single horizontal row, mobile = stacked (track info → controls → progress)
- Mobile bottom nav: Home / Search / Library with SVG icons, shifts up when player is visible (`body.player-visible`)
- `<main>` bottom margin accounts for both player and bottom nav

### Player (`player.js`)
- Shuffle: calls `Queue.random()`, button highlights accent when active
- Repeat: restarts current track on `ended`, button highlights accent when active
- Sleep timer: cycles 15 / 30 / 45 / 60 / off, fades audio out over 10s before pausing
- Play/pause uses SVG icon swap (`#icon-play` / `#icon-pause`) instead of textContent
- `body.paused` class toggled on audio play/pause (used by eq-bars animation)
- `body.player-visible` class added when player first appears
- Recently played written to `music_recent` localStorage on every `play()` call — deduped by `track_id`, capped at 20, newest first
- Dispatches `trackchange` custom event with `track_id` on every track start

### Queue (`queue.js`)
- Added `Queue.random()` export for shuffle mode

### Infinite scroll (`scroll.js`) — new module
- `IntersectionObserver` on a sentinel element, 200px lookahead
- `fetchFn(offset)` / `renderFn(tracks, offset)` interface
- Status line: "Showing 40" today → automatically becomes "40 of 40,897" when backend adds `total` field
- Stops observing when a page returns fewer results than `PAGE_SIZE`

### API (`api.js`)
- All three search functions (`searchTracks`, `searchByGenre`, `searchByType`) now accept `offset` param
- `PAGE_SIZE = 20` exported constant

### Home view (`views/home.js`)
- Filter chips replace colored block cards — unified pill style, accent active state
- Type chips include inline SVG icons (music note, mic, book, dots)
- Mood and genre chips are plain text — no emojis
- Infinite scroll on genre/type results via `InfiniteScroll`
- Auto-scrolls to results section when a chip is selected
- Empty state shown below filters when nothing is selected yet
- Heart button on every track row — saves/unsaves via `library.js`
- Duration shown on track rows
- Now-playing indicator: green border + eq-bars animation on active row

### Search view (`views/search.js`)
- Infinite scroll — pages load as user scrolls, artist chips rebuild after each page
- Artist → Album drill-down filter (client-side, built from loaded results)
- "Play all" queues current filtered view
- Heart button on every track row
- Now-playing indicator on active row

### Library view (`views/library.js`) — new
- Renders saved tracks from `music_library` localStorage
- "Play all" button
- Heart button removes track from library and re-renders
- Empty state with heart icon and prompt

### Library module (`library.js`) — new
- `getSaved()`, `isSaved(track_id)`, `toggleSaved(track)` — all localStorage-backed

### App shell (`app.js`)
- Router handles `#/`, `#/search`, `#/library` — 404 fallback for unknown routes
- Active nav link highlighted on route change (`.active` class on `.nav-link` and `.bottom-nav-item`)
- Keyboard shortcuts: Space = play/pause, ←/→ = seek ±10s, N = next, P = prev (blocked when input focused)
- `trackchange` event listener updates `now-playing` class on visible track rows

### CSS (`app.css`)
- Custom range input styling (no OS default appearance, white thumb, scales on hover)
- `.chip` / `.chip-active` — unified filter pill styles
- `.section-label` — consistent uppercase section headers
- `.now-playing` — green-tinted border + background on active track row
- `.eq-bars` — animated 3-bar equaliser, pauses when `body.paused`
- `.scroll-row` — horizontal scrollable container, hidden scrollbar
- Bottom nav shift rule: `body.player-visible #bottom-nav { bottom: 7.5rem }`

### PWA
- `service-worker.js` cache updated to include `scroll.js`, `library.js`, `views/library.js`
- `<audio crossorigin="anonymous">` added for future Web Audio API use

### Hamburger menu & drawer
- Hamburger button in fixed header (mobile only) — matches GC's Office pattern
- Drawer slides in from right: `translate-x-full` toggle, `duration-300` transition
- Overlay click-to-close, all drawer links call `closeMenu()` inline
- Drawer nav links: Home, Search, Library, About
- Divider separates nav from external links
- GitHub link → `https://github.com/Shannon-Goddard/music`
- "Buy the Dev a Beer" button styled in accent green (`#04AA6D`) with mug SVG icon → Buy Me a Coffee (`goddardshannon9`)

### Legal & info pages (all dark-themed, consistent drawer + footer)
- **`about.html`** — mission statement (free music, Internet Archive, no account), analytics disclosure, Shannon Goddard bio, Loyal9 LLC, Amazon Q credit, MIT open source section. Targets Google quality rater E-E-A-T signals.
- **`privacy.html`** — Google Analytics (anonymous aggregate only, personal dev use), localStorage (never transmitted), no identity data collected, no selling or sharing
- **`terms.html`** — as-is free service, CC/public domain music, MIT code license, no scraping, California governing law
- **`licenses.html`** — this project MIT, Tailwind MIT, boto3 Apache 2.0, AWS services, Internet Archive content, Creative Commons license types with links (CC BY, CC BY-SA, CC BY-NC, CC0)
- All four pages share identical inlined CSS, identical drawer HTML/JS, footer with Privacy / Terms / Licenses links
- Canonical URLs reference `shannon-goddard.loyal9.app/music/` — update to actual deployed domain when live

---

## Pending — needs backend work (other project)

### High priority

1. **`total` field in all search responses**
   - Currently the API returns `{ count, results }` where `count` = results in this page
   - Need `total` = total matching records in the database
   - Frontend `InfiniteScroll` already checks for `data.total` — zero frontend changes needed once added
   - Affects: `GET /tracks/search?q=`, `?genre=`, `?type=`

2. **`offset` param validation**
   - Frontend sends `&offset=20`, `&offset=40` etc.
   - Confirmed working in testing but needs to be stable — currently returns some duplicate records across pages (observed in manual curl test)
   - Needs consistent ordering (e.g. `ORDER BY track_id`) so pages don't overlap or skip

### Medium priority

3. **Dedicated artist endpoint**
   - `GET /artists/search?q={query}` → `{ results: [{ artist_id, artist_name, track_count }] }`
   - Currently artist filtering is client-side on whatever tracks happen to be in the loaded pages
   - A real artist search would let users find artists directly without loading tracks first

4. **Dedicated album endpoint**
   - `GET /albums/search?artist_id={id}` or `?q={query}` → `{ results: [{ album_id, album_title, artist_name, track_count, cover_art_url }] }`
   - Same issue as above — album chips only show albums present in loaded pages

5. **Cover art**
   - Most tracks return `cover_art_url: null`
   - Even a low-res thumbnail per album would significantly improve the visual quality of the Recently Played row and track rows
   - If scraping cover art isn't feasible, consider a fallback: generate a deterministic gradient per `album_id` as a placeholder

### Lower priority

6. **License / attribution data surfacing**
   - `attribution_text` and `license_type` are in the API response but not displayed anywhere in the UI yet
   - A small "i" button on each track row could show this — important for a platform built on open-licensed content
   - Frontend can add this without backend changes, but worth noting

7. **Download endpoint or direct link**
   - `is_downloadable: true` is present on many tracks
   - `source_url` points to the Internet Archive page
   - A download button linking to `stream_url` with a `download` attribute would be straightforward
