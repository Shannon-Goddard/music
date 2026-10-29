# 🗺️ Architecture & Technical Roadmap: Infinite Meta-Index Music Platform

This document serves as the master engineering blueprint for building an uncapped, automated, and serverless music meta-indexer and streaming application. It is written for developers contributing to the project, researchers accessing the dataset, and engineers adapting the architecture for other use cases.

---

## Architecture Overview

```
[ Data Sources ]
 (Internet Archive, Jamendo, FMA, MusicBrainz)
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
[ GitHub Pages (Frontend) ] ──────────> PWA / SPA HTML5 Web Player (WCAG 2.1 AA)
       │
       ├──> Casual Listeners     (radio, queue, Bluetooth, Chromecast, AirPlay)
       ├──> Music Enthusiasts    (tag browse, similar tracks, waveform, deep links)
       ├──> Content Creators     (CC filter, download, copy attribution string)
       └──> Accessibility Users  (focus mode, keyboard nav, reduced motion)
```

---

## 1. Master Universal Database Schema (DynamoDB)

Every track record includes metadata, source tracing, acoustic fingerprinting, research-grade tags, and system health tracking.

```json
{
  "track_id": "TRK-IA-9823411",
  "title": "Starlight (Live)",
  "duration_sec": 243.5,
  "release_year": 2021,

  "artist": {
    "artist_id": "ART-00192",
    "name": "The Solar Collective",
    "musicbrainz_artist_id": "mbid-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "album": {
    "album_id": "ALB-88392",
    "title": "Live at the Beacon Theatre",
    "track_number": 4,
    "cover_art_url": "https://archive.org/download/solar2021/cover.jpg"
  },
  "genre": "Indie Rock",
  "tags": ["live", "indie", "guitar", "2021"],

  "acoustic": {
    "bpm": 118.4,
    "key": "A minor",
    "mood": "energetic",
    "acoustid_fingerprint": "AQADtMiybFIAAA...",
    "acoustid_id": "a8fa3e21-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },

  "media_stream": {
    "source_platform": "internet_archive",
    "stream_url": "https://archive.org/download/solar2021/track04.mp3",
    "source_url": "https://archive.org/details/solar2021_track04",
    "format": "mp3",
    "bitrate_kbps": 320,
    "audio_hash_md5": "e99a18c428cb38d5f260853678922e03"
  },

  "licensing": {
    "license_type": "CC-BY-NC-SA 4.0",
    "is_streamable": true,
    "is_downloadable": true,
    "attribution_text": "\"Starlight (Live)\" by The Solar Collective — CC-BY-NC-SA 4.0 — archive.org/details/solar2021_track04",
    "embed_url": "https://<platform>/embed/track/TRK-IA-9823411"
  },

  "research": {
    "play_count": 0,
    "dataset_version": "v1.0.0",
    "doi": "10.5281/zenodo.xxxxxxx"
  },

  "system_health": {
    "status": "active",
    "http_status_code": 200,
    "last_checked_at": "2026-10-29T06:44:00Z",
    "added_at": "2026-01-15T10:00:00Z",
    "last_updated_at": "2026-10-29T06:44:00Z"
  }
}
```

---

## 2. Technical Roadmap

### Phase 1: Modular Ingestion & Pipeline Setup

- **Step 1.1: Multi-Source Adapters**
  - Write Python adapters (`ia_adapter.py`, `jamendo_adapter.py`, `fma_adapter.py`) using pagination to pull large batches without API timeouts.
  - Each adapter implements a shared `BaseAdapter` interface: `fetch()`, `normalize()`, `paginate()`.
- **Step 1.2: Normalization & Deduplication**
  - Convert incoming payloads into the Master Universal Schema via `normalizer.py`.
  - Compute `audio_hash_md5` to skip existing tracks and prevent duplicate entries.
- **Step 1.3: Incremental State Storage**
  - Store a high-water mark timestamp (`last_ingested_at`) per source to fetch only new tracks since the last run.
- **Step 1.4: AcoustID Fingerprint Verification**
  - Run `acoustid_checker.py` on each ingested track to compute a Chromaprint fingerprint.
  - Submit to the AcoustID API to verify identity and cross-reference with MusicBrainz.
  - Tracks that fail fingerprint verification are flagged `pending_recheck` and excluded from the live index until resolved.

---

### Phase 2: Uncapped Database Design (AWS DynamoDB)

- **Step 2.1: Table & Index Setup**
  - **Partition Key (`PK`):** `track_id` (String)
  - **Global Secondary Indexes (GSIs):**
    - `ArtistIndex`: PK: `artist.artist_id` | SK: `album.title`
    - `AlbumIndex`: PK: `album.album_id` | SK: `album.track_number`
    - `GenreIndex`: PK: `genre` | SK: `system_health.added_at`
    - `HealthIndex`: PK: `system_health.status` | SK: `system_health.last_checked_at`
    - `TagIndex`: PK: `tags[*]` | SK: `system_health.added_at` (via DynamoDB list flattening)
    - `DatasetIndex`: PK: `research.dataset_version` | SK: `system_health.added_at`
    - `MoodIndex`: PK: `acoustic.mood` | SK: `acoustic.bpm`
- **Step 2.2: Scaling Considerations**
  - Enable **On-Demand Capacity Mode** to auto-scale past 1M into tens of millions of tracks.

---

### Phase 3: Automated Lifecycle Maintenance (Monthly Sync & Dead Link Removal)

- **Step 3.1: Monthly Content Ingestion Job**
  - Scheduled GitHub Action or AWS EventBridge trigger on the 1st of every month.
  - On failure: publish to an AWS SQS Dead Letter Queue (DLQ) for manual review. Alert via CloudWatch alarm.
- **Step 3.2: Automated Link Health Checker (Cron Job)**
  - Query `HealthIndex` where `status = "active"` sorted by `last_checked_at` ASC.
  - Send HTTP `HEAD` requests to evaluate `stream_url` health:
    - **HTTP 200 / 302:** Update `last_checked_at`, keep status `active`.
    - **HTTP 404 / 410 / 403:** Set status to `dead_link`. Frontend queries exclude `dead_link` tracks automatically.
  - **Retry strategy:** On timeout or 5xx, retry with exponential backoff (3 attempts: 5s, 30s, 120s) before marking `pending_recheck`.

---

### Phase 4: Serverless API Gateway & Frontend Player (GitHub Pages)

- **Step 4.1: API Gateway Endpoint Mapping**
  - `GET /tracks/search?q={query}` – Search across artists, titles, albums, and tags.
  - `GET /artist/{id}` – Load discography for artist view.
  - `GET /album/{id}` – Load tracklist sorted by `track_number`.
  - `GET /radio?genre={genre}` – Randomized selection filtered by `genre` and `status = "active"`.
  - `GET /tracks/{id}` – Single track detail with full schema.
  - `GET /tracks/filter?key={key}&bpm_min={n}&bpm_max={n}&mood={mood}&license={type}&is_downloadable={bool}` – Filtered browse for educators, creators, and app builders.
  - `GET /embed/{id}` – Embeddable player widget (iframe-safe, no auth required).
  - `GET /playlist/{id}/m3u` – Export a saved playlist as an M3U file.
  - `POST /session` – Save/restore queue state (authenticated via Cognito).
  - `GET /export?format=json|csv&genre={genre}&limit={n}` – Bulk dataset export for researchers (rate limited, public tier).
  - `GET /stats` – Total track count, source breakdown, genre distribution, link health summary, dataset version.
  - `GET /health-history?days={n}` – Time-series link health data for archivists and preservationists.
- **Step 4.2: API Security**
  - Enforce CORS policy: allow only the GitHub Pages origin in production.
  - Apply AWS WAF rate limiting: 100 requests/minute per IP on public endpoints.
  - `/session` endpoint requires a Cognito JWT — no anonymous queue persistence.
  - All Lambda functions validate input schema before touching DynamoDB.
- **Step 4.3: Frontend HTML5 Player**
  - SPA using HTML5, CSS (Tailwind), and vanilla JS.
  - Features: persistent playback footer, global queue, artist discography, album view, genre radio, tag-based browsing.
- **Step 4.4: Direct Source Attribution**
  - Display a "View Original Source" link pointing to `media_stream.source_url` on every track for transparency and license compliance.
  - Display license badge (e.g. CC-BY-NC-SA 4.0) inline on the track detail view.

---

### Phase 5: Cross-Device Playback (PWA + Stereo / Bluetooth Support)

- **Step 5.1: PWA Manifest & Installability**
  - Add `manifest.json` to the GitHub Pages root with app name, icons, `display: standalone`, and `theme_color`.
  - Register `service-worker.js` to cache the UI shell, track metadata, and queue state for offline resilience.
  - Result: Installable on Android, iOS (Add to Home Screen), and desktop Chrome/Edge.
- **Step 5.2: Media Session API (Bluetooth & Hardware Controls)**
  - Integrate the Media Session API into the persistent playback footer.
  - Populate `navigator.mediaSession.metadata` with `title`, `artist`, `album`, and `cover_art_url` on every track change.
  - Register handlers for `play`, `pause`, `nexttrack`, `previoustrack`, and `seekto`.
  - Result: Hardware button support on Bluetooth speakers/headphones, car stereos (Android Auto / Apple CarPlay), lock screens, and OS notification trays — no native app required.

  ```js
  navigator.mediaSession.metadata = new MediaMetadata({
    title: track.title,
    artist: track.artist.name,
    album: track.album.title,
    artwork: [{ src: track.album.cover_art_url, sizes: '512x512', type: 'image/jpeg' }]
  });
  navigator.mediaSession.setActionHandler('nexttrack', () => playNext());
  navigator.mediaSession.setActionHandler('previoustrack', () => playPrev());
  navigator.mediaSession.setActionHandler('seekto', (d) => seek(d.seekTime));
  ```

- **Step 5.3: Chromecast / Google TV (Cast SDK)**
  - Load the Cast Sender SDK, initialize a `CastContext` targeting the Default Media Receiver.
  - Pass `stream_url`, `title`, `artist`, and `cover_art_url` as a `MediaInfo` object on session start.
  - Display a `<google-cast-launcher>` button in the player footer.
  - Result: One-tap cast to Chromecast, Google TV, or Cast-enabled speakers (Sonos, JBL).
- **Step 5.4: AirPlay (Zero-Config)**
  - No additional code required. Safari exposes a native AirPlay button on any standard `<audio>` element.
  - Keep the player on a plain `<audio>` tag — do not wrap in a Web Audio pipeline.
  - Result: AirPlay to Apple TV, HomePod, and AirPlay 2 speakers works out of the box.
- **Step 5.5: Persistent Queue Sync**
  - Save queue and playback position to `localStorage` on every track change.
  - POST queue state to `/session` (Cognito-authenticated) for cross-device resume.

---

### Phase 6: Production Hardening

- **Step 6.1: Observability**
  - Enable AWS CloudWatch structured logging on all Lambda functions (JSON log format).
  - Create CloudWatch alarms for: Lambda error rate > 1%, DLQ message count > 0, API Gateway 5xx rate > 0.5%.
  - Add an SQS Dead Letter Queue for all async ingestion and health-check jobs — failed messages are retained for 14 days for manual replay.
  - Emit a `play_count` increment to DynamoDB on each `/tracks/{id}` stream event for usage analytics.
- **Step 6.2: Error Handling & Retry Strategy**
  - All adapters implement exponential backoff on rate-limit (HTTP 429) and server error (5xx) responses: 3 retries at 5s, 30s, 120s.
  - Ingestion jobs write a `checkpoint.json` per source after each paginated batch so a mid-run failure resumes from the last successful page, not from scratch.
  - Lambda functions return structured error responses: `{ "error": "NOT_FOUND", "message": "...", "request_id": "..." }`.
- **Step 6.3: API Security Hardening**
  - Attach AWS WAF to API Gateway with managed rule sets (SQLi, XSS, rate limiting).
  - Enforce HTTPS-only. All API responses include `Strict-Transport-Security` and `X-Content-Type-Options` headers.
  - Rotate any API keys (Jamendo, AcoustID) via AWS Secrets Manager — never hardcoded or committed.
- **Step 6.4: AcoustID Pipeline (Full Implementation)**
  - `acoustid_checker.py` uses `pyacoustid` + `fpcalc` (Chromaprint CLI) to generate fingerprints from stream URLs.
  - Fingerprint is stored as `acoustic.acoustid_fingerprint` and the resolved ID as `acoustic.acoustid_id`.
  - Tracks with a confirmed AcoustID match have `acoustic.acoustid_id` populated and are considered verified.
  - Tracks that cannot be fingerprinted (e.g. stream unreachable at ingest time) are flagged `pending_recheck` and retried on the next health cycle.

---

### Phase 7: Developer Experience

- **Step 7.1: OpenAPI Specification**
  - Maintain `docs/openapi.yaml` as the single source of truth for all API endpoints.
  - Auto-generate interactive docs via Swagger UI or Redoc, hosted at `/docs` on the GitHub Pages site.
  - Every endpoint documents: request params, response schema, error codes, and example payloads.
- **Step 7.2: Local Development Setup**
  - Document a `make dev` or `docker-compose up` workflow in `CONTRIBUTING.md` that spins up:
    - DynamoDB Local (via Docker) seeded with 100 sample tracks.
    - A mock API Gateway using AWS SAM CLI (`sam local start-api`).
    - The frontend dev server with hot reload.
  - All environment variables documented in `.env.example` — no undocumented config.
- **Step 7.3: Contribution Guide**
  - `docs/CONTRIBUTING.md` covers: branching strategy, adapter interface contract, schema change process, and how to add a new data source.
  - Adding a new source = implement `BaseAdapter`, add a workflow YAML, add a GSI if needed. Document this as a 4-step process.
- **Step 7.4: Code Quality**
  - Python: `ruff` for linting, `black` for formatting, `pytest` for unit tests. CI enforced via GitHub Actions.
  - JavaScript: `eslint` + `prettier`. No build step required — vanilla JS keeps the frontend forkable without a Node toolchain.
  - Test coverage targets: normalization layer 90%+, Lambda handlers 80%+.

---

### Phase 8: User Experience

- **Step 8.1: Accessibility (WCAG 2.1 AA)**
  - All interactive elements keyboard-navigable. Focus indicators visible.
  - Player controls have `aria-label` attributes. Track lists use semantic `<ul>/<li>` with `role="listitem"`.
  - Color contrast ratio ≥ 4.5:1 across all text. Test with axe-core in CI.
- **Step 8.2: Visual Polish**
  - Skeleton loaders on all async data fetches — no blank states.
  - Waveform scrubber on the player footer using the Web Audio API `AnalyserNode` (visualizer only, not for routing — preserves AirPlay compatibility).
  - Dark / light theme toggle, persisted to `localStorage`. System preference respected via `prefers-color-scheme` on first load.
  - Smooth page transitions between views (CSS `view-transition` API).
- **Step 8.3: Discoverability**
  - Tag-based browsing: clicking any tag on a track opens a filtered view of all tracks sharing that tag.
  - "Similar tracks" section on track detail view — powered by matching `genre` + `bpm` range + `key` from the schema.
  - Shareable URLs for every view: `/artist/{id}`, `/album/{id}`, `/radio/{genre}`, `/track/{id}` — deep-linkable and bookmarkable.
- **Step 8.4: Internationalisation (i18n) Ready**
  - All UI strings extracted to a `js/i18n/en.js` locale file from day one.
  - No hardcoded UI copy in component logic — makes adding new languages a single file addition.

---

### Phase 9: Research & Data Access

- **Step 9.1: Public Read-Only API Tier**
  - Unauthenticated public endpoints with generous rate limits (300 req/min) for research use:
    - `GET /export?format=json|csv&genre={genre}&year={year}&license={type}&limit={n}&offset={n}`
    - `GET /stats` — returns total track count, source breakdown, genre distribution, and dataset version.
    - `GET /tracks/{id}` — full schema including acoustic fields.
  - Paginated exports support up to 10,000 records per request.
- **Step 9.2: DOI Registration & Dataset Versioning**
  - Register the dataset with [Zenodo](https://zenodo.org) to obtain a citable DOI (e.g. `10.5281/zenodo.xxxxxxx`).
  - Cut a versioned dataset snapshot (JSON + CSV) on the 1st of each quarter, uploaded to Zenodo automatically via GitHub Actions.
  - Each snapshot is tagged in the repo (`dataset-v1.0.0`, `dataset-v1.1.0`) and linked from the README.
  - `research.dataset_version` in the schema tracks which snapshot a record was first included in.
- **Step 9.3: Citation Format**
  - Provide a `CITATION.cff` file in the repo root for automatic citation support in GitHub and Zenodo.
  - README includes a ready-to-copy BibTeX block:

  ```bibtex
  @dataset{infinite_meta_index_2026,
    title     = {Infinite Meta-Index Music Dataset},
    author    = {<author>},
    year      = {2026},
    publisher = {Zenodo},
    doi       = {10.5281/zenodo.xxxxxxx},
    url       = {https://doi.org/10.5281/zenodo.xxxxxxx}
  }
  ```

- **Step 9.4: MusicBrainz Cross-Reference**
  - `artist.musicbrainz_artist_id` in the schema links every artist to the MusicBrainz open knowledge graph.
  - Researchers can join this dataset with MusicBrainz, Wikidata, and Last.fm datasets using the MBID as a shared key.
- **Step 9.5: Acoustic Feature Dataset**
  - `acoustic.bpm`, `acoustic.key`, and `acoustic.acoustid_fingerprint` make this dataset usable for:
    - Music Information Retrieval (MIR) research
    - Mood / tempo classification model training
    - Playlist generation algorithm benchmarking
  - Document these fields explicitly in the Zenodo dataset description and README.

---

### Phase 10: Extended Use Cases & API Tiers

- **Step 10.1: Music Educators & Students**
  - The `acoustic.bpm`, `acoustic.key`, `acoustic.mood`, and `tags[]` fields make this dataset directly usable in music theory, ear training, and genre analysis curricula.
  - The `/tracks/filter` endpoint supports classroom queries like "all tracks in A minor between 90–110 BPM" without any custom tooling.
  - Document an "Educator Quick Start" section in the README with 5 example queries covering common music education use cases.
  - Future: a dedicated "Classroom" view in the frontend that presents tracks with their key, BPM, and mood displayed prominently alongside the player.

- **Step 10.2: Indie Developers & App Builders (API Key Tier)**
  - Create a developer API tier using AWS API Gateway Usage Plans:
    - **Free tier:** 300 req/day, no key required, read-only.
    - **Developer tier:** 10,000 req/day, API key required (self-serve via a `/register` form), read-only.
    - **Partner tier:** Unlimited, negotiated, includes `/export` and `/health-history`.
  - Self-serve API key registration: a simple form on the GitHub Pages site POSTs to a Lambda that creates a usage plan key via the AWS SDK and emails it to the requester.
  - Use cases this unlocks: meditation apps, game soundtracks, fitness apps, podcast background music tools, browser extensions.
  - Document the API key flow and tier limits in `docs/openapi.yaml` and the README.

- **Step 10.3: Podcast & Content Creators (Creator Tools View)**
  - Add a "Creator Tools" view to the frontend SPA:
    - Filter by `is_downloadable: true` and license type (e.g. CC-BY only for maximum reuse freedom).
    - Filter by `acoustic.mood`, `acoustic.bpm`, and `genre` to find music that fits a scene or segment.
    - One-click copy of the pre-formatted `licensing.attribution_text` string — ready to paste into show notes or video descriptions.
    - Download button wired to `media_stream.stream_url` for tracks where `is_downloadable: true`.
  - No backend changes required — this is a frontend view consuming existing API endpoints.

- **Step 10.4: Archivists & Digital Preservationists**
  - The `system_health` lifecycle already passively tracks when Internet Archive and other source content goes dark.
  - Surface this data explicitly:
    - `GET /health-history?days={n}` — returns a time-series of `dead_link` counts per source platform, useful for preservation trend analysis.
    - `GET /stats` — includes a `link_health_summary` block: total active, dead, and pending tracks per source.
    - A public "Health Dashboard" page in the frontend showing live link health stats and a chart of dead link trends over time.
  - This makes the platform a secondary integrity monitor for open audio archives — a genuine contribution to the digital preservation community.

- **Step 10.5: Playlist Curators & Music Bloggers**
  - Saved playlists: authenticated users (Cognito) can create, name, and share playlists.
  - `GET /playlist/{id}` — returns a named playlist with full track metadata.
  - `GET /playlist/{id}/m3u` — exports the playlist as an M3U file, compatible with VLC, Winamp, and any media player.
  - Embeddable player widget: `GET /embed/{id}` returns an iframe-safe HTML player for a single track or playlist — embeddable in blog posts, Notion pages, or any website without CORS issues.
  - Shareable playlist URLs are deep-linkable and bookmarkable via the SPA router.

- **Step 10.6: Accessibility-First Users (Focus Mode)**
  - Beyond WCAG 2.1 AA compliance, implement a dedicated "Focus Mode" toggle in the UI:
    - Strips all visual chrome except the player footer, track title, artist, and next/prev controls.
    - Increases font size to 1.25rem minimum.
    - Removes animations and transitions (`prefers-reduced-motion` respected globally).
    - High-contrast mode toggle independent of the OS setting.
  - Keyboard-only navigation mode: Tab order is logical and announced. All modals trap focus correctly. Escape always closes.
  - Screen reader testing target: NVDA + Firefox and VoiceOver + Safari before each release.
  - Document accessibility testing procedure in `docs/CONTRIBUTING.md`.

---

### Phase 11: Listener-First PWA Features (The iPod Replacement)

The primary user is someone who wants to open an app, find music they love, and listen — on their phone, in their car, on their speaker, with zero friction. Every decision in this phase is made with that person in mind.

- **Step 11.1: Offline Playback Queue**
  - The service worker caches not just the UI shell but the audio URLs of the current queue.
  - On queue change, pre-fetch and cache the next 2–3 tracks in the background using the Cache API.
  - If a stream URL is unreachable offline, fall back gracefully with a "Unavailable offline" indicator — never a silent failure or broken state.
  - Result: Load your queue on WiFi, get on the subway, music keeps playing.

- **Step 11.2: Continue Where You Left Off**
  - On every track change and every 10 seconds of playback, write `{ track_id, position_sec, queue }` to `localStorage`.
  - On app open, read this state and restore the player to the exact track and position before rendering anything else.
  - Show a "Resume" prompt rather than auto-playing — respects the user's intent.
  - This is the single highest-impact UX feature for a daily-use music player.

- **Step 11.3: My Library (Saved Music)**
  - Authenticated users (Cognito) can save artists, albums, and tracks to a personal library.
  - New endpoints:
    - `GET /library` — returns saved artists, albums, and tracks for the authenticated user.
    - `POST /library` — add an item `{ type: "artist"|"album"|"track", id }` to the library.
    - `DELETE /library/{id}` — remove an item.
  - Library is synced server-side so it persists across devices — phone, desktop, smart TV.
  - Heart / bookmark icon on every track, artist, and album card. Filled = saved. One tap to toggle.

- **Step 11.4: Recently Played**
  - Maintain a local `recently_played[]` array in `localStorage` (last 50 tracks, no auth required).
  - Display as a "Recently Played" row on the home view — the first thing a returning user sees.
  - Optionally sync to server via `/session` for cross-device recently played history when authenticated.

- **Step 11.5: Sleep Timer**
  - A timer control in the player footer (15 / 30 / 45 / 60 min or custom).
  - On expiry: fade audio out over 10 seconds, pause, clear the timer.
  - Timer state persisted to `localStorage` so a page refresh doesn't reset it.
  - Displayed as a countdown badge on the player footer when active.

- **Step 11.6: Crossfade**
  - Implement crossfade between tracks using the Web Audio API:
    - Create two `AudioBufferSourceNode` instances.
    - On track end approach (last 5 seconds), begin fading out current track while fading in the next.
    - Crossfade duration configurable in settings (2s / 5s / 10s).
  - Note: crossfade uses Web Audio routing. Ensure the AirPlay `<audio>` element remains the primary output node so AirPlay compatibility is preserved.

- **Step 11.7: Playback Speed Control**
  - Expose `audioElement.playbackRate` as a UI control: 0.5x, 0.75x, 1x, 1.25x, 1.5x, 2x.
  - Persisted to `localStorage` — if you prefer 1.25x, it stays that way across sessions.
  - Displayed as a badge on the player footer when not at 1x so the user always knows.

- **Step 11.8: Home Screen & Discovery**
  - The home view is the first thing a user sees on open. It should feel like a music app, not a search box:
    - **Continue Listening** — restored last session track (Step 11.2).
    - **Recently Played** — last 10 tracks (Step 11.4).
    - **My Library** — quick-access row for saved artists/albums (Step 11.3).
    - **Genre Radio** — one-tap genre cards that launch the radio endpoint.
    - **New Additions** — tracks sorted by `system_health.added_at` DESC, showing what's fresh in the index.
    - **Mood Mix** — filter by `acoustic.mood` for contextual listening (energetic, calm, melancholic, etc.).
  - All rows are horizontally scrollable cards — familiar mobile music app pattern.

- **Step 11.9: Settings & Personalization**
  - A `/settings` view with:
    - Crossfade duration slider.
    - Playback speed default.
    - Sleep timer default.
    - Dark / light / system theme toggle.
    - Focus Mode toggle (Phase 10.6).
    - Cache management: "Clear offline cache" button with current cache size displayed.
    - Account: sign in / sign out (Cognito), linked to library and cross-device queue sync.
  - All settings persisted to `localStorage`. No account required for any setting except library sync.

- **Step 11.10: Folder Structure Additions**
  - New frontend views: `home.js`, `library.js`, `settings.js`.
  - New backend Lambdas: `library.py` (`GET/POST/DELETE /library`).
  - New test file: `test_library.py`.

---

```
music/
├── .github/
│   └── workflows/
│       ├── ingest.yml              # Monthly ingestion cron job
│       ├── health-check.yml        # Dead link checker cron job
│       ├── dataset-export.yml      # Quarterly Zenodo snapshot upload
│       └── ci.yml                  # Lint, test, OpenAPI validation
│
├── backend/
│   ├── ingestion/
│   │   ├── base_adapter.py         # Shared adapter interface (fetch, normalize, paginate)
│   │   ├── ia_adapter.py           # Internet Archive adapter
│   │   ├── jamendo_adapter.py      # Jamendo adapter
│   │   ├── fma_adapter.py          # FMA adapter
│   │   ├── normalizer.py           # Converts raw payloads → Master Schema
│   │   └── deduplicator.py         # MD5 hash check, skips existing tracks
│   │
│   ├── fingerprint/
│   │   └── acoustid_checker.py     # Chromaprint fingerprinting + AcoustID API verification
│   │
│   ├── health/
│   │   ├── link_checker.py         # HEAD request checker, exponential backoff, DLQ publish
│   │   └── health_history.py       # Writes time-series health snapshots for /health-history
│   │
│   ├── api/
│   │   ├── search.py               # Lambda: GET /tracks/search
│   │   ├── filter.py               # Lambda: GET /tracks/filter (BPM, key, mood, license)
│   │   ├── artist.py               # Lambda: GET /artist/{id}
│   │   ├── album.py                # Lambda: GET /album/{id}
│   │   ├── radio.py                # Lambda: GET /radio?genre=
│   │   ├── track.py                # Lambda: GET /tracks/{id}
│   │   ├── embed.py                # Lambda: GET /embed/{id} (iframe-safe widget)
│   │   ├── playlist.py             # Lambda: GET|POST /playlist + GET /playlist/{id}/m3u
│   │   ├── library.py              # Lambda: GET|POST|DELETE /library (Cognito-authenticated)
│   │   ├── export.py               # Lambda: GET /export (researcher bulk export)
│   │   ├── stats.py                # Lambda: GET /stats
│   │   ├── health_history.py       # Lambda: GET /health-history
│   │   ├── register.py             # Lambda: POST /register (self-serve API key)
│   │   └── session.py              # Lambda: POST /session (Cognito-authenticated)
│   │
│   ├── db/
│   │   └── dynamo_client.py        # Shared DynamoDB client + table config
│   │
│   └── requirements.txt
│
├── frontend/                       # GitHub Pages root
│   ├── index.html                  # SPA entry point
│   ├── manifest.json               # PWA manifest
│   ├── service-worker.js           # Caching + offline shell
│   │
│   ├── css/
│   │   └── app.css                 # Tailwind build output
│   │
│   ├── js/
│   │   ├── app.js                  # SPA router + bootstrap
│   │   ├── player.js               # Playback engine, Media Session API, Cast SDK, waveform
│   │   ├── queue.js                # Queue state + localStorage + /session sync
│   │   ├── api.js                  # Fetch wrapper for all API calls (JSDoc typed)
│   │   ├── i18n/
│   │   │   └── en.js               # All UI strings (i18n-ready)
│   │   └── views/
│   │       ├── search.js           # Search results view
│   │       ├── artist.js           # Artist discography view
│   │       ├── album.js            # Album tracklist view
│   │       ├── radio.js            # Genre radio view
│   │       ├── track.js            # Track detail + similar tracks
│   │       ├── tags.js             # Tag-filtered browse view
│   │       ├── creator.js          # Creator Tools: CC filter, download, attribution copy
│   │       ├── playlist.js         # Playlist view + M3U export
│   │       ├── health.js           # Archivist health dashboard + dead link trend chart
│   │       ├── embed.js            # Embeddable player widget (iframe target)
│   │       ├── home.js             # Home screen: resume, recently played, genre cards, mood mix
│   │       ├── library.js          # My Library: saved artists, albums, tracks
│   │       └── settings.js         # Settings: crossfade, speed, sleep timer, theme, cache, account
│   │
│   └── icons/                      # PWA icons (192x192, 512x512)
│
├── infra/
│   └── dynamo_schema.json          # DynamoDB table + GSI definitions (IaC)
│
├── tests/
│   ├── test_normalizer.py          # Unit tests: schema normalization
│   ├── test_deduplicator.py        # Unit tests: MD5 dedup logic
│   ├── test_link_checker.py        # Unit tests: retry/backoff behavior
│   ├── test_lambdas.py             # Unit tests: Lambda handlers (mocked DynamoDB)
│   └── test_library.py             # Unit tests: library GET/POST/DELETE handlers
│
├── docs/
│   ├── openapi.yaml                # OpenAPI 3.0 spec (source of truth for all endpoints)
│   ├── CONTRIBUTING.md             # Dev setup, adapter interface, schema change process
│   ├── ACCESSIBILITY.md            # WCAG 2.1 AA testing procedure, screen reader targets
│   └── project_architecture_technical_roadmap.md
│
├── .env.example                    # All required environment variables documented
├── CITATION.cff                    # Machine-readable citation file (GitHub + Zenodo)
└── README.md
```

---

## 4. README Reference: Architectural Perspective & Differentiation

> 📋 **Note:** This section is staged for the project README. Copy into `README.md` at project completion.

### How This Project Compares to Existing Audio Platforms

Developers familiar with self-hosted or open-source streaming solutions (e.g., Navidrome, custom Jamendo/FMA wrappers, or traditional media servers) may notice both similarities and meaningful differences.

#### Similarities to Existing Ecosystems

- **Metadata-Driven Indexing:** Like Navidrome or Plex, this platform relies on standard metadata schemas, audio feature tags, and structured relational queries for play queue management.
- **Open Data Utilization:** Built on open APIs and datasets from the Internet Archive, Free Music Archive, Jamendo, and MusicBrainz.

#### Key Differentiators & Innovation

- **Zero-Hosting Meta-Index Architecture:** Traditional media servers require hosting local audio binaries or cloud buckets. This project functions purely as a remote meta-index aggregator — 0 GB of physical audio stored, resulting in $0 storage and egress costs.
- **Unified Cross-Platform Catalog:** The Universal Normalization Engine merges distinct source schemas into a single cohesive library rather than locking into a single API.
- **Decoupled Serverless Infrastructure:** GitHub Pages + AWS Lambda/API Gateway + DynamoDB creates a resilient, auto-scaling platform that operates within free-tier limits without dedicated server maintenance.
- **Pre-Gatekeeper Licensing & Hash Verification:** Unusable or copyrighted material is rejected or flagged prior to database storage using MD5 hashes and AcoustID fingerprints (Chromaprint), protecting infrastructure integrity automatically.
- **Research-Grade Dataset:** BPM, key, mood, AcoustID fingerprints, MusicBrainz IDs, and DOI registration make this the only open streaming platform that doubles as a citable academic dataset.
- **Multi-Audience API Design:** A single platform purpose-built for casual listeners, content creators, educators, archivists, indie developers, and researchers — each with dedicated endpoints, views, and documentation rather than an afterthought API.
- **Preservation Monitoring:** The dead link health system passively monitors the integrity of open audio archives (Internet Archive, FMA, Jamendo) and surfaces degradation trends publicly via the health dashboard — a genuine contribution to the digital preservation community.

---

## 5. Next Steps & Implementation Priority

1. **Database Provisioning:** Deploy DynamoDB schema with all GSIs including `TagIndex`, `DatasetIndex`, and `MoodIndex`.
2. **Core Python Ingestor:** Write `ia_adapter.py` implementing `BaseAdapter` against the Internet Archive Metadata API.
3. **AcoustID Pipeline:** Implement `acoustid_checker.py` with Chromaprint + AcoustID API integration.
4. **Health Checker Script:** Write `link_checker.py` with exponential backoff, DLQ publishing, and `health_history.py` time-series writer.
5. **API Gateway + Lambdas:** Deploy all endpoints with WAF, CORS, input validation, and usage plan tiers.
6. **PWA Manifest + Service Worker:** Add `manifest.json` and `service-worker.js` to the frontend root.
7. **Media Session API:** Integrate into the playback footer for Bluetooth and hardware control support.
8. **Cast SDK:** Add Chromecast support with a Cast button in the player UI.
9. **Creator Tools View:** Build `creator.js` view with CC filter, download button, and attribution copy.
10. **Health Dashboard:** Build `health.js` view with live stats and dead link trend chart.
11. **Embed Widget:** Implement `embed.py` Lambda and `embed.js` iframe-safe player.
12. **Playlist & M3U:** Implement `playlist.py` Lambda and `playlist.js` frontend view.
13. **API Key Self-Serve:** Implement `register.py` Lambda and usage plan tier config in API Gateway.
14. **OpenAPI Spec:** Write `docs/openapi.yaml` and host interactive docs at `/docs`.
15. **Zenodo Registration:** Register dataset, obtain DOI, add `CITATION.cff` and BibTeX block to README.
16. **Accessibility Audit:** Run axe-core + NVDA/VoiceOver testing, resolve all WCAG 2.1 AA violations, document in `ACCESSIBILITY.md`.
17. **CI Pipeline:** Wire `ci.yml` to run `pytest`, `ruff`, `eslint`, and OpenAPI validation on every PR.
18. **Home Screen:** Build `home.js` with Continue Listening, Recently Played, Genre Radio cards, and Mood Mix rows.
19. **My Library:** Implement `library.py` Lambda (`GET/POST/DELETE /library`) and `library.js` frontend view with heart/bookmark toggle on all cards.
20. **Offline Queue Caching:** Extend `service-worker.js` to pre-fetch and cache the next 2–3 audio URLs in the active queue.
21. **Continue Where You Left Off:** Implement 10-second position write to `localStorage` and Resume prompt on app open.
22. **Sleep Timer:** Add timer control to player footer with fade-out on expiry.
23. **Crossfade:** Implement Web Audio API crossfade between tracks with configurable duration.
24. **Playback Speed:** Expose `playbackRate` control in player footer and settings.
25. **Settings View:** Build `settings.js` covering all personalization options, cache management, and account controls.
