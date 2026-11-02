/**
 * api.js — static JSON backend
 *
 * Data lives in /data/ on GitHub Pages:
 *   data/genre/<genre>.json   — tracks by canonical genre
 *   data/type/<type>.json     — tracks by content_type (no music — use genre)
 *   data/search-index.json    — {track_id, title, artist_name} for Fuse.js
 *   data/index.json           — manifest
 *
 * All functions return { results: [], total } to match the InfiniteScroll contract.
 */

export const PAGE_SIZE = 20;

// ── Language filter ───────────────────────────────────────

let _lang = localStorage.getItem('music_lang') || 'eng';
export function getLang() { return _lang; }
export function setLang(val) { _lang = val; localStorage.setItem('music_lang', val); }

function _langMatch(track) {
  if (_lang === 'all') return true;
  return !track.language || track.language === 'eng';
}

// ── Chunk cache — load each file once ────────────────────

const _cache = {};

async function _load(path) {
  if (_cache[path]) return _cache[path];
  const base = window.location.pathname.startsWith('/music') ? '/music' : '';
  const res = await fetch(`${base}/${path}`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  _cache[path] = await res.json();
  return _cache[path];
}

function _page(tracks, offset) {
  const filtered = tracks.filter(_langMatch);
  return {
    results: filtered.slice(offset, offset + PAGE_SIZE),
    total:   filtered.length,
  };
}

// ── Public API ────────────────────────────────────────────

/** Genre filter — loads data/genre/<genre>.json */
export async function searchByGenre(genre, limit = PAGE_SIZE, offset = 0) {
  const tracks = await _load(`data/genre/${genre.toLowerCase()}.json`);
  return _page(tracks, offset);
}

/** Content type filter — loads data/type/<type>.json */
export async function searchByType(type, limit = PAGE_SIZE, offset = 0) {
  const tracks = await _load(`data/type/${type}.json`);
  return _page(tracks, offset);
}

/** Text search — Fuse.js against search-index, then hydrate from genre/type chunks */
export async function searchTracks(query, limit = PAGE_SIZE, offset = 0) {
  if (!query?.trim()) return { results: [], total: 0 };

  const index = await _load('data/search-index.json');

  // Lazy-load Fuse from CDN
  if (!window.Fuse) {
    await _loadScript('https://cdn.jsdelivr.net/npm/fuse.js@7/dist/fuse.min.js');
  }

  const fuse = new window.Fuse(index, {
    keys: ['title', 'artist_name'],
    threshold: 0.35,
    distance: 100,
  });

  const hits = fuse.search(query).map(r => r.item);
  const filtered = hits.filter(h => {
    // language filter — search index doesn't have language, so we can't filter here
    // full track objects are returned from _hydrate which has language
    return true;
  });

  const page = filtered.slice(offset, offset + PAGE_SIZE);
  const hydrated = await _hydrateMany(page);
  const langFiltered = hydrated.filter(_langMatch);

  return { results: langFiltered, total: filtered.length };
}

/** Radio — load genre chunk, shuffle, return limit tracks */
export async function getRadio(genre, limit = 50) {
  const tracks = await _load(`data/genre/${genre.toLowerCase()}.json`);
  const filtered = tracks.filter(_langMatch);
  const shuffled = [...filtered].sort(() => Math.random() - 0.5);
  return { tracks: shuffled.slice(0, limit) };
}

/** Stats — from index.json manifest */
export async function getStats() {
  return _load('data/index.json');
}

// ── Hydration — look up full track objects from chunks ────

// Build a flat lookup map lazily
let _trackMap = null;

async function _buildTrackMap() {
  if (_trackMap) return _trackMap;
  const index = await _load('data/index.json');
  _trackMap = {};

  // Load all genre chunks and type chunks to build the map
  const genreLoads = Object.keys(index.genres).map(g =>
    _load(`data/genre/${g}.json`).then(tracks => {
      tracks.forEach(t => { _trackMap[t.track_id] = t; });
    })
  );
  const typeLoads = Object.keys(index.types).map(c =>
    _load(`data/type/${c}.json`).then(tracks => {
      tracks.forEach(t => { _trackMap[t.track_id] = t; });
    })
  );
  await Promise.all([...genreLoads, ...typeLoads]);
  return _trackMap;
}

async function _hydrateMany(indexItems) {
  const map = await _buildTrackMap();
  return indexItems.map(item => map[item.track_id]).filter(Boolean);
}

// ── Utility ───────────────────────────────────────────────

function _loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}
