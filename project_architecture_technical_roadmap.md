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
| Ingestion — IA opensource_audio | 🔄 Running | Up to 100,000 items, ~80 pages/hr |
| Ingestion — IA audio_music | 🔄 Running | Up to 25,000 items |
| Ingestion — IA georgeblood | 🔄 Running | Up to 25,000 items, pre-1928 public domain |
| Ingestion — IA audio_bookspoetry | 🔄 Running | Up to 10,000 items |
| Ingestion — IA librivoxaudio | 🔄 Running | Up to 5,000 items |
| Ingestion — Jamendo | ✅ Done | ~13,656 CC tracks, 46 genre tags |
| Ingestion — ccMixter | ❌ Removed | CORS 403 on content server — unplayable |
| `content_type` classification | ✅ Done | music / podcast / lecture / audiobook / interview / other |
| `language` field | ✅ Done | ISO 639-2 stored per record, null = language-agnostic |
| API — `/tracks/search` | ✅ Live | `q=`, `genre=`, `type=`, `lang=`, `offset=`, `total` |
| API — `/artists/search` | ✅ Live | `q=` → `{ artist_id, artist_name, track_count }` |
| API — `/albums/search` | ✅ Live | `artist_id=` (GSI) or `q=` (scan) |
| Lambda memory | ✅ 1024MB | All 3 Lambdas, 30s timeout |
| Frontend PWA | ✅ Live | `https://shannon-goddard.github.io/music/` |
| Icons | ✅ Done | Real PNG icons, apple-touch-icon for home screen saves |
| Service worker | ✅ Fixed | Cache `v4`, 206 Partial Content responses skipped |
| Language toggle | ✅ Live | EN / All pill in header, persists to localStorage |

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

#### Pending Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/tracks/{id}` | Single track detail |
| GET | `/radio?genre=` | Randomized active tracks by genre |
| GET | `/stats` | Total count, source breakdown, genre distribution |

---

### Phase 5: PWA & Cross-Device Playback ✅ Complete

- PWA manifest + service worker — cache `v4`, 206 fix applied
- Real PNG icons — favicon, PWA splash, apple-touch-icon
- Media Session API — Bluetooth / lock screen / car stereo controls
- AirPlay — zero-config via `<audio>` element

---

### Phase 6: Production Hardening 🔜 Pending

- **6.1** CloudWatch alarms — Lambda error rate, 5xx rate
- **6.2** WAF rate limiting — 100 req/min per IP
- **6.3** CORS locked to GitHub Pages origin (currently open `*`)

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
| Attribution "i" button | 🔜 Pending | Tap to see CC license + copy attribution string |
| Download button | 🔜 Pending | `stream_url` with `download` attr where `is_downloadable: true` |
| Continue where left off | 🔜 Pending | 10s position write + Resume prompt on open |
| Offline queue caching | 🔜 Pending | Pre-fetch next 2–3 audio URLs via Cache API |
| Crossfade | 🔜 Pending | Web Audio API, configurable duration |
| Playback speed | 🔜 Pending | `playbackRate` control |
| Settings view | 🔜 Pending | Crossfade, speed, cache management |

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

### API (`api.js`)
- `lang` state — `getLang()` / `setLang()`, persists to localStorage, defaults to `'eng'`
- `_langParam()` appended to all search calls — `&lang=all` when set to all, empty otherwise
- All search functions: `searchTracks`, `searchByGenre`, `searchByType`, `searchArtists`, `searchAlbums`

### Service Worker (`service-worker.js`)
- Cache `v4` — shell assets cached on install, includes `utils.js`
- 206 Partial Content responses skipped in both `_cacheFirst` and `PRECACHE_AUDIO`
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
| Internet Archive — opensource_audio | 🔄 Running | TBD | 3M item pool, CC-licensed |
| Internet Archive — audio_music | 🔄 Running | TBD | 535k item pool, music-focused |
| Internet Archive — georgeblood | 🔄 Running | TBD | 187k digitized 78rpm/shellac, pre-1928 PD |
| Internet Archive — audio_bookspoetry | 🔄 Running | TBD | 75k audiobooks + poetry |
| Internet Archive — librivoxaudio | 🔄 Running | TBD | 21k LibriVox public domain audiobooks |
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
| Service worker 206 error | ✅ Fixed | Cache `v3` skips 206 responses |
| ccMixter CORS 403 | ✅ Resolved | All records wiped from DB |
| Lambda total count cache | ⚠️ Known | `total` caches ~5min after large DB changes |
| Cover art missing on most tracks | ✅ Fixed | Deterministic gradient fallback via `utils.js` — same track always same gradient |
| Non-English content in results | ✅ Mitigated | `lang=eng` default filters to English + language-agnostic; EN/All toggle in header |

---

## 7. Folder Structure (Current)

```
music/
├── backend/
│   ├── api/
│   │   ├── search.py               # Lambda: GET /tracks/search (q, genre, type, lang, offset)
│   │   ├── artists.py              # Lambda: GET /artists/search?q=
│   │   └── albums.py               # Lambda: GET /albums/search
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
│   ├── service-worker.js           # Cache v3, 206 fix
│   ├── about.html
│   ├── privacy.html
│   ├── terms.html
│   ├── licenses.html
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   ├── app.js                  # Router, lang toggle wiring, keyboard shortcuts
│   │   ├── player.js               # Media Session API, sleep timer, shuffle, repeat
│   │   ├── queue.js
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

### Next — finish running IA collections
- All 5 new collections running in parallel terminals
- After completion: update live record count, commit results

### High priority (UX)
- Attribution "i" button — tap on any track row to see CC license + copy attribution string
- Download button — `stream_url` with `download` attribute where `is_downloadable: true`

### Medium priority
- Continue where left off — 10s position write to localStorage + Resume prompt on open
- Offline queue caching — pre-fetch next 2–3 audio URLs via Cache API
- `/stats` endpoint — total count, source breakdown, genre distribution

### Lower priority
- Settings view — crossfade, playback speed, cache management
- Crossfade — Web Audio API, configurable duration
- Playback speed — `playbackRate` control
- `/tracks/{id}` single track endpoint
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
- **Source quality gating** — CORS vetting + license check before any source is ingested
- **Language-aware catalog** — ISO 639-2 per record, EN default filter, user-toggleable
- **Content-type diversity** — music, audiobooks, lectures, podcasts all classified and filterable
- **Unified cross-platform catalog** — single flat schema across Internet Archive + Jamendo
- **Decoupled serverless stack** — GitHub Pages + Lambda + DynamoDB, free-tier friendly
- **Preservation monitoring** — dead link health system tracks open archive integrity over time
