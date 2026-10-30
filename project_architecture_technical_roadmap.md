# Architecture & Technical Roadmap: Infinite Meta-Index Music Platform

This document is the master engineering blueprint for the platform. It reflects the current live state of the project and the forward roadmap.

---

## Current Live State

| Layer | Status | Detail |
|---|---|---|
| DynamoDB table | ✅ Live | `music-tracks`, `us-east-1`, ~23,274 records |
| GSIs | ✅ All 7 ACTIVE | See Section 2 |
| Ingestion — Internet Archive | ✅ Done | `netlabels` (4,734) + `78rpm` (4,884) = 9,618 |
| Ingestion — Jamendo | ✅ Done | 46 genre tags swept, ~13,656 CC tracks |
| Ingestion — ccMixter | ❌ Removed | 19,508 ingested, wiped — ccMixter content server 403s all cross-origin requests, unplayable |
| `content_type` classification | ✅ Done | All records classified at ingest |
| API — `/tracks/search` | ✅ Live | `q=`, `genre=`, `type=`, `offset=`, `total` in response |
| API — `/artists/search` | ✅ Live | `q=` → `{ artist_id, artist_name, track_count }` |
| API — `/albums/search` | ✅ Live | `artist_id=` (GSI) or `q=` (scan) → albums with track counts |
| Lambda memory | ✅ 1024MB | All 3 Lambdas — required for full-scan ops on ~23k records |
| Frontend PWA | ✅ Live | `https://shannon-goddard.github.io/music/` |
| Icons | ✅ Updated | `icon.png` → `icon-192.png` + `icon-512.png`, `logo.png` → `logo-180.png` apple-touch-icon |
| Service worker | ✅ Fixed | Cache `v3`, 206 Partial Content responses no longer attempted to cache |

**API base URL:** `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1`

---

## Architecture Overview

```
[ Data Sources ]
  Internet Archive ✅  Jamendo ✅  Internet Archive (more collections) 🔜  MusicBrainz (enrichment) 🔜
       │
       ▼
[ Ingestion & Normalization Layer ]
       │
       ▼
[ AWS DynamoDB ] ─────────────────────> Meta-Index (~23k streamable CC tracks)
       │
       ▼
[ AWS API Gateway + Lambda ] ─────────> Serverless REST API
       │
       ▼
[ GitHub Pages (Frontend) ] ──────────> PWA / SPA HTML5 Web Player
       │
       ├──> Casual Listeners     (radio, queue, Bluetooth, sleep timer)
       ├──> Music Enthusiasts    (tag browse, infinite scroll, library, deep links)
       └──> Content Creators     (CC filter, download, copy attribution string)
```

---

## 1. Database Schema (DynamoDB — Flat, Live)

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

Future fields (not yet populated): `bpm`, `mood`, `track_number`, `cover_art_url`, `acoustid_fingerprint`, `musicbrainz_artist_id`.

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

- Multi-source adapters — `ia_adapter.py`, `jamendo_adapter.py` live
- Normalization & deduplication — `normalizer.py` + `deduplicator.py` live
- `content_type` classification — `_detect_content_type()` in `ia_adapter.py`
- `ALLOWED_PLATFORMS` in `normalizer.py` — gating for source quality control

---

### Phase 2: Database Design ✅ Complete

- Flat DynamoDB schema deployed (see Section 1)
- All 7 GSIs ACTIVE (see Section 2)
- On-demand capacity mode enabled

---

### Phase 3: Automated Lifecycle Maintenance 🔜 Pending

- **3.1** Monthly ingestion cron — GitHub Actions EventBridge trigger
- **3.2** Dead link health checker — `link_checker.py` exists, needs scheduling
- **3.3** Retry strategy — exponential backoff, `pending_recheck` flag on timeout

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
| GET | `/radio?genre=` | Randomized active tracks by genre |
| GET | `/stats` | Total count, source breakdown, genre distribution |

---

### Phase 5: PWA & Cross-Device Playback ✅ Partially Complete

- **5.1** PWA manifest + service worker — ✅ live, cache `v3`, 206 fix applied
- **5.2** Icons — ✅ real PNG icons, apple-touch-icon wired for home screen saves
- **5.3** Media Session API — ✅ live (Bluetooth / lock screen / car stereo controls)
- **5.4** AirPlay — ✅ zero-config via `<audio>` element
- **5.5** Persistent queue — localStorage done, cross-device sync not planned

---

### Phase 6: Production Hardening 🔜 Pending

- **6.1** CloudWatch alarms — Lambda error rate, 5xx rate
- **6.2** WAF rate limiting — 100 req/min per IP
- **6.3** CORS locked to GitHub Pages origin in production (currently open)

---

### Phase 7: Listener-First PWA Features ✅ Mostly Complete

| Feature | Status | Notes |
|---|---|---|
| Sleep timer | ✅ Live | 15/30/45/60/off, 10s fade-out |
| Shuffle | ✅ Live | `Queue.random()` |
| Repeat | ✅ Live | Restarts on `ended` |
| Recently played | ✅ Live | `music_recent` localStorage, capped at 20 |
| My Library (local) | ✅ Live | `music_library` localStorage, heart toggle |
| Library view | ✅ Live | `views/library.js`, Play all, empty state |
| Home view | ✅ Live | Filter chips, infinite scroll, now-playing indicator |
| Infinite scroll | ✅ Live | `scroll.js`, `IntersectionObserver` |
| Keyboard shortcuts | ✅ Live | Space, ←/→, N, P |
| Media Session API | ✅ Live | Bluetooth / lock screen / car stereo |
| Offline queue caching | 🔜 Pending | Pre-fetch next 2–3 tracks via Cache API |
| Continue where left off | 🔜 Pending | 10s position write + Resume prompt |
| Crossfade | 🔜 Pending | Web Audio API, configurable duration |
| Playback speed | 🔜 Pending | `playbackRate` control |
| Settings view | 🔜 Pending | Crossfade, speed, cache management |

---

## 4. Frontend — What's Built (Live on gh-pages)

### Visual Design
- Dark theme: `#111113` surface, `#1c1c1f` card, `#242428` raised
- Brand accent: `#04AA6D` — header wordmark, active chips, eq bars, heart icons
- Tailwind CDN 3.4.1 with custom color tokens (`surface`, `card`, `raised`, `accent`)

### Layout
- Fixed header: waveform wordmark + centered search + desktop nav
- Fixed player footer: desktop = single row, mobile = stacked
- Mobile bottom nav: Home / Search / Library
- Hamburger drawer (mobile): slides from right

### Player (`player.js`)
- Shuffle, repeat, sleep timer (15/30/45/60/off with 10s fade)
- Media Session API — Bluetooth / lock screen / hardware controls
- `trackchange` custom event on every track start
- Recently played written to `music_recent` localStorage on every `play()`
- Audio error → skip to next (no silent failures)

### Service Worker (`service-worker.js`)
- Cache `v3` — shell assets cached on install
- 206 Partial Content responses skipped (audio range requests not cached)
- API calls always network-only
- `PRECACHE_AUDIO` message handler for pre-fetching next tracks

### Icons
- `icon-192.png` — 192×192, browser favicon + PWA installer
- `icon-512.png` — 512×512, PWA splash
- `logo-180.png` — 180×180, `apple-touch-icon` for iOS/Android home screen saves

### Views
- `views/home.js` — filter chips (type + genre + mood), infinite scroll, hearts, now-playing
- `views/search.js` — infinite scroll, artist→album drill-down, Play all, hearts
- `views/library.js` — saved tracks, Play all, heart removes, empty state

### Legal Pages
- `about.html`, `privacy.html`, `terms.html`, `licenses.html`

---

## 5. Ingestion Sources

| Source | Status | Records | Notes |
|---|---|---|---|
| Internet Archive — netlabels | ✅ Done | 4,734 | Modern CC netlabel releases |
| Internet Archive — 78rpm | ✅ Done | 4,884 | Pre-1930s jazz/blues |
| Jamendo | ✅ Done | ~13,656 | 46 genre tags, all CC-licensed |
| ccMixter | ❌ Removed | 0 | Content server 403s cross-origin — unplayable, poor UX |
| Internet Archive (more collections) | 🔜 Next | — | Additional IA collections TBD |
| MusicBrainz | 🔜 Planned | — | Metadata enrichment only, not a track source |
| Free Music Archive (FMA) | ❌ Dead end | 0 | API fully dead (404), hotlinking prohibited |

**Total live records:** ~23,274 — all CC-licensed, all streamable

### Source Vetting Criteria
A source is only ingested if:
1. Files are directly streamable cross-origin (CORS headers present)
2. CC license is confirmed per-track
3. No hotlinking or scraping prohibition

ccMixter and FMA both failed criterion 1 and are permanently excluded.

---

## 6. Known Issues

| Issue | Status | Notes |
|---|---|---|
| Service worker 206 error | ✅ Fixed | Cache `v3` skips 206 responses |
| ccMixter CORS 403 | ✅ Resolved | All ccMixter records wiped from DB |
| Lambda total count cache | ⚠️ Known | `total` field caches for ~5min after large DB changes |
| Cover art missing on most tracks | ⚠️ Known | `cover_art_url` null for IA + Jamendo majority — placeholder shown |

---

## 7. Folder Structure (Current)

```
music/
├── backend/
│   ├── api/
│   │   ├── search.py               # Lambda: GET /tracks/search
│   │   ├── artists.py              # Lambda: GET /artists/search?q=
│   │   └── albums.py               # Lambda: GET /albums/search
│   ├── db/
│   │   └── dynamo_client.py
│   ├── health/
│   │   └── link_checker.py
│   ├── ingestion/
│   │   ├── base_adapter.py
│   │   ├── ia_adapter.py           # Internet Archive
│   │   ├── jamendo_adapter.py      # Jamendo — 46 tags, ~13,656 tracks
│   │   ├── ccmixter_adapter.py     # ccMixter — kept for reference, not used
│   │   ├── normalizer.py           # ALLOWED_PLATFORMS gating
│   │   └── deduplicator.py
│   └── requirements.txt
│
├── frontend/                       # Deployed to gh-pages branch
│   ├── index.html
│   ├── manifest.json               # PWA: start_url /music/, 3 icon sizes
│   ├── service-worker.js           # Cache v3, 206 fix
│   ├── about.html
│   ├── privacy.html
│   ├── terms.html
│   ├── licenses.html
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   ├── app.js
│   │   ├── player.js               # Media Session API, sleep timer, shuffle, repeat
│   │   ├── queue.js
│   │   ├── api.js
│   │   ├── scroll.js
│   │   ├── library.js
│   │   ├── i18n/
│   │   │   └── en.js
│   │   └── views/
│   │       ├── home.js
│   │       ├── search.js
│   │       └── library.js
│   └── icons/
│       ├── icon.png                # Source image (221×221)
│       ├── icon-192.png            # PWA + favicon
│       ├── icon-512.png            # PWA splash
│       ├── logo.png                # Source image (224×224)
│       └── logo-180.png            # apple-touch-icon
│
├── infra/
│   ├── dynamo_schema.json
│   ├── aws-resources.md
│   ├── lambda-policy.json
│   └── lambda-trust-policy.json
│
├── scripts/
│   ├── backfill_content_type.py
│   ├── probe_jamendo_cc_total.py   # Confirmed 46 productive tags
│   └── preview_collections.py
│
├── tests/
│   ├── test_ingest.py              # IA netlabels + 78rpm
│   ├── test_ingest_jamendo.py      # Jamendo 46-tag sweep
│   ├── test_ingest_ccmixter.py     # ccMixter — kept for reference, not run
│   └── wipe_ccmixter.py            # Utility: wipe ccmixter records from DB
│
├── .gitignore
├── project_architecture_technical_roadmap.md
└── serve.py
```

---

## 8. Pending Items (Prioritized)

### Next — Internet Archive additional collections
- Identify productive IA collections beyond `netlabels` + `78rpm`
- Candidates: `audio_music`, `georgeblood`, `librivoxaudio` (music only), netlabel sub-collections
- All IA streams are CORS-friendly — confirmed working

### Medium priority
- Cover art — deterministic gradient fallback per `album_id` when `cover_art_url` is null
- Attribution display — "i" button on track rows surfacing `attribution_text` + `license_type`
- Download button — `stream_url` with `download` attribute where `is_downloadable: true`
- Continue where left off — 10s position write to localStorage + Resume prompt
- Offline queue caching — pre-fetch next 2–3 audio URLs via Cache API

### Lower priority
- `/tracks/{id}` single track endpoint
- `/stats` endpoint — total count, source breakdown, genre distribution
- Settings view — crossfade, playback speed, cache management
- Crossfade — Web Audio API
- WAF + CORS hardening
- MusicBrainz metadata enrichment (artist IDs, album art, BPM)

---

## 9. Key AWS Resources

| Resource | Value |
|---|---|
| Region | `us-east-1` |
| Account | `170377509849` |
| DynamoDB table | `music-tracks` |
| Lambda — search | `music-search` (1024MB, 30s) |
| Lambda — artists | `music-artists` (1024MB, 30s) |
| Lambda — albums | `music-albums` (1024MB, 30s) |
| Lambda role | `arn:aws:iam::170377509849:role/music-lambda-role` |
| API Gateway ID | `9jxmxtjybb` |
| API base URL | `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1` |
| Jamendo credentials | Secrets Manager `music/jamendo` |
| Frontend (live) | `https://shannon-goddard.github.io/music/` |
| GitHub repo | `https://github.com/Shannon-Goddard/music` |

---

## 10. Architectural Differentiators

- **Zero-storage meta-index** — 0 GB audio stored, streams direct from source
- **Source quality gating** — `ALLOWED_PLATFORMS` + CORS vetting before any source is ingested
- **Unified cross-platform catalog** — single flat schema normalizes Internet Archive + Jamendo
- **Decoupled serverless stack** — GitHub Pages + Lambda + DynamoDB, operates within free-tier limits
- **Content-type classification** — separates music from podcasts/lectures/interviews at ingest
- **Preservation monitoring** — dead link health system tracks open archive integrity over time
