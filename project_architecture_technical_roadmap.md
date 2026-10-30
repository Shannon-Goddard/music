# Architecture & Technical Roadmap: Infinite Meta-Index Music Platform

This document is the master engineering blueprint for the platform. It reflects the current live state of the project and the forward roadmap. Updated to sync with `about-index.md`.

---

## Current Live State

| Layer | Status | Detail |
|---|---|---|
| DynamoDB table | ✅ Live | `music-tracks`, `us-east-1`, 9,618 records |
| GSIs | ✅ All 7 ACTIVE | See Section 2 |
| Ingestion | ✅ Done | `netlabels` (4,734) + `78rpm` (4,884) |
| `content_type` classification | ✅ Done | 5,373 music, rest classified |
| API — `/tracks/search` | ✅ Live | `q=`, `genre=`, `type=`, `offset=`, `total` in response |
| API — `/artists/search` | ✅ Live | `q=` → `{ artist_id, artist_name, track_count }` |
| API — `/albums/search` | ✅ Live | `artist_id=` (GSI) or `q=` (scan) → albums with track counts |
| Frontend PWA | ✅ Live | `https://shannon-goddard.github.io/music/` |
| GitHub Pages deployment | ✅ Live | `gh-pages` branch, `master` → sync workflow |

**API base URL:** `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1`

---

## Architecture Overview

```
[ Data Sources ]
 (Internet Archive ✅, Jamendo 🔜, FMA 🔜, MusicBrainz 🔜)
       │
       ▼
[ Ingestion & Normalization Layer ] ──> Automated Cron Jobs (GitHub Actions / AWS Lambda)
       │                                        │
       ▼                                        ▼
[ AcoustID Fingerprint Checker ] ──> Reject / Flag Unverified Tracks
       │
       ▼
[ AWS DynamoDB ] ─────────────────────> Uncapped Meta-Index (Core Data + Source Tracking)
       │
       ├──> [ Public Read-Only API Tier ] ──────────────────────────────────────────────────┐
       │         │                                                                           │
       │         ├──> Researchers (bulk export, DOI, BibTeX, acoustic features)             │
       │         ├──> Developers (API keys, usage plans, OpenAPI docs, SDKs)                │
       │         ├──> Educators (BPM/key filters, curriculum-ready query params)            │
       │         ├──> Archivists (dead link dashboard, health history endpoint)             │
       │         └──> App Builders (royalty-free search, M3U export, embed widget)         │
       │                                                                                    │
       ▼                                                                                    │
[ AWS API Gateway + Lambda ] ─────────> Serverless REST API (WAF, Rate Limited, CORS) <───┘
       │
       ▼
[ GitHub Pages (Frontend) ] ──────────> PWA / SPA HTML5 Web Player
       │
       ├──> Casual Listeners     (radio, queue, Bluetooth, sleep timer)
       ├──> Music Enthusiasts    (tag browse, infinite scroll, library, deep links)
       ├──> Content Creators     (CC filter, download, copy attribution string)
       └──> Accessibility Users  (keyboard nav, reduced motion)
```

---

## 1. Database Schema (DynamoDB — Flat, Live)

The actual deployed schema uses flat top-level attributes (no nested objects). Every track record:

```json
{
  "track_id":         "TRK-IA-autojazz",
  "title":            "Autojazz",
  "artist_id":        "ART-IA-8eee9be3",
  "artist_name":      "Jazzaria.com",
  "album_id":         "ALB-IA-autojazz",
  "album_title":      "Autojazz",
  "track_number":     null,
  "genre":            "jazz",
  "tags":             ["jazz", "improvisation", "waltz"],
  "mood":             null,
  "bpm":              null,
  "content_type":     "music",
  "duration_sec":     null,
  "cover_art_url":    null,
  "stream_url":       "https://archive.org/download/autojazz/autojazz.mp3",
  "source_url":       "https://archive.org/details/autojazz",
  "source_platform":  "internet_archive",
  "ia_collection":    "netlabels",
  "license_type":     "https://creativecommons.org/licenses/by-nc-nd/4.0/",
  "is_streamable":    true,
  "is_downloadable":  true,
  "attribution_text": "\"Autojazz\" by Jazzaria.com — CC-BY-NC-ND 4.0 — archive.org/details/autojazz",
  "health_status":    "active",
  "last_checked_at":  "2026-10-29T06:44:00Z",
  "added_at":         "2026-10-29T06:44:00Z",
  "dataset_version":  "v1.0.0"
}
```

Future fields (not yet populated): `bpm`, `mood`, `track_number`, `cover_art_url`, `acoustid_fingerprint`, `acoustid_id`, `musicbrainz_artist_id`, `doi`, `play_count`.

---

## 2. DynamoDB GSIs (All 7 Deployed & ACTIVE)

| Index | Hash Key | Range Key | Used By |
|---|---|---|---|
| `ArtistIndex` | `artist_id` | `album_title` | `/albums/search?artist_id=` |
| `AlbumIndex` | `album_id` | `track_number` | future `/album/{id}` |
| `GenreIndex` | `genre` | `added_at` | `/tracks/search?genre=` |
| `HealthIndex` | `health_status` | `last_checked_at` | link checker |
| `MoodIndex` | `mood` | `bpm` | future mood filter |
| `ContentTypeIndex` | `content_type` | `added_at` | `/tracks/search?type=` |
| `DatasetIndex` | `dataset_version` | `added_at` | future dataset export |

All GSIs use `PAY_PER_REQUEST` billing and `ProjectionType: ALL`.

---

## 3. Technical Roadmap

### Phase 1: Modular Ingestion & Pipeline Setup ✅ Complete

- **1.1** Multi-source adapters — `ia_adapter.py` live, `jamendo_adapter.py` / `fma_adapter.py` pending
- **1.2** Normalization & deduplication — `normalizer.py` + `deduplicator.py` live
- **1.3** Targeted collection strategy — `netlabels` (modern CC) + `78rpm` (pre-1930s) ingested clean
- **1.4** `content_type` classification — `_detect_content_type()` in `ia_adapter.py`, backfill script ran on all records
- **1.5** AcoustID fingerprint verification — `acoustid_checker.py` planned (Phase 6)

---

### Phase 2: Database Design ✅ Complete

- Flat DynamoDB schema deployed (see Section 1)
- All 7 GSIs ACTIVE (see Section 2)
- On-demand capacity mode enabled

---

### Phase 3: Automated Lifecycle Maintenance 🔜 Pending

- **3.1** Monthly ingestion cron — GitHub Actions EventBridge trigger on 1st of month
- **3.2** Dead link health checker — `link_checker.py` exists, needs scheduling + DLQ wiring
- **3.3** Retry strategy — exponential backoff (5s / 30s / 120s), `pending_recheck` flag on timeout

---

### Phase 4: API Gateway & Lambda ✅ Partially Complete

#### Live Endpoints

| Method | Path | Lambda | Status |
|---|---|---|---|
| GET | `/tracks/search?q=` | `music-search` | ✅ Live |
| GET | `/tracks/search?genre=` | `music-search` | ✅ Live |
| GET | `/tracks/search?type=` | `music-search` | ✅ Live |
| GET | `/artists/search?q=` | `music-artists` | ✅ Live |
| GET | `/albums/search?artist_id=` | `music-albums` | ✅ Live |
| GET | `/albums/search?q=` | `music-albums` | ✅ Live |

All live endpoints support `offset=` + `limit=` pagination and return `{ count, total, offset, query, results }`.

#### Pending Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/tracks/{id}` | Single track detail |
| GET | `/album/{id}` | Tracklist sorted by `track_number` |
| GET | `/radio?genre=` | Randomized active tracks by genre |
| GET | `/tracks/filter` | BPM, key, mood, license, downloadable |
| GET | `/stats` | Total count, source breakdown, genre distribution |
| GET | `/health-history?days=` | Time-series dead link data |
| GET | `/export` | Bulk dataset export (researchers) |
| GET | `/embed/{id}` | iframe-safe embeddable player |
| GET | `/playlist/{id}/m3u` | M3U playlist export |
| POST | `/session` | Save/restore queue (Cognito-authenticated) |
| POST | `/register` | Self-serve API key |

#### API Security (Pending)
- AWS WAF rate limiting: 100 req/min per IP
- CORS locked to GitHub Pages origin in production
- Input schema validation on all Lambda handlers
- API keys via Secrets Manager (Jamendo credentials already stored at `music/jamendo`)

---

### Phase 5: PWA & Cross-Device Playback ✅ Partially Complete

- **5.1** PWA manifest + service worker — ✅ live, `start_url: /music/`, `scope: /music/`, solid green icons
- **5.2** Media Session API — 🔜 pending (Bluetooth / hardware controls)
- **5.3** Chromecast / Cast SDK — 🔜 pending
- **5.4** AirPlay — ✅ zero-config, `<audio crossorigin="anonymous">` in place
- **5.5** Persistent queue sync — localStorage done, cross-device `/session` pending

---

### Phase 6: Production Hardening 🔜 Pending

- **6.1** CloudWatch structured logging + alarms (Lambda error rate, DLQ count, 5xx rate)
- **6.2** SQS Dead Letter Queue for ingestion and health-check jobs
- **6.3** WAF managed rule sets (SQLi, XSS)
- **6.4** AcoustID pipeline — `acoustid_checker.py` using `pyacoustid` + `fpcalc`

---

### Phase 7: Developer Experience 🔜 Pending

- **7.1** `docs/openapi.yaml` — OpenAPI 3.0 spec, Swagger UI at `/docs`
- **7.2** Local dev setup — DynamoDB Local + SAM CLI + frontend hot reload
- **7.3** `CONTRIBUTING.md` — adapter interface contract, schema change process
- **7.4** CI pipeline — `pytest`, `ruff`, `eslint`, OpenAPI validation on every PR

---

### Phase 8: User Experience 🔜 Partially Complete

- **8.1** Accessibility (WCAG 2.1 AA) — keyboard nav ✅, aria-labels 🔜, axe-core CI 🔜
- **8.2** Visual polish — dark theme ✅, eq-bars ✅, skeleton loaders 🔜, waveform scrubber 🔜
- **8.3** Discoverability — tag browse 🔜, similar tracks 🔜, shareable URLs 🔜
- **8.4** i18n — `js/i18n/en.js` exists ✅, strings not yet fully extracted 🔜

---

### Phase 9: Research & Data Access 🔜 Pending

- DOI registration via Zenodo
- Quarterly dataset snapshots (JSON + CSV) uploaded via GitHub Actions
- `CITATION.cff` + BibTeX block in README
- MusicBrainz cross-reference via `musicbrainz_artist_id`
- Acoustic feature dataset documentation (BPM, key, AcoustID)

---

### Phase 10: Extended Use Cases 🔜 Pending

- **10.1** Educator quick-start — `/tracks/filter` with BPM/key/mood params
- **10.2** Developer API key tier — free / developer / partner usage plans
- **10.3** Creator Tools view — CC filter, download button, one-click attribution copy
- **10.4** Archivist health dashboard — dead link trends, `GET /health-history`
- **10.5** Playlist curators — saved playlists, M3U export, embeddable widget
- **10.6** Focus Mode — stripped UI, high contrast, reduced motion

---

### Phase 11: Listener-First PWA Features (iPod Replacement) ✅ Partially Complete

| Feature | Status | Notes |
|---|---|---|
| Sleep timer | ✅ Live | 15/30/45/60/off, 10s fade-out |
| Shuffle | ✅ Live | `Queue.random()` |
| Repeat | ✅ Live | Restarts on `ended` |
| Recently played | ✅ Live | `music_recent` localStorage, capped at 20 |
| My Library (local) | ✅ Live | `music_library` localStorage, heart toggle |
| Library view | ✅ Live | `views/library.js`, Play all, empty state |
| Home view | ✅ Live | Filter chips, infinite scroll, now-playing indicator |
| Infinite scroll | ✅ Live | `scroll.js`, `IntersectionObserver`, "X of Y" status |
| Keyboard shortcuts | ✅ Live | Space, ←/→, N, P |
| Offline queue caching | 🔜 Pending | Pre-fetch next 2–3 tracks via Cache API |
| Continue where left off | 🔜 Pending | 10s position write + Resume prompt on open |
| My Library (server-side) | 🔜 Pending | Cognito + `GET/POST/DELETE /library` |
| Crossfade | 🔜 Pending | Web Audio API, configurable duration |
| Playback speed | 🔜 Pending | `playbackRate` control, persisted |
| Settings view | 🔜 Pending | `settings.js` — crossfade, speed, theme, cache |
| Media Session API | 🔜 Pending | Bluetooth / lock screen / car stereo controls |
| Chromecast | 🔜 Pending | Cast SDK, `<google-cast-launcher>` |

---

## 4. Frontend — What's Built (Live on gh-pages)

### Visual Design
- Dark theme: `#111113` surface, `#1c1c1f` card, `#242428` raised
- Brand accent: `#04AA6D` — header wordmark, active chips, eq bars, heart icons, player controls
- All emojis replaced with inline SVGs, consistent `1.8px` stroke weight
- Tailwind CDN 3.4.1 with custom color tokens (`surface`, `card`, `raised`, `accent`)
- `console.warn` intercept suppresses Tailwind CDN production warning

### Layout
- Fixed header: waveform wordmark + centered search + desktop nav
- Fixed player footer: desktop = single row, mobile = stacked (track info → controls → progress)
- Mobile bottom nav: Home / Search / Library, shifts up when player visible (`body.player-visible`)
- Hamburger drawer (mobile): slides from right, overlay click-to-close

### Player (`player.js`)
- Shuffle, repeat, sleep timer (15/30/45/60/off with 10s fade)
- SVG icon swap on play/pause, `body.paused` class for eq-bars
- `trackchange` custom event dispatched on every track start
- Recently played written to `music_recent` localStorage on every `play()`

### API (`api.js`)
- `searchTracks(q, limit, offset)`, `searchByGenre(genre, limit, offset)`, `searchByType(type, limit, offset)`
- `searchArtists(query)` → `GET /artists/search?q=`
- `searchAlbums({ artistId, query })` → `GET /albums/search?artist_id=` or `?q=`
- `PAGE_SIZE = 20` exported

### Views
- `views/home.js` — filter chips (type + genre + mood), infinite scroll, heart buttons, now-playing indicator
- `views/search.js` — infinite scroll, artist→album drill-down, Play all, heart buttons, now-playing
- `views/library.js` — renders `music_library` localStorage, Play all, heart removes track, empty state

### Modules
- `scroll.js` — `IntersectionObserver` sentinel, `fetchFn(offset)` / `renderFn(tracks, offset)`, "X of Y" status
- `library.js` — `getSaved()`, `isSaved(track_id)`, `toggleSaved(track)`, localStorage-backed
- `queue.js` — `Queue.random()` for shuffle

### App Shell (`app.js`)
- Router: `#/`, `#/search`, `#/library`, 404 fallback
- Active nav highlighting on route change
- Keyboard shortcuts: Space, ←/→ ±10s, N, P (blocked when input focused)
- `trackchange` listener updates `.now-playing` on visible rows

### CSS (`app.css`)
- `.chip` / `.chip-active`, `.now-playing`, `.eq-bars` (animated, pauses on `body.paused`)
- `.scroll-row` — horizontal scrollable, hidden scrollbar
- Custom range input styling, bottom nav shift rule

### PWA
- `manifest.json`: `start_url: /music/`, `scope: /music/`, solid green icons (192×192, 512×512)
- `service-worker.js`: cache `v2`, includes `scroll.js`, `library.js`, `views/library.js`
- `<audio crossorigin="anonymous">` for future Web Audio API

### Legal Pages
- `about.html`, `privacy.html`, `terms.html`, `licenses.html` — dark-themed, shared drawer, E-E-A-T signals

---

## 5. Ingestion Sources

| Source | Status | Collection | Records |
|---|---|---|---|
| Internet Archive — netlabels | ✅ Done | `netlabels` | 4,734 |
| Internet Archive — 78rpm | ✅ Done | `78rpm` | 4,884 |
| Jamendo | 🔜 Next | — | credentials in Secrets Manager `music/jamendo` |
| Free Music Archive (FMA) | 🔜 Planned | — | — |
| MusicBrainz | 🔜 Planned | — | cross-reference only |

**Total live records:** 9,618 (5,373 music, 60 podcast, 35 other, 13 lecture, 7 interview + remainder)

---

## 6. Folder Structure (Current)

```
music/
├── backend/
│   ├── api/
│   │   ├── search.py               # Lambda: GET /tracks/search (q, genre, type, offset, total)
│   │   ├── artists.py              # Lambda: GET /artists/search?q=
│   │   └── albums.py               # Lambda: GET /albums/search?artist_id= or ?q=
│   ├── db/
│   │   └── dynamo_client.py        # Shared DynamoDB client
│   ├── health/
│   │   └── link_checker.py         # HEAD request checker, exponential backoff
│   ├── ingestion/
│   │   ├── base_adapter.py         # Shared adapter interface
│   │   ├── ia_adapter.py           # Internet Archive — netlabels + 78rpm
│   │   ├── normalizer.py           # Raw payload → flat schema + content_type
│   │   └── deduplicator.py         # MD5 hash dedup
│   └── requirements.txt
│
├── frontend/                       # Deployed to gh-pages branch
│   ├── index.html                  # SPA entry, Tailwind CDN, warn intercept
│   ├── manifest.json               # PWA: start_url /music/, scope /music/
│   ├── service-worker.js           # Cache v2, shell + scroll/library assets
│   ├── about.html
│   ├── privacy.html
│   ├── terms.html
│   ├── licenses.html
│   ├── css/
│   │   └── app.css                 # Chips, eq-bars, now-playing, range input
│   ├── js/
│   │   ├── app.js                  # Router, keyboard shortcuts, nav highlight
│   │   ├── player.js               # Playback, shuffle, repeat, sleep timer
│   │   ├── queue.js                # Queue state + Queue.random()
│   │   ├── api.js                  # All fetch calls incl. artists + albums
│   │   ├── scroll.js               # InfiniteScroll class
│   │   ├── library.js              # getSaved/isSaved/toggleSaved localStorage
│   │   ├── i18n/
│   │   │   └── en.js
│   │   └── views/
│   │       ├── home.js             # Filter chips, infinite scroll, hearts
│   │       ├── search.js           # Search, artist→album drill-down, Play all
│   │       └── library.js          # Saved tracks view
│   └── icons/
│       ├── icon-192.png
│       └── icon-512.png
│
├── infra/
│   ├── dynamo_schema.json          # Table + all 7 GSI definitions
│   ├── aws-resources.md
│   ├── lambda-policy.json
│   └── lambda-trust-policy.json
│
├── scripts/
│   ├── backfill_content_type.py    # Classified 306 records, 0 errors
│   ├── gen_icons.py                # Generates solid green PNG icons
│   └── preview_collections.py     # Previews first page of IA collection
│
├── tests/
│   ├── test_ingest.py              # Wipes + re-ingests netlabels + 78rpm
│   └── test_link_checker.py
│
├── .gitignore                      # Excludes *.zip, *_out.json, __pycache__
├── about-index.md                  # Frontend changelog + pending items
├── project_architecture_technical_roadmap.md
└── serve.py
```

---

## 7. Pending Items (Prioritized)

### Next up — Jamendo ingestion
- Credentials already in Secrets Manager at `music/jamendo`
- Write `jamendo_adapter.py` implementing `BaseAdapter`
- Add `jamendo` to `IA_COLLECTIONS`-equivalent config in ingestion layer

### Medium priority
- Cover art fallback — deterministic gradient per `album_id` when `cover_art_url` is null
- License / attribution display — "i" button on track rows surfacing `attribution_text` + `license_type`
- Download button — `stream_url` with `download` attribute on tracks where `is_downloadable: true`
- Media Session API — Bluetooth / lock screen / car stereo hardware controls
- Continue where left off — 10s position write to localStorage + Resume prompt on open
- Offline queue caching — pre-fetch next 2–3 audio URLs via Cache API

### Lower priority
- `/tracks/{id}` single track endpoint
- `/stats` endpoint — total count, source breakdown, genre distribution
- Settings view (`settings.js`) — crossfade, playback speed, theme, cache management
- Crossfade — Web Audio API, configurable duration
- Playback speed — `playbackRate` control in player footer
- WAF + CORS hardening for production
- OpenAPI spec (`docs/openapi.yaml`)
- CI pipeline (pytest + ruff + eslint)

---

## 8. Key AWS Resources

| Resource | Value |
|---|---|
| Region | `us-east-1` |
| Account | `170377509849` |
| DynamoDB table | `music-tracks` |
| Lambda — search | `music-search` |
| Lambda — artists | `music-artists` |
| Lambda — albums | `music-albums` |
| Lambda role | `arn:aws:iam::170377509849:role/music-lambda-role` |
| API Gateway ID | `9jxmxtjybb` |
| API base URL | `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1` |
| Jamendo credentials | Secrets Manager `music/jamendo` |
| Frontend (live) | `https://shannon-goddard.github.io/music/` |
| GitHub repo | `https://github.com/Shannon-Goddard/music` |

---

## 9. Architectural Differentiators

- **Zero-storage meta-index** — 0 GB audio stored, $0 storage/egress costs, streams direct from source
- **Unified cross-platform catalog** — single flat schema normalizes Internet Archive, Jamendo, FMA into one index
- **Decoupled serverless stack** — GitHub Pages + Lambda + DynamoDB, operates within free-tier limits
- **Content-type classification** — `_detect_content_type()` separates music from podcasts/lectures/interviews at ingest
- **Targeted collection strategy** — quality over quantity: `netlabels` (modern CC) + `78rpm` (pre-1930s), zero noise
- **Research-grade dataset** — BPM, key, mood, AcoustID fingerprints, MusicBrainz IDs, DOI registration (planned)
- **Preservation monitoring** — dead link health system passively tracks open archive integrity over time
