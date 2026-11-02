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

**Result:** ✅ Done — 56,848 SET, 39,585 REMOVE, 0 errors.

**Post-backfill issue:** `delete_rows.py` removed 785 junk rows from the CSV but those records already existed in DynamoDB and were never touched by the backfill. Verify scan (`verify_genres.py`) revealed 2,455 non-canonical genre values still live in the table.

#### Step 5 — DynamoDB non-canonical cleanup
**Script:** `cleaning/clean_noncanonical_genres.py`

Scans the live table, REMOVEs `genre` on any row whose value is not in the 15 canonical set. Catches both the 785 deleted-CSV rows and any stragglers that slipped through the tag fallback.

- Dry-run confirmed: 2,455 rows
- Dry-run by default, `--live` flag to apply

**Result:** ✅ Done — 2,455 removed, 0 errors.

---

## Pass 2 — Final Verified State (live DynamoDB)

| | Count | % |
|---|---|---|
| Total rows | 99,220 | |
| With canonical genre | 57,180 | 57.6% |
| Without genre (null) | 42,040 | 42.4% |

### Genre distribution
| Genre | Tracks |
|---|---|
| electronic | 13,079 |
| ambient | 6,908 |
| classical | 5,596 |
| hip-hop | 4,707 |
| rock | 4,674 |
| pop | 4,441 |
| jazz | 4,284 |
| experimental | 3,397 |
| reggae | 2,894 |
| blues | 2,074 |
| folk | 1,783 |
| soul | 1,553 |
| country | 833 |
| metal | 457 |
| punk | 297 |
| industrial | 203 |

**Status:** Running live.

---

## Pass 4 — duration_sec ✅ Done

**Script:** `cleaning/clean_duration.py`
**Input:** `cleaning/catalog_clean_unknown.csv`
**Output:** `cleaning/catalog_final.csv`

Decision: null out zeros, accept the missing gap. Duration is display-only — a missing value shows blank in the UI, the track still plays.

| | Count |
|---|---|
| Has duration_sec | 75,434 |
| Missing (accepted gap) | 20,904 — 99.9% IA |
| Zero → nulled | 265 |
| Over 1hr (valid) | 1,400 — radio recordings, experimental long-form |

**Final catalog:** `catalog_final.csv` — 96,338 rows, all passes complete.

---

## Pass 3 — Duplicates & Unidentifiable Tracks ✅ Done

#### Step 1 — True duplicate check (stream_url)
**Script:** `cleaning/probe_true_dupes.py`

Checked for duplicate `stream_url` values — the only reliable signal of a true duplicate (same file ingested from multiple IA collections).

| | Count |
|---|---|
| Duplicate stream_url groups | 0 |
| Extra rows to delete | 0 |

Title overlaps (e.g. 71x "None Legible", 7x "The Lost Chord") are all legitimate — different recordings of the same public domain songs across different IA collections. Not duplicates.

#### Step 2 — Unidentifiable tracks
**Script:** `cleaning/delete_unknown.py`
**Input:** `cleaning/catalog_genre_applied.csv`
**Output:** `cleaning/catalog_clean_unknown.csv`

Deleted rows where both `title` AND `artist_name` were unknown/blank — no way to display these in the UI.

Unknown values matched: `unknown artist`, `unknown`, `""`, `-`, `none legible`, `none listed`

| | Count |
|---|---|
| Deleted | 95 |
| Kept | 96,338 |

All 95 were `internet_archive`, 80 had no genre either. Not worth adding an `other` content type chip to the UI for 95 unidentifiable tracks.

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
| `clean_noncanonical_genres.py` | Pass 2 step 5 — REMOVEs any non-canonical genre still in DynamoDB |
| `verify_genres.py` | Verification script — scans live table, reports genre distribution |
| `probe_tags.py` | Audit script — tags field coverage and top token vocabulary |
| `probe_dupes.py` | Pass 3 — duplicate probe by title+artist+platform |
| `report_dupes.py` | Pass 3 — dupe group detail report with stream_urls |
| `probe_true_dupes.py` | Pass 3 — true duplicate check by stream_url |
| `probe_unknown.py` | Pass 3 — unidentifiable track probe (unknown title+artist) |
| `delete_unknown.py` | Pass 3 — deletes unidentifiable tracks from DynamoDB + writes cleaned CSV |
| `catalog_clean_unknown.csv` | After Pass 3 — unidentifiable rows deleted (96,338) |
| `probe_duration.py` | Pass 4 — missing duration_sec probe by platform and content_type |
| `probe_duration_outliers.py` | Pass 4 — zero and outlier duration probe |
| `clean_duration.py` | Pass 4 — nulls zero duration_sec in DynamoDB + writes final CSV |
| `catalog_final.csv` | 🏁 Final clean catalog — 96,338 rows, all passes complete |
| `tags_audit.txt` | Output of probe_tags.py |
| `genre_audit.txt` | All 3,616 distinct genre values with counts and platform breakdown |
| `genre_mapping.txt` | Full mapping table — every raw value → canonical or unresolved |
| `genre_unresolved.txt` | Post-apply unresolved genre values with counts |
