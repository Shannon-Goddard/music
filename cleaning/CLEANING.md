# Catalog Cleaning Workstream

Source: `cleaning/catalog_review.csv` — full DynamoDB export, 99,220 tracks as of 2026-11-01.

Each cleaning pass produces a new CSV. The final clean CSV will be the candidate for the flat JSON architecture decision.

---

## Passes

### Pass 1 — Bad stream URLs ✅ Done
**Script:** `cleaning/clean_stream_url.py`
**Input:** `cleaning/catalog_review.csv`
**Output:** `cleaning/catalog_clean_stream_url.csv`

**Rule:** Remove any row where `stream_url` contains non-ASCII characters in the URL path.

Two categories removed:
- Non-Latin scripts in filename — Nepali, Marathi, Bengali, Arabic, etc. — guaranteed to fail in the player
- Accented Latin characters — French `é`, `ô`, German `ü`, etc. — unreliable across players and proxies

| | Count |
|---|---|
| Removed | 2,002 |
| Kept | 97,218 |

---

## Catalog Snapshot (at export)

From `cleaning/catalog_summary.txt`:

### By Platform
| Platform | Tracks | % |
|---|---|---|
| internet_archive | 49,605 | 50.0% |
| jamendo | 35,025 | 35.3% |
| freesound | 11,023 | 11.1% |
| wikimedia | 3,567 | 3.6% |

### By Content Type
| Type | Tracks | % |
|---|---|---|
| music | 67,379 | 67.9% |
| other | 29,027 | 29.3% |
| audiobook | 961 | 1.0% |
| podcast | 940 | 0.9% |
| lecture | 551 | 0.6% |
| interview | 362 | 0.4% |

### Missing Fields
| Field | Missing | % |
|---|---|---|
| cover_art_url | 59,862 | 60.3% |
| language | 69,327 | 69.9% |
| duration_sec | 22,044 | 22.2% |
| title | 0 | 0% |
| artist_name | 0 | 0% |
| genre | 0 | 0% |

### Known Bad Genre Values
These genre values are collection names, label names, or placeholders — not real genres.
Pending a cleaning pass.

| Genre value | Count | Problem |
|---|---|---|
| `78rpm` | 9,546 | IA collection name |
| `librivox` | 8,478 | IA collection name |
| `victor` | 3,818 | Record label name |
| `Unknown` | 3,705 | Placeholder |
| `columbia` | 1,144 | Record label name |
| `صوتيات` | 738 | Arabic for "audio files" |

---

## Passes (continued)

### Pass 2 — Genre cleaning ✅ Done

#### Step 1 — Delete junk rows
**Script:** `cleaning/delete_rows.py`
**Input:** `cleaning/catalog_clean_stream_url.csv`
**Output:** `cleaning/catalog_clean_genre.csv`

Deleted 785 rows where genre was provably junk — not bad data, not unmappable, but actively wrong to keep:
- `Mystery*` / `Misterio*` variants — single uploader's internal tagging system
- `NSFRI`, `NSSUN` — internal codes
- `shitpost`, `shit`, `cunt`, `Pussy` — noise
- `asdsad`, `Djjdj`, `Ldldldl` etc. — keyboard mash
- `LP`, `cd`, `mp3`, `mp4`, `vinyl`, `pdf`, `dvd-video` — format labels

| | Count |
|---|---|
| Deleted | 785 |
| Kept | 96,433 |

#### Step 2 — Build strict genre map
**Script:** `cleaning/map_genres.py` (imported by apply script)

Strict unambiguous-only mappings. Rule: if a reasonable person could disagree, it's not in the map.
- 15 canonical genres: `electronic`, `ambient`, `jazz`, `classical`, `blues`, `rock`, `hip-hop`, `folk`, `country`, `metal`, `punk`, `reggae`, `soul`, `experimental`, `pop`, `industrial`
- `indie` and `poprock` → rock
- `country` added as its own canonical genre (526 genre hits + 1,187 tag hits)
- No catch-all buckets — world, gospel, ethnic, filmscore, country → not forced into folk/electronic

#### Step 3 — Apply map + tags fallback
**Script:** `cleaning/apply_genres.py`
**Input:** `cleaning/catalog_clean_genre.csv`
**Output:** `cleaning/catalog_genre_applied.csv` (adds `genre_resolved` column)

Logic per row:
1. Try strict map on `genre` field
2. If no hit, scan `tags` tokens through same map
3. If still no hit, `genre_resolved` = blank → will be nulled in DynamoDB

| | Tracks | % |
|---|---|---|
| Total | 96,433 | |
| Mapped via genre field | 45,639 | 47.3% |
| Rescued via tags | 11,209 | 11.6% |
| Unresolved → null | 39,585 | 41.0% |

#### Step 4 — DynamoDB backfill
**Script:** `cleaning/backfill_genres.py`
**Input:** `cleaning/catalog_genre_applied.csv`

- `genre_resolved` has value → `SET genre = <canonical>`
- `genre_resolved` blank → `REMOVE genre` (null)
- Dry-run by default, `--live` flag to apply

**Status:** Ready to run.

---

## Pending Passes

- [ ] **Pass 3** — Duplicate titles within same platform — spot check
- [ ] **Pass 4** — Missing `duration_sec` (22,044) — decide: backfill or acceptable gap

---

## Frontend Changes

### Removed: `Other` from Type filter chips
**File:** `js/views/home.js`
**Reason:** `content_type = other` no longer exists in the catalog after Pass 2 (content_type backfill). Showing it would return zero results.

### Removed: Mood Mix section (Energetic / Calm / Melancholic / Happy / Intense)
**File:** `js/views/home.js`
**Reason:** Mood values in the DB (`low/medium/high` from Jamendo `musicinfo.speed`) do not match the chip filter values (`energetic/calm/melancholic/happy/intense`). All five chips returned zero results. Dead UI removed.

### Added: `Country` to Genre chips
**File:** `js/views/home.js`
**Reason:** 526 tracks with `country` genre + 1,187 tag hits rescued via tags fallback. Earns its own chip.

---

## Files

| File | Description |
|---|---|
| `catalog_review.csv` | Full raw DynamoDB export — do not modify |
| `catalog_summary.txt` | Aggregate stats from the raw export |
| `catalog_clean_stream_url.csv` | After Pass 1 — bad URLs removed |
| `export_catalog_csv.py` | Pulls full table from DynamoDB to CSV |
| `summarize_catalog.py` | Generates `catalog_summary.txt` from any CSV |
| `clean_stream_url.py` | Pass 1 script |
| `probe_bad_urls.py` | Exploration script used to identify bad URL patterns |
| `catalog_clean_genre.csv` | After Pass 2 step 1 — junk rows deleted (96,433) |
| `catalog_genre_applied.csv` | After Pass 2 step 3 — `genre_resolved` column added |
| `map_genres.py` | Strict canonical genre map — imported by apply/backfill scripts |
| `apply_genres.py` | Applies genre map + tags fallback, produces `catalog_genre_applied.csv` |
| `delete_rows.py` | Pass 2 step 1 — deletes junk genre rows |
| `backfill_genres.py` | Pass 2 step 4 — writes resolved genres to DynamoDB |
| `probe_tags.py` | Audit script — tags field coverage and top token vocabulary |
| `tags_audit.txt` | Output of probe_tags.py |
| `genre_audit.txt` | All 3,616 distinct genre values with counts and platform breakdown |
| `genre_mapping.txt` | Full mapping table — every raw value → canonical or unresolved |
| `genre_unresolved.txt` | Post-apply unresolved genre values with counts |
