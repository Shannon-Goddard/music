import { searchTracks } from '../api.js';
import { InfiniteScroll } from '../scroll.js';
import { playQueue } from '../player.js';
import { isSaved, toggleSaved } from '../library.js';
import { artThumb } from '../utils.js';
import en from '../i18n/en.js';

export async function render(app, query) {
  app.innerHTML = `
    <div id="sticky-count-bar" aria-live="polite">
      <p id="results-count" class="text-xs text-white/40"></p>
      <button id="btn-play-all"
              class="flex items-center gap-1.5 text-xs font-medium text-accent hover:opacity-80 transition">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        Play all
      </button>
    </div>
    <div class="flex items-baseline justify-between mb-5">
      <h2 class="text-base font-semibold">Results for <span class="text-accent">${_esc(query)}</span></h2>
    </div>
    <div id="search-filters" class="hidden">
      <div class="mb-3">
        <p class="section-label">Artist</p>
        <div id="artist-chips" class="scroll-row"></div>
      </div>
      <div id="album-filter" class="mb-4 hidden">
        <p class="section-label">Album</p>
        <div id="album-chips" class="scroll-row"></div>
      </div>
    </div>
    <div id="results" class="space-y-2"></div>
    <p id="results-status" class="text-xs text-center py-4"></p>
  `;

  // Accumulated tracks across all pages for queue + client-side filtering
  let allTracks    = [];
  let activeArtist = null;
  let activeAlbum  = null;
  let artistMap    = {};

  const listEl   = document.getElementById('results');
  const statusEl = document.getElementById('results-status');

  const scroller = new InfiniteScroll({
    listEl,
    statusEl,
    fetchFn: (offset) => searchTracks(query, 20, offset),
    renderFn: (tracks, offset) => {
      allTracks = allTracks.slice(0, offset).concat(tracks);
      artistMap = _buildArtistMap(allTracks);

      // Append rows
      listEl.insertAdjacentHTML('beforeend', tracks.map((t, i) => _trackRow(t, offset + i)).join(''));

      // Show sticky count bar once first results arrive
      const bar = document.getElementById('sticky-count-bar');
      if (bar) bar.style.display = 'flex';

      // Rebuild artist chips after each page
      const artists = Object.keys(artistMap).sort();
      if (artists.length > 1) {
        document.getElementById('search-filters').classList.remove('hidden');
        _renderArtistChips(artists, activeArtist);
      }
      _updateCount(allTracks.length, activeArtist, activeAlbum, artistMap);
    },
  });

  scroller.start();

  // ── Artist chip clicks ──────────────────────────────────
  document.getElementById('artist-chips').addEventListener('click', e => {
    const chip = e.target.closest('[data-artist]');
    if (!chip) return;
    const artist = chip.dataset.artist;

    if (activeArtist === artist) {
      activeArtist = null; activeAlbum = null;
      _setActiveChip(null, '#artist-chips');
      document.getElementById('album-filter').classList.add('hidden');
      _renderFilteredTracks(allTracks);
    } else {
      activeArtist = artist; activeAlbum = null;
      _setActiveChip(chip, '#artist-chips');
      const albums = Object.keys(artistMap[artist] || {}).sort();
      if (albums.length > 1) {
        _renderAlbumChips(albums, null);
        document.getElementById('album-filter').classList.remove('hidden');
      } else {
        document.getElementById('album-filter').classList.add('hidden');
      }
      _renderFilteredTracks(_tracksForArtist(artistMap, artist));
    }
    _updateCount(allTracks.length, activeArtist, activeAlbum, artistMap);
  });

  // ── Album chip clicks ───────────────────────────────────
  document.getElementById('album-chips').addEventListener('click', e => {
    const chip = e.target.closest('[data-album]');
    if (!chip) return;
    const album = chip.dataset.album;

    if (activeAlbum === album) {
      activeAlbum = null;
      _setActiveChip(null, '#album-chips');
      _renderFilteredTracks(_tracksForArtist(artistMap, activeArtist));
    } else {
      activeAlbum = album;
      _setActiveChip(chip, '#album-chips');
      _renderFilteredTracks(artistMap[activeArtist][album]);
    }
    _updateCount(allTracks.length, activeArtist, activeAlbum, artistMap);
  });

  // ── Play all ────────────────────────────────────────────
  document.getElementById('btn-play-all').addEventListener('click', () => {
    const tracks = _currentTracks(artistMap, activeArtist, activeAlbum, allTracks);
    if (tracks.length) playQueue(tracks, 0);
  });

  // ── Track row clicks ────────────────────────────────────
  listEl.addEventListener('click', e => {
    const save = e.target.closest('[data-save]');
    if (save) {
      e.stopPropagation();
      const track = allTracks.find(t => t.track_id === save.dataset.save);
      if (track) {
        const nowSaved = toggleSaved(track);
        save.classList.toggle('text-accent', nowSaved);
        save.classList.toggle('text-white/20', !nowSaved);
        save.querySelector('svg').setAttribute('fill', nowSaved ? 'currentColor' : 'none');
      }
      return;
    }
    const row = e.target.closest('[data-index]');
    if (!row) return;
    const tracks = _currentTracks(artistMap, activeArtist, activeAlbum, allTracks);
    playQueue(tracks, parseInt(row.dataset.index));
  });
}

// ── Render helpers ────────────────────────────────────────

function _renderArtistChips(artists, active) {
  document.getElementById('artist-chips').innerHTML =
    artists.map(a => `<button data-artist="${_esc(a)}" class="${a === active ? 'chip-active' : 'chip'}">${_esc(a)}</button>`).join('');
}

function _renderAlbumChips(albums, active) {
  document.getElementById('album-chips').innerHTML =
    albums.map(a => `<button data-album="${_esc(a)}" class="${a === active ? 'chip-active' : 'chip'}">${_esc(a)}</button>`).join('');
}

function _renderFilteredTracks(tracks) {
  document.getElementById('results').innerHTML = tracks.map((t, i) => _trackRow(t, i)).join('');
}

function _updateCount(total, activeArtist, activeAlbum, artistMap) {
  const filtered = _currentTracks(artistMap, activeArtist, activeAlbum, []).length;
  const el = document.getElementById('results-count');
  if (!el) return;
  if (activeArtist || activeAlbum) {
    el.textContent = `${filtered} of ${total.toLocaleString()} loaded`;
  } else {
    el.textContent = `${total.toLocaleString()} loaded`;
  }
}

function _setActiveChip(activeEl, containerSelector) {
  document.querySelectorAll(`${containerSelector} [data-artist], ${containerSelector} [data-album]`).forEach(b => {
    b.className = 'chip';
  });
  if (activeEl) activeEl.className = 'chip-active';
}

// ── Data helpers ──────────────────────────────────────────

/** Build { artistName: { albumTitle: [tracks] } } */
function _buildArtistMap(tracks) {
  return tracks.reduce((map, track) => {
    const artist = track.artist_name || 'Unknown Artist';
    const album  = track.album_title  || 'Unknown Album';
    if (!map[artist])        map[artist] = {};
    if (!map[artist][album]) map[artist][album] = [];
    map[artist][album].push(track);
    return map;
  }, {});
}

function _tracksForArtist(artistMap, artist) {
  return Object.values(artistMap[artist] || {}).flat();
}

function _currentTracks(artistMap, activeArtist, activeAlbum, allTracks) {
  if (activeArtist && activeAlbum) return artistMap[activeArtist][activeAlbum] || [];
  if (activeArtist)                return _tracksForArtist(artistMap, activeArtist);
  return allTracks;
}

// ── Track row ─────────────────────────────────────────────

function _trackRow(track, index) {
  const duration = track.duration_sec ? _fmt(track.duration_sec) : '';
  const saved = _isSaved(track.track_id);
  return `
    <div data-index="${index}" data-track-id="${_esc(track.track_id)}"
         class="card flex items-center gap-3 p-3 rounded-lg bg-card cursor-pointer hover:bg-raised transition"
         style="border:1px solid rgba(255,255,255,0.06)">
      <div class="shrink-0">${artThumb(track)}</div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium truncate">${_esc(track.title)}</p>
        <p class="text-xs text-white/40 truncate">${_esc(track.album_title || '')}</p>
      </div>
      <span class="text-xs text-white/25 tabular-nums shrink-0">${duration}</span>
      <button data-save="${_esc(track.track_id)}" aria-label="Save to library"
              class="shrink-0 p-1 transition hover:scale-110 ${saved ? 'text-accent' : 'text-white/20 hover:text-white/60'}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="${saved ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
      </button>
    </div>
  `;
}

// ── Utilities ─────────────────────────────────────────────

function _isSaved(track_id) { return isSaved(track_id); }

function _fmt(sec) {
  sec = parseFloat(sec);
  if (isNaN(sec)) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function _skeletons(n) {
  return Array.from({ length: n }, () => `<div class="skeleton h-16 w-full"></div>`).join('');
}

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
