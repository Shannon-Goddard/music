# Architecture & Technical Roadmap: Infinite Meta-Index Music Platform

---

## ⚠️ Project Pivot Notice

This document is preserved in full as a reusable blueprint for any developer who wants to implement this architecture at scale. The serverless infrastructure (API Gateway, Lambda, WAF, DynamoDB) was fully designed, built, and deployed — it works.

**Why we pivoted:**
The original roadmap was designed for a catalog of 500k+ tracks. After completing all ingestion and 4 cleaning passes, the final catalog landed at **96,338 tracks** — with only ~57k having a resolved genre and ~67k classified as music. At that scale, the serverless stack is operational overhead that isn't justified:

- API Gateway + Lambda costs money at real traffic; a static catalog doesn't need server-side compute
- Cold starts add latency that a pre-built client-side index eliminates
- The primary growth path (Openverse — 4M+ tracks) has an indefinitely broken search endpoint with no public recovery timeline
- All other viable CC-licensed, CORS-clean sources with real APIs have been exhausted

**The decision:**
- ✅ DynamoDB table deleted — `catalog_final.csv` (96,338 rows) is the source of truth, committed to the repo
- ✅ API Gateway + all Lambdas torn down
- ✅ WAF WebACL detached and deleted
- ✅ Frontend rebuilt against a static JSON export served from GitHub Pages
- ✅ Client-side search via Fuse.js replaces all Lambda query patterns

**For other developers:**
Everything below this notice is the full working blueprint. If your project has the scale to justify it — pick it up and run.

---

This document is the master engineering blueprint for the platform. It reflects the state of the project at the point of the pivot.

---

## Current Live State

| Layer | Status | Detail |
|---|---|---|
| DynamoDB table | ✅ Deleted | `catalog_final.csv` is source of truth |
| API Gateway + Lambdas | ✅ Torn down | Replaced by static JSON |
| WAF WebACL | ✅ Deleted | No longer needed |
| Ingestion — IA netlabels | ✅ Done | 4,734 records |
| Ingestion — IA 78rpm | ✅ Done | 4,884 records |
| Ingestion — IA opensource_audio | ✅ Done | 7,497 records (1,739 deduped) |
| Ingestion — IA audio_music | ✅ Done | 4,893 records (4,857 deduped) |
| Ingestion — IA georgeblood | ✅ Done | 9,697 records (4 deduped) |
| Ingestion — IA audio_bookspoetry | ✅ Done | 6,144 records (3,618 deduped) |
| Ingestion — IA librivoxaudio | ✅ Done | 3,819 records (1,096 deduped) |
| Ingestion — Jamendo | ✅ Done | 35,025 CC tracks, 47 genre tags |
| Ingestion — Wikimedia Commons | ✅ Done | 3,559 tracks — 17 genre categories |
| Ingestion — Freesound | ✅ Done | 24 genre tags, CDN-hosted HQ MP3 previews |
| **Total catalog** | **96,338 tracks (final)** | IA: 42,037 — Jamendo: 35,025 — Wikimedia: 3,559 — Freesound: remainder |
| Ingestion — ccMixter | ❌ Removed | CORS 403 on content server — unplayable |
| `content_type` classification | ✅ Done | music / podcast / lecture / audiobook / interview |
| `language` field | ✅ Done | ISO 639-2 stored per record, null = language-agnostic |
| Static JSON export | ✅ Done | `data/genre/` (16 files) + `data/type/` (4 files) + `search-index.json` |
| Frontend PWA | ✅ Live | `https://shannon-goddard.github.io/music/` |
| Icons | ✅ Done | Real PNG icons, apple-touch-icon |
| Service worker | ✅ Live | Cache `v11`, 206 fix, offline pre-cache next 2 tracks |
| Language toggle | ✅ Live | EN / All pill in header, persists to localStorage |
| Attribution ⓘ sheet | ✅ Live | Bottom sheet on every track row — license, attribution, copy, download |
| Continue where left off | ✅ Live | 10s position write, resume bar shows track + timestamp, seeks on resume |
| Offline queue pre-cache | ✅ Live | Next 2 track URLs sent to SW `PRECACHE_AUDIO` on every play |
| Radio UI | ✅ Live | Radio section on home — tap genre, 50 random tracks auto-play instantly |

---

## Architecture Overview

```
[ Data Sources ]
  Internet Archive (7 collections) ✅  Jamendo ✅  Wikimedia Commons ✅  Freesound ✅
       │
       ▼
[ Ingestion & Normalization Layer ]  ← threaded, 10 workers/page, resumable
       │
       ▼
[ catalog_final.csv ] ────────────> Source of truth (96,338 rows, committed to repo)
       │
       ▼
[ export_json.py ] ───────────────> data/ JSON chunks (genre + type + search-index)
       │
       ▼
[ GitHub Pages (Frontend) ] ──────> PWA / SPA HTML5 Web Player + Fuse.js search
       │
       ├──> Casual Listeners     (radio, queue, Bluetooth, sleep timer)
       ├──> Music Enthusiasts    (tag browse, infinite scroll, library)
       ├──> Audiobook / Lecture listeners  (content_type filter)
       └──> Content Creators     (CC filter, attribution copy)
```

---

## 1. Database Schema (DynamoDB — Flat, Reference Only)

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

`language` is ISO 639-2 (`eng`, `fra`, `spa`, etc.) or absent for language-agnostic content (most music).

Future fields (not yet populated): `bpm`, `acoustid_fingerprint`, `musicbrainz_artist_id`.

`mood` is populated for Jamendo tracks via `musicinfo.speed` (low/medium/high).

---

## 2. DynamoDB GSIs (Reference Only — Table Deleted)

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

### Phase 4: API Gateway & Lambda ✅ Torn Down

All endpoints were live and working. Torn down after pivot to static JSON. Schema preserved here for reference.

| Method | Path | Lambda |
|---|---|---|
| GET | `/tracks/search?q=` | `music-search` |
| GET | `/tracks/search?genre=` | `music-search` |
| GET | `/tracks/search?type=` | `music-search` |
| GET | `/tracks/search?lang=` | `music-search` |
| GET | `/artists/search?q=` | `music-artists` |
| GET | `/albums/search?artist_id=` | `music-albums` |
| GET | `/albums/search?q=` | `music-albums` |
| GET | `/stats` | `music-stats` |
| GET | `/tracks/{id}` | `music-track` |
| GET | `/radio?genre=` | `music-radio` |

---

### Phase 5: PWA & Cross-Device Playback ✅ Complete

- PWA manifest + service worker — cache `v11`, 206 fix, offline pre-cache next 2 tracks
- Real PNG icons — favicon, PWA splash, apple-touch-icon
- Media Session API — Bluetooth / lock screen / car stereo controls
- AirPlay — zero-config via `<audio>` element

---

### Phase 6: Production Hardening ✅ Complete (Torn Down with Pivot)

- **6.1** CloudWatch alarms — Lambda error rate, 5xx rate
- **6.2** WAF rate limiting — 1000 req/5min per IP, WebACL attached to stage `v1`
- **6.3** CORS locked to `https://shannon-goddard.github.io` on all Lambdas

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
| Home view | ✅ Live | Filter chips (type + genre + radio), infinite scroll |
| Infinite scroll | ✅ Live | `IntersectionObserver` sentinel, `Showing X of Y` sticky bar |
| Keyboard shortcuts | ✅ Live | Space, ←/→, N, P |
| Media Session API | ✅ Live | Bluetooth / lock screen / car stereo |
| Language toggle | ✅ Live | EN / All pill in header, persists to localStorage |
| Cover art fallback | ✅ Live | Deterministic gradient per `album_id` |
| Attribution ⓘ button | ✅ Live | Bottom sheet — license URL, attribution text + copy, source link, download |
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
- Fully static — no Lambda calls
- `getLang()` / `setLang()` — persists to localStorage, defaults to `'eng'`
- `_langMatch(track)` — client-side language filter applied to all loaded chunks
- Functions: `searchByGenre`, `searchByType`, `searchTracks` (Fuse.js), `getRadio`, `getStats`
- Chunk cache (`_cache`) — each JSON file loaded once per session

### Attribution Sheet (`index.html`)
- `openInfo(encoded)` / `closeInfo()` — global functions, bottom sheet slides up from any track row
- Shows: title, artist, license URL (linked), attribution text + copy button, source link, download if `is_downloadable`

### Continue Where Left Off (`queue.js` + `player.js`)
- `savePosition(sec)` stores full track object + position to `music_session` every 10s
- Resume bar on home shows track title + saved timestamp, calls `playAt()` on click

### Service Worker (`service-worker.js`)
- Cache `v11` — shell assets cached on install
- 206 Partial Content responses skipped in both `_cacheFirst` and `PRECACHE_AUDIO`
- `PRECACHE_AUDIO` message handler — pre-fetches next 2 track URLs from player on every play
- `data/` JSON chunks served cache-first (static, never changes without a deploy)

### Views
- `views/home.js` — type chips + 16 genre chips + 16 radio chips, infinite scroll, `Showing X of Y` sticky bar
- `views/search.js` — Fuse.js text search, infinite scroll, artist→album drill-down, Play all
- `views/library.js` — saved tracks, Play all, heart removes, empty state

---

## 5. Ingestion Sources

| Source | Status | Records | Notes |
|---|---|---|---|
| Internet Archive — netlabels | ✅ Done | 4,734 | Modern CC netlabel releases |
| Internet Archive — 78rpm | ✅ Done | 4,884 | Pre-1930s jazz/blues |
| Internet Archive — opensource_audio | ✅ Done | 7,497 | 1,739 deduped |
| Internet Archive — audio_music | ✅ Done | 4,893 | 4,857 deduped |
| Internet Archive — georgeblood | ✅ Done | 9,697 | 4 deduped |
| Internet Archive — audio_bookspoetry | ✅ Done | 6,144 | 3,618 deduped |
| Internet Archive — librivoxaudio | ✅ Done | 3,819 | 1,096 deduped |
| Jamendo | ✅ Done | 35,025 | 47 taxonomy-informed tags, all CC-licensed |
| Wikimedia Commons | ✅ Done | 3,559 | 17 genre categories, CC audio |
| Freesound | ✅ Done | remainder | 24 genre tags, CDN HQ MP3 previews |
| ccMixter | ❌ Removed | 0 | Content server 403s cross-origin — unplayable |
| Free Music Archive (FMA) | ❌ Dead end | 0 | API dead, hotlinking prohibited |
| Openverse | ⏸ Paused | 0 | Search endpoint down — revisit if recovered |
| Starfrosch | ❌ Dead end | 0 | No API, Cloudflare-protected website only |
| Pixabay | ❌ No audio API | 0 | Images/video API only |
| MusicBrainz | 🔜 Planned | — | Metadata enrichment only, not a track source |

### Source Vetting Criteria
A source is only ingested if:
1. Files are directly streamable cross-origin (CORS headers present)
2. CC license or public domain confirmed per-track
3. No hotlinking or scraping prohibition

### Ingest Commands
```
python -u tests\test_ingest_ia.py netlabels
python -u tests\test_ingest_ia.py 78rpm
python -u tests\test_ingest_ia.py opensource_audio
python -u tests\test_ingest_ia.py audio_music
python -u tests\test_ingest_ia.py georgeblood
python -u tests\test_ingest_ia.py audio_bookspoetry
python -u tests\test_ingest_ia.py librivoxaudio

# Resume mid-run
python -u tests\test_ingest_ia.py opensource_audio --start-page 150

# Jamendo — full taxonomy sweep
python -u tests\test_ingest_jamendo.py

# Wikimedia — all 17 genres
python -u tests\test_ingest_wikimedia.py

# Freesound — all 24 tags
python -u tests\test_ingest_freesound.py

# Backfills
python -u tests\backfill_content_type.py
python -u tests\backfill_duration.py --workers 3
```

---

## 6. Known Issues

| Issue | Status | Notes |
|---|---|---|
| Service worker 206 error | ✅ Fixed | Cache `v11` skips 206 responses |
| ccMixter CORS 403 | ✅ Resolved | All records wiped |
| Scroll broken (overflow-x:hidden) | ✅ Fixed | `overflow-x:clip` on body |
| Non-English content in results | ✅ Mitigated | `lang=eng` default, EN/All toggle in header |
| AbortError on rapid track change | ✅ Fixed | Suppressed in `player.js` — benign race condition |

---

## 7. Folder Structure (Current)

```
music/
├── backend/
│   ├── api/                        # Lambda handlers — reference only, torn down
│   ├── db/
│   │   └── dynamo_client.py
│   ├── health/
│   │   └── link_checker.py
│   ├── ingestion/
│   │   ├── ia_adapter.py
│   │   ├── jamendo_adapter.py
│   │   ├── wikimedia_adapter.py
│   │   ├── freesound_adapter.py
│   │   ├── normalizer.py
│   │   └── deduplicator.py
│   └── requirements.txt
│
├── cleaning/
│   ├── catalog_final.csv           # Source of truth — 96,338 rows, all 4 passes complete
│   ├── export_json.py              # Exports catalog_final.csv → data/ JSON chunks
│   └── CLEANING.md                 # Full documentation of all 4 cleaning passes
│
├── data/                           # Static JSON served from GitHub Pages
│   ├── index.json                  # Manifest — total counts, genre/type inventory
│   ├── genre/                      # 16 files — one per canonical genre
│   └── type/                       # 4 files — audiobook, podcast, lecture, interview
│
├── css/
│   └── app.css
│
├── js/
│   ├── app.js                      # Router, lang toggle, back-to-top, keyboard shortcuts
│   ├── player.js                   # play(), playAt(), sleep timer, shuffle, repeat, precache
│   ├── queue.js                    # setQueue, savePosition
│   ├── api.js                      # Static JSON loader, Fuse.js search, lang filter
│   ├── utils.js                    # coverGradient(id), artThumb(track)
│   ├── scroll.js                   # InfiniteScroll — IntersectionObserver sentinel
│   ├── library.js
│   ├── i18n/
│   │   └── en.js
│   └── views/
│       ├── home.js                 # Type + genre + radio chips, infinite scroll
│       ├── search.js               # Fuse.js search, artist→album drill-down
│       └── library.js
│
├── icons/
├── infra/                          # AWS reference docs — dynamo schema, IAM policies
├── scripts/                        # Probe + taxonomy scripts
├── tests/                          # Ingest + backfill scripts
│
├── index.html
├── about.html
├── privacy.html
├── terms.html
├── licenses.html
├── manifest.json
├── service-worker.js
├── serve.py                        # Local dev server — strips /music prefix
├── robots.txt
├── sitemap.xml
└── project_architecture_technical_roadmap.md
```

---

## 8. Pending Items (Prioritized)

### 1. content_type backfill ✅ Done
### 2. duration_sec backfill ✅ Done
### 3. Freesound full ingest ✅ Done
### 4. Genre normalization ✅ Done — 4 cleaning passes complete
### 5. Static JSON export ✅ Done — `cleaning/export_json.py`

### 6. Openverse ⏸ Paused (when API recovers)
- Search endpoint currently timing out
- 644k Jamendo + 3.98M Wikimedia tracks not yet touched via their API
- Would 10x+ the catalog — highest volume multiplier available
- If catalog reaches 500k+, revert to the serverless architecture above

### 7. README
- Write user-facing README for the GitHub repo

---

## 9. Key Resources

| Resource | Value |
|---|---|
| Frontend (live) | `https://shannon-goddard.github.io/music/` |
| GitHub repo | `https://github.com/Shannon-Goddard/music` |
| Source of truth | `cleaning/catalog_final.csv` — 96,338 rows |
| Static data | `data/` — 16 genre chunks + 4 type chunks + search-index |
| Dev server | `python serve.py` → `http://localhost:8000/` |

---

## 10. Architectural Differentiators

- **Zero-storage meta-index** — 0 GB audio stored, streams direct from source
- **Source quality gating** — CORS vetting + license check before any source is ingested
- **Language-aware catalog** — ISO 639-2 per record, EN default filter, user-toggleable
- **Content-type diversity** — music, audiobooks, lectures, podcasts all classified and filterable
- **Unified cross-platform catalog** — single flat schema across Internet Archive + Jamendo + Wikimedia + Freesound
- **Preservation monitoring** — dead link health system tracks open archive integrity over time

---

## 11. Detour — Static JSON Architecture

### Why
After completing all 4 cleaning passes, the final catalog landed at **96,338 tracks**. The serverless stack was designed for 500k+. At this scale:

- API Gateway + Lambda costs money at real traffic — a static catalog doesn't need server-side compute
- Cold starts add latency that a pre-built client-side index eliminates
- Openverse (the primary 10x growth path) has an indefinitely broken search endpoint
- All other viable CC-licensed, CORS-clean sources with real APIs are exhausted

The infrastructure works. The scale didn't materialize. A detour is the smarter road.

### What changed
- DynamoDB table deleted — `cleaning/catalog_final.csv` (96,338 rows) is the source of truth
- API Gateway + all 6 Lambdas torn down
- WAF WebACL detached and deleted
- Frontend rewired to static JSON served from GitHub Pages
- Client-side search (Fuse.js) replaces all Lambda query patterns

### Static data architecture

```
data/
├── index.json              # Manifest — total counts, genre/type inventory
├── genre/
│   ├── electronic.json     # 12,981 tracks
│   ├── ambient.json        # 6,851 tracks
│   ├── classical.json      # 5,580 tracks
│   ├── hip-hop.json        # 4,702 tracks
│   ├── rock.json           # 4,665 tracks
│   ├── pop.json            # 4,438 tracks
│   ├── jazz.json           # 4,275 tracks
│   ├── experimental.json   # 3,276 tracks
│   ├── reggae.json         # 2,894 tracks
│   ├── blues.json          # 2,074 tracks
│   ├── folk.json           # 1,770 tracks
│   ├── soul.json           # 1,553 tracks
│   ├── country.json        # 832 tracks
│   ├── metal.json          # 453 tracks
│   ├── punk.json           # 293 tracks
│   └── industrial.json     # 196 tracks
└── type/
    ├── audiobook.json      # 10,867 tracks
    ├── podcast.json        # 880 tracks
    ├── lecture.json        # 535 tracks
    └── interview.json      # 361 tracks
```

Note: `type/music.json` was not generated — at 64MB it is too large for GitHub Pages. Music is browsed by genre only.

### Query pattern mapping

| Old Lambda pattern | New static pattern |
|---|---|
| `GET /tracks/search?genre=jazz` | Load `data/genre/jazz.json`, paginate client-side |
| `GET /tracks/search?type=audiobook` | Load `data/type/audiobook.json`, paginate client-side |
| `GET /tracks/search?q=coltrane` | Fuse.js search against `data/search-index.json` |
| `GET /radio?genre=jazz&limit=50` | Load `data/genre/jazz.json`, shuffle, slice 50 |
| `lang=eng` filter | Client-side filter on `language` field |

### Scripts
- `cleaning/export_json.py` — exports `catalog_final.csv` → `data/` JSON chunks
- Run once after any catalog update; commit `data/` to repo

### Trade-offs accepted
- Text search quality: Fuse.js fuzzy search vs DynamoDB full-scan — acceptable at 96k tracks
- No server-side artist/album search endpoints — client-side filtering on loaded chunks
- `data/` folder is ~15-20MB in the repo — acceptable for GitHub Pages
- If catalog ever reaches 500k+, revert to the serverless architecture above
