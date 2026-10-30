# Architecture & Technical Roadmap: Infinite Meta-Index Music Platform

This document is the master engineering blueprint for the platform. It reflects the current live state of the project and the forward roadmap.

---

## Current Live State

| Layer | Status | Detail |
|---|---|---|
| DynamoDB table | ✅ Live | `music-tracks`, `us-east-1` |
| GSIs | ✅ All 7 ACTIVE | See Section 2 |
| Ingestion — IA netlabels | ✅ Done | 4,734 records |
| Ingestion — IA 78rpm | ✅ Done | 4,884 records |
| Ingestion — IA opensource_audio | ✅ Done | 7,497 records (1,739 deduped) |
| Ingestion — IA audio_music | ✅ Done | 4,893 records (4,857 deduped) |
| Ingestion — IA georgeblood | ✅ Done | 9,697 records (4 deduped) |
| Ingestion — IA audio_bookspoetry | ✅ Done | 6,144 records (3,618 deduped) |
| Ingestion — IA librivoxaudio | ✅ Done | 3,819 records (1,096 deduped) |
| Ingestion — Jamendo | ✅ Done | 13,656 CC tracks, 46 genre tags |
| **Total catalog** | **55,666 tracks** | IA: 42,010 — Jamendo: 13,656 |
| Ingestion — ccMixter | ❌ Removed | CORS 403 on content server — unplayable |
| `content_type` classification | ✅ Done | music / podcast / lecture / audiobook / interview / other |
| `language` field | ✅ Done | ISO 639-2 stored per record, null = language-agnostic |
| API — `/tracks/search` | ✅ Live | `q=`, `genre=`, `type=`, `lang=`, `offset=`, `total` |
| API — `/artists/search` | ✅ Live | `q=` → `{ artist_id, artist_name, track_count }` |
| API — `/albums/search` | ✅ Live | `artist_id=` (GSI) or `q=` (scan) |
| Lambda memory | ✅ 1024MB | All 4 Lambdas, 30s timeout |
| API — `/stats` | ✅ Live | 55,666 total — IA: 42,010, Jamendo: 13,656 |
| Frontend PWA | ✅ Live | `https://shannon-goddard.github.io/music/` |
| Icons | ✅ Done | Real PNG icons, apple-touch-icon → `logo-180.png` (solid bg) |
| Service worker | ✅ Fixed | Cache `v4`, 206 fix, offline pre-cache next 2 tracks |
| Language toggle | ✅ Live | EN / All pill in header, persists to localStorage |
| Attribution ⓘ sheet | ✅ Live | Bottom sheet on every track row — license, attribution, copy, download |
| Continue where left off | ✅ Live | 10s position write, resume bar shows track + timestamp, seeks on resume |
| Offline queue pre-cache | ✅ Live | Next 2 track URLs sent to SW `PRECACHE_AUDIO` on every play |

**API base URL:** `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1`

---

## Architecture Overview

```
[ Data Sources ]
  Internet Archive (7 collections) ✅  Jamendo ✅  MusicBrainz (enrichment) 🔜
       │
       ▼
[ Ingestion & Normalization Layer ]  ← threaded, 10 workers/page, resumable
       │
       ▼
[ AWS DynamoDB ] ─────────────────────> Meta-Index (CC-licensed, all streamable)
       │
       ▼
[ AWS API Gateway + Lambda ] ─────────> Serverless REST API (lang= filter live)
       │
       ▼
[ GitHub Pages (Frontend) ] ──────────> PWA / SPA HTML5 Web Player
       │
       ├──> Casual Listeners     (radio, queue, Bluetooth, sleep timer)
       ├──> Music Enthusiasts    (tag browse, infinite scroll, library)
       ├──> Audiobook / Lecture listeners  (content_type filter)
       └──> Content Creators     (CC filter, attribution copy)
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
  "language":         "eng",
  "content_type":     "music",
  "duration_sec":     null,
  "cover_art_url":    null,
  "stream_url":       "https://archive.org/download/autojazz/autojazz.mp3",
  "source_url":       "https://archive.org/details/autojazz",
  "source_platform":  "internet_archive",
  "ia_collection":    "netlabels",
  "format":           "mp3",
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

`language` is ISO 639-2 (`eng`, `fra`, `spa`, etc.) or absent for language-agnostic content (most music). The API `lang=eng` filter matches `language=eng` OR no language field.

Future fields (not yet populated): `bpm`, `mood`, `acoustid_fingerprint`, `musicbrainz_artist_id`.

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

---

## 3. Technical Roadmap

### Phase 1: Modular Ingestion & Pipeline Setup ✅ Complete

- Multi-source adapters — `ia_adapter.py`, `jamendo_adapter.py` live
- Normalization & deduplication — `normalizer.py` + `deduplicator.py` live
- `content_type` classification — `_detect_content_type()` in `ia_adapter.py`
- `language` normalization — ISO 639-2, stored per record, null = language-agnostic
- Threaded ingest — `normalize_batch()` with 10 workers, ~80 pages/hr
- Resumable runs — `--start-page N` flag on `test_ingest_ia.py`
- WAV + M4A fallback — `_pick_audio()` accepts WAV and M4A when no MP3 exists
- `ALLOWED_PLATFORMS` gating — source quality control in `normalizer.py`

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
| GET | `/tracks/search?lang=` | `music-search` | ✅ Live — `eng` default, `all` disables filter |
| GET | `/artists/search?q=` | `music-artists` | ✅ Live |
| GET | `/albums/search?artist_id=` | `music-albums` | ✅ Live |
| GET | `/albums/search?q=` | `music-albums` | ✅ Live |
| GET | `/stats` | `music-stats` | ✅ Live — total, by_platform, by_type, top 20 genres |

#### Pending Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/tracks/{id}` | `music-track` | ✅ Live — single track by `track_id`, includes all MB fields |
| GET | `/radio?genre=` | pending | Randomized active tracks by genre |

---

### Phase 5: PWA & Cross-Device Playback ✅ Complete

- PWA manifest + service worker — cache `v4`, 206 fix, offline pre-cache next 2 tracks
- Real PNG icons — favicon, PWA splash, apple-touch-icon
- Media Session API — Bluetooth / lock screen / car stereo controls
- AirPlay — zero-config via `<audio>` element

---

### Phase 6: Production Hardening ✅ Complete

- **6.1** CloudWatch alarms — Lambda error rate, 5xx rate
- **6.2** WAF rate limiting — 100 req/5min per IP, WebACL `music-api-waf` attached to stage `v1`
- **6.3** CORS locked to `https://shannon-goddard.github.io` on all 5 Lambdas

---

### Phase 7: Listener-First PWA Features ✅ Mostly Complete

| Feature | Status | Notes |
|---|---|---|
| Sleep timer | ✅ Live | 15/30/45/60/off, 10s fade-out |
| Shuffle | ✅ Live | `Queue.random()` |
| Repeat | ✅ Live | Restarts on `ended` |
| Recently played | ✅ Live | `music_recent` localStorage, capped at 20 |
| My Library (local) | ✅ Live | `music_library` localStorage, heart toggle |
| Library view | ✅ Live | Play all, empty state |
| Home view | ✅ Live | Filter chips (type + genre + mood), infinite scroll |
| Infinite scroll | ✅ Live | `IntersectionObserver` sentinel |
| Keyboard shortcuts | ✅ Live | Space, ←/→, N, P |
| Media Session API | ✅ Live | Bluetooth / lock screen / car stereo |
| Language toggle | ✅ Live | EN / All pill in header, persists to localStorage |
| Cover art fallback | ✅ Live | Deterministic gradient per `album_id` — 12 palette pairs, hash-derived angle, note/eq-bars overlay |
| Attribution ⓘ button | ✅ Live | Bottom sheet — license URL, attribution text + copy, source link, download if `is_downloadable` |
| Download button | ✅ Live | Inside attribution sheet, `stream_url` with `download` attr where `is_downloadable: true` |
| Continue where left off | ✅ Live | 10s position write, resume bar shows track + timestamp, `playAt()` seeks on resume |
| Offline queue caching | ✅ Live | Next 2 track URLs pre-fetched via SW `PRECACHE_AUDIO` on every play |
| Crossfade | ✅ Live | Web Audio API GainNode, 2–12s configurable, toggle + slider in settings |
| Playback speed | ✅ Live | `playbackRate` 0.5–2x, persists to localStorage, in settings |
| Settings view | ✅ Live | Speed picker, crossfade toggle+slider, audio cache clear |

---

## 4. Frontend — What's Built (Live on gh-pages)

### Visual Design
- Dark theme: `#111113` surface, `#1c1c1f` card, `#242428` raised
- Brand accent: `#04AA6D` — header wordmark, active chips, eq bars, heart icons
- Tailwind CDN 3.4.1 with custom color tokens

### Layout
- Fixed header: waveform wordmark + search + desktop nav + EN/All language toggle
- Fixed player footer: desktop = single row, mobile = stacked
- Mobile bottom nav: Home / Search / Library
- Hamburger drawer (mobile): slides from right

### Player (`player.js`)
- Shuffle, repeat, sleep timer (15/30/45/60/off with 10s fade)
- Media Session API — Bluetooth / lock screen / hardware controls
- Audio error → skip to next (no silent failures)
- Recently played written to localStorage on every `play()`
- `playAt(track, positionSec)` — plays track then seeks after `canplay`
- `_precacheNext()` — posts next 2 queue URLs to SW `PRECACHE_AUDIO` on every play

### API (`api.js`)
- `lang` state — `getLang()` / `setLang()`, persists to localStorage, defaults to `'eng'`
- `_langParam()` appended to all search calls — `&lang=all` when set to all, empty otherwise
- All search functions: `searchTracks`, `searchByGenre`, `searchByType`, `searchArtists`, `searchAlbums`

### Attribution Sheet (`index.html`)
- `openInfo(encoded)` / `closeInfo()` — global functions, bottom sheet slides up from any track row
- Shows: title, artist, license URL (linked), attribution text + copy button, source link, download if `is_downloadable`
- Track data passed as `encodeURIComponent(JSON.stringify({...}))` on `data-info` attribute

### Continue Where Left Off (`queue.js` + `player.js`)
- `savePosition(sec)` stores full track object + position to `music_session` every 10s
- Resume bar on home shows track title + saved timestamp, calls `playAt()` on click

### Service Worker (`service-worker.js`)
- Cache `v4` — shell assets cached on install, includes `utils.js`
- 206 Partial Content responses skipped in both `_cacheFirst` and `PRECACHE_AUDIO`
- `PRECACHE_AUDIO` message handler — pre-fetches next 2 track URLs from player on every play
- API calls always network-only

### Views
- `views/home.js` — filter chips (type + genre + mood), infinite scroll, hearts, now-playing
- `views/search.js` — infinite scroll, artist→album drill-down, Play all, hearts
- `views/library.js` — saved tracks, Play all, heart removes, empty state

---

## 5. Ingestion Sources

| Source | Status | Records | Notes |
|---|---|---|---|
| Internet Archive — netlabels | ✅ Done | 4,734 | Modern CC netlabel releases |
| Internet Archive — 78rpm | ✅ Done | 4,884 | Pre-1930s jazz/blues |
| Internet Archive — opensource_audio | ✅ Done | 7,497 | 1,739 deduped |
| Internet Archive — audio_music | ✅ Done | 4,893 | 4,857 deduped — heavy overlap w/ other collections |
| Internet Archive — georgeblood | ✅ Done | 9,697 | 4 deduped — unique 78rpm/shellac catalog |
| Internet Archive — audio_bookspoetry | ✅ Done | 6,144 | 3,618 deduped |
| Internet Archive — librivoxaudio | ✅ Done | 3,819 | 1,096 deduped, overlaps w/ bookspoetry |
| Jamendo | ✅ Done | ~13,656 | 46 genre tags, all CC-licensed |
| ccMixter | ❌ Removed | 0 | Content server 403s cross-origin — unplayable |
| Free Music Archive (FMA) | ❌ Dead end | 0 | API dead, hotlinking prohibited |
| MusicBrainz | 🔜 Planned | — | Metadata enrichment only, not a track source |

### Source Vetting Criteria
A source is only ingested if:
1. Files are directly streamable cross-origin (CORS headers present)
2. CC license or public domain confirmed per-track
3. No hotlinking or scraping prohibition

### Ingest Commands (per collection, run in separate terminals)
```
python -u tests\test_ingest_ia.py opensource_audio
python -u tests\test_ingest_ia.py audio_music
python -u tests\test_ingest_ia.py georgeblood
python -u tests\test_ingest_ia.py audio_bookspoetry
python -u tests\test_ingest_ia.py librivoxaudio

# Resume mid-run
python -u tests\test_ingest_ia.py opensource_audio --start-page 150
```

---

## 6. Known Issues

| Issue | Status | Notes |
|---|---|---|
| Service worker 206 error | ✅ Fixed | Cache `v4` skips 206 responses |
| ccMixter CORS 403 | ✅ Resolved | All records wiped from DB |
| Lambda total count cache | ⚠️ Known | `total` caches ~5min after large DB changes |
| Scroll broken (overflow-x:hidden) | ✅ Fixed | `overflow-x:clip` on body — `hidden` creates scroll container collapsing body height |
| Non-English content in results | ✅ Mitigated | `lang=eng` default filters to English + language-agnostic; EN/All toggle in header |

---

## 7. Folder Structure (Current)

```
music/
├── backend/
│   ├── api/
│   │   ├── search.py               # Lambda: GET /tracks/search (q, genre, type, lang, offset)
│   │   ├── artists.py              # Lambda: GET /artists/search?q=
│   │   ├── albums.py               # Lambda: GET /albums/search
│   │   └── stats.py                # Lambda: GET /stats — total, by_platform, by_type, top_genres
│   ├── db/
│   │   └── dynamo_client.py
│   ├── health/
│   │   └── link_checker.py
│   ├── ingestion/
│   │   ├── base_adapter.py
│   │   ├── ia_adapter.py           # IA — 7 collections, threaded, language normalization
│   │   ├── jamendo_adapter.py      # Jamendo — 46 tags, ~13,656 tracks
│   │   ├── ccmixter_adapter.py     # ccMixter — kept for reference, not used
│   │   ├── normalizer.py           # ALLOWED_PLATFORMS gating
│   │   └── deduplicator.py
│   └── requirements.txt
│
├── frontend/                       # Deployed to gh-pages branch
│   ├── index.html                  # EN/All language toggle in header
│   ├── manifest.json               # PWA: 3 icon sizes
│   ├── service-worker.js           # Cache v4, 206 fix, PRECACHE_AUDIO handler
│   ├── about.html
│   ├── privacy.html
│   ├── terms.html
│   ├── licenses.html
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   ├── app.js                  # Router, lang toggle, back-to-top, keyboard shortcuts
│   │   ├── player.js               # play(), playAt(), sleep timer, shuffle, repeat, precache
│   │   ├── queue.js                # setQueue, savePosition (stores full track + sec)
│   │   ├── api.js                  # getLang/setLang, lang= param on all search calls
│   │   ├── utils.js                # coverGradient(id), artThumb(track) — shared across views
│   │   ├── scroll.js
│   │   ├── library.js
│   │   ├── i18n/
│   │   │   └── en.js
│   │   └── views/
│   │       ├── home.js
│   │       ├── search.js
│   │       └── library.js
│   └── icons/
│       ├── icon.png                # Source (221×221)
│       ├── icon-192.png            # PWA + favicon
│       ├── icon-512.png            # PWA splash
│       ├── logo.png                # Source (224×224)
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
│   ├── probe_jamendo_cc_total.py
│   ├── probe_ia_collections.py     # Item counts across all IA collections
│   ├── probe_ia_new_collections.py # Sanity check one page per collection
│   └── preview_collections.py
│
├── tests/
│   ├── test_ingest.py              # Legacy: IA netlabels + 78rpm
│   ├── test_ingest_ia.py           # Current: all IA collections, threaded, resumable
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

### Next — content_type backfill
- `other` = 25,718 records — mostly georgeblood + older IA items with weak metadata
- georgeblood records are all music by definition
- librivoxaudio records are all audiobooks by definition
- Quick script keyed off `ia_collection` would reclassify most without touching the API

### Pending (lower priority)
- MusicBrainz metadata enrichment — backfill script running, cover art + artist IDs + genre tags
- `/radio?genre=` randomized endpoint
- CloudWatch alarms — Lambda error rate, 5xx rate
- Settings view — ✅ Live (speed, crossfade, cache clear)

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
| Lambda — stats | `music-stats` (1024MB, 30s) |
| Lambda — track | `music-track` (512MB, 10s) |
| Lambda role | `arn:aws:iam::170377509849:role/music-lambda-role` |
| WAF WebACL | `music-api-waf` — 100 req/5min per IP, attached to stage `v1` |
| CORS origin | `https://shannon-goddard.github.io` (all 5 Lambdas) |
| API Gateway ID | `9jxmxtjybb` |
| API base URL | `https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1` |
| Jamendo credentials | Secrets Manager `music/jamendo` |
| Frontend (live) | `https://shannon-goddard.github.io/music/` |
| GitHub repo | `https://github.com/Shannon-Goddard/music` |

---

## 10. Architectural Differentiators

- **Zero-storage meta-index** — 0 GB audio stored, streams direct from source
- **Source quality gating** — CORS vetting + license check before any source is ingested
- **Language-aware catalog** — ISO 639-2 per record, EN default filter, user-toggleable
- **Content-type diversity** — music, audiobooks, lectures, podcasts all classified and filterable
- **Unified cross-platform catalog** — single flat schema across Internet Archive + Jamendo
- **Decoupled serverless stack** — GitHub Pages + Lambda + DynamoDB, free-tier friendly
- **Preservation monitoring** — dead link health system tracks open archive integrity over time
