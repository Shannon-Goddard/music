import { searchByGenre, searchByType, getRadio } from '../api.js';
import { InfiniteScroll } from '../scroll.js';
import { playQueue } from '../player.js';
import { playAt } from '../player.js';
import { loadSession } from '../queue.js';
import { isSaved, toggleSaved } from '../library.js';
import { artThumb, coverGradient } from '../utils.js';
import en from '../i18n/en.js';

const GENRES = ['Electronic', 'Rock', 'Ambient', 'Experimental', 'Blues', 'Jazz', 'Industrial', 'Classical', 'Hip-Hop', 'Folk'];

const MOODS = [
  { label: 'Energetic', value: 'energetic' },
  { label: 'Calm',      value: 'calm' },
  { label: 'Melancholic', value: 'melancholic' },
  { label: 'Happy',     value: 'happy' },
  { label: 'Intense',   value: 'intense' },
];

const CONTENT_TYPES = [
  { label: 'Music',      value: 'music',      icon: _svgMusic() },
  { label: 'Podcasts',   value: 'podcast',    icon: _svgMic() },
  { label: 'Interviews', value: 'interview',  icon: _svgMic() },
  { label: 'Lectures',   value: 'lecture',    icon: _svgBook() },
  { label: 'Audiobooks', value: 'audiobook',  icon: _svgBook() },
  { label: 'Other',      value: 'other',      icon: _svgDots() },
];

export async function render(app) {
  const session = loadSession();
  const recentRaw = _loadRecent();

  app.innerHTML = `
    ${session.track_id ? _resumeBar(session) : ''}

    ${recentRaw.length ? `
      <section class="mb-8">
        <h2 class="section-label">${en.home_recent}</h2>
        <div class="scroll-row">
          ${recentRaw.map((t, i) => _miniCard(t, i, 'recent')).join('')}
        </div>
      </section>` : ''}

    <section class="mb-8">
      <h2 class="section-label">Type</h2>
      <div class="scroll-row">
        ${CONTENT_TYPES.map(t => _typeChip(t)).join('')}
      </div>
    </section>

    <section class="mb-8">
      <h2 class="section-label">${en.home_genre}</h2>
      <div class="scroll-row">
        ${GENRES.map(g => _chip({ label: g, attr: 'data-genre', value: g.toLowerCase() })).join('')}
      </div>
    </section>

    <section class="mb-8">
      <h2 class="section-label">Radio</h2>
      <div class="scroll-row">
        ${GENRES.map(g => _radioChip(g)).join('')}
      </div>
    </section>

    <section class="mb-8">
      <h2 class="section-label">${en.home_mood}</h2>
      <div class="scroll-row">
        ${MOODS.map(m => _chip({ label: m.label, attr: 'data-genre', value: m.value })).join('')}
      </div>
    </section>

    <section id="genre-results" class="mb-8 hidden">
      <h2 id="genre-results-title" class="section-label"></h2>
      <div id="sticky-count-bar" aria-live="polite">
        <p id="results-count" class="text-xs text-white/40"></p>
        <button id="btn-play-all"
                class="flex items-center gap-1.5 text-xs font-medium text-accent hover:opacity-80 transition">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Play all
        </button>
      </div>
      <div id="genre-results-list" class="space-y-2">${_skeletons(5)}</div>
      <p id="genre-results-status" class="text-xs text-center py-4"></p>
    </section>

    <div id="home-empty" class="flex flex-col items-center justify-center py-16 gap-3 text-white/20">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <p class="text-sm">Pick a filter above or search to start listening</p>
    </div>
  `;

  let activeScroll = null;

  app.querySelectorAll('[data-type]').forEach(el => {
    el.addEventListener('click', () => {
      _setActive(el, '[data-type]');
      activeScroll?.destroy();
      activeScroll = _loadPaged(
        (offset) => searchByType(el.dataset.type, 20, offset),
        el.dataset.label
      );
    });
  });

  app.querySelectorAll('[data-genre]').forEach(el => {
    el.addEventListener('click', () => {
      _setActive(el, '[data-genre]');
      activeScroll?.destroy();
      activeScroll = _loadPaged(
        (offset) => searchByGenre(el.dataset.genre, 20, offset),
        el.dataset.genre
      );
    });
  });

  app.querySelectorAll('[data-radio]').forEach(el => {
    el.addEventListener('click', () => {
      _setActive(el, '[data-radio]');
      _startRadio(el.dataset.radio);
    });
  });

  app.querySelectorAll('[data-recent]').forEach(el => {
    el.addEventListener('click', () => playQueue(recentRaw, parseInt(el.dataset.recent)));
  });

  app.querySelector('#btn-resume')?.addEventListener('click', () => {
    if (session.track) {
      playAt(session.track, session.position_sec || 0);
    } else {
      const tracks = JSON.parse(localStorage.getItem('music_queue') || '{}').queue || [];
      if (tracks.length) playQueue(tracks, 0);
    }
  });
}

function _setActive(el, selector) {
  document.querySelectorAll(selector).forEach(b => {
    b.classList.remove('chip-active');
    b.classList.add('chip');
  });
  el.classList.add('chip-active');
  el.classList.remove('chip');
}

async function _startRadio(genre) {
  const section = document.getElementById('genre-results');
  const title   = document.getElementById('genre-results-title');
  const list    = document.getElementById('genre-results-list');
  const status  = document.getElementById('genre-results-status');
  const bar     = document.getElementById('sticky-count-bar');
  document.getElementById('home-empty')?.classList.add('hidden');

  section.classList.remove('hidden');
  title.textContent = `${genre.charAt(0).toUpperCase() + genre.slice(1)} Radio`;
  list.innerHTML = _skeletons(5);
  status.textContent = '';
  if (bar) bar.style.display = 'none';

  setTimeout(() => {
    const top = section.getBoundingClientRect().top + window.scrollY - 60;
    window.scrollTo({ top, behavior: 'smooth' });
  }, 50);

  try {
    const data = await getRadio(genre, 50);
    const tracks = data.tracks || [];
    if (!tracks.length) {
      list.innerHTML = '';
      status.textContent = 'No tracks found for this genre.';
      return;
    }
    list.innerHTML = tracks.map((t, i) => _trackRow(t, i)).join('');
    status.textContent = '';
    if (bar) {
      bar.style.display = 'flex';
      const countEl = document.getElementById('results-count');
      if (countEl) countEl.textContent = `${tracks.length} tracks`;
    }
    // Wire play-all
    document.getElementById('btn-play-all')?.addEventListener('click', () => playQueue(tracks, 0));
    // Wire row clicks
    list.addEventListener('click', e => {
      const save = e.target.closest('[data-save]');
      if (save) {
        e.stopPropagation();
        const track = tracks.find(t => t.track_id === save.dataset.save);
        if (track) {
          const nowSaved = toggleSaved(track);
          save.classList.toggle('text-accent', nowSaved);
          save.classList.toggle('text-white/20', !nowSaved);
          save.querySelector('svg').setAttribute('fill', nowSaved ? 'currentColor' : 'none');
        }
        return;
      }
      const row = e.target.closest('[data-index]');
      if (row) playQueue(tracks, parseInt(row.dataset.index));
    });
    // Auto-play immediately
    playQueue(tracks, 0);
  } catch (err) {
    list.innerHTML = '';
    status.textContent = 'Failed to load radio. Try again.';
    console.error('Radio error:', err);
  }
}

function _loadPaged(fetchFn, label) {
  const section = document.getElementById('genre-results');
  const title   = document.getElementById('genre-results-title');
  const list    = document.getElementById('genre-results-list');
  const status  = document.getElementById('genre-results-status');
  document.getElementById('home-empty')?.classList.add('hidden');

  section.classList.remove('hidden');
  title.textContent = label || '';
  list.innerHTML = _skeletons(5);
  // Scroll window to the results section
  setTimeout(() => {
    const top = section.getBoundingClientRect().top + window.scrollY - 60;
    window.scrollTo({ top, behavior: 'smooth' });
  }, 50);

  // Reset sticky bar
  const bar = document.getElementById('sticky-count-bar');
  if (bar) bar.style.display = 'none';

  // Accumulated tracks for queue playback
  let allLoaded = [];

  // Play all wired after DOM exists
  document.getElementById('btn-play-all')?.addEventListener('click', () => {
    if (allLoaded.length) playQueue(allLoaded, 0);
  });

  const scroller = new InfiniteScroll({
    listEl:   list,
    statusEl: status,
    fetchFn,
    renderFn: (tracks, offset) => {
      if (offset === 0) list.innerHTML = '';
      allLoaded = allLoaded.slice(0, offset).concat(tracks);
      list.insertAdjacentHTML('beforeend', tracks.map((t, i) => _trackRow(t, offset + i)).join(''));
      // Update sticky count
      const bar = document.getElementById('sticky-count-bar');
      if (bar) {
        bar.style.display = 'flex';
        const countEl = document.getElementById('results-count');
        if (countEl) countEl.textContent = `${allLoaded.length.toLocaleString()} loaded`;
      }
    },
  });

  list.addEventListener('click', e => {
    const save = e.target.closest('[data-save]');
    if (save) {
      e.stopPropagation();
      const track = allLoaded.find(t => t.track_id === save.dataset.save);
      if (track) {
        const nowSaved = toggleSaved(track);
        save.classList.toggle('text-accent', nowSaved);
        save.classList.toggle('text-white/20', !nowSaved);
        save.querySelector('svg').setAttribute('fill', nowSaved ? 'currentColor' : 'none');
      }
      return;
    }
    const row = e.target.closest('[data-index]');
    if (row) playQueue(allLoaded, parseInt(row.dataset.index));
  });

  scroller.start();
  return scroller;
}

// ── Components ────────────────────────────────────────────

function _resumeBar(session) {
  const title = session.track?.title || 'Last session';
  const pos = session.position_sec ? _fmt(session.position_sec) : '';
  return `
    <div class="flex items-center justify-between bg-card rounded-lg px-4 py-3 mb-6" style="border:1px solid rgba(255,255,255,0.07)">
      <div class="min-w-0">
        <p class="text-xs text-white/40 mb-0.5">${en.home_continue}</p>
        <p class="text-sm font-medium truncate">${_esc(title)}${pos ? ` <span class="text-white/30 font-normal">· ${pos}</span>` : ''}</p>
      </div>
      <button id="btn-resume" class="ml-4 shrink-0 text-sm font-medium text-accent hover:opacity-80 transition">Resume</button>
    </div>
  `;
}

function _typeChip({ label, value, icon }) {
  return `
    <button data-type="${value}" data-label="${label}"
      class="chip flex items-center gap-2">
      <span class="text-white/40">${icon}</span>
      ${label}
    </button>
  `;
}

function _chip({ label, attr, value }) {
  return `<button ${attr}="${value}" class="chip">${label}</button>`;
}

function _radioChip(genre) {
  return `
    <button data-radio="${genre.toLowerCase()}" class="chip flex items-center gap-1.5">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" class="opacity-60"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      ${genre}
    </button>`;
}

function _miniCard(track, index, type) {
  const art = track.cover_art_url
    ? `<img src="${_esc(track.cover_art_url)}" class="w-full h-full object-cover" alt="" />`
    : `<div class="w-full h-full flex items-center justify-center"
            style="background:${coverGradient(track.album_id || track.track_id)}">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="rgba(255,255,255,0.25)"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/></svg>
       </div>`;
  return `
    <button data-${type}="${index}" class="card flex-shrink-0 w-36 text-left">
      <div class="w-36 h-36 rounded-lg overflow-hidden mb-2">${art}</div>
      <p class="text-xs font-medium truncate">${_esc(track.title)}</p>
      <p class="text-xs text-white/40 truncate">${_esc(track.artist_name)}</p>
    </button>
  `;
}

function _trackRow(track, index) {
  const duration = track.duration_sec ? _fmt(track.duration_sec) : '';
  const saved = _isSaved(track.track_id);
  const info = encodeURIComponent(JSON.stringify({
    title: track.title, artist_name: track.artist_name,
    license_type: track.license_type, attribution_text: track.attribution_text,
    source_url: track.source_url, stream_url: track.stream_url,
    is_downloadable: track.is_downloadable,
  }));
  return `
    <div data-index="${index}" data-track-id="${_esc(track.track_id)}"
         class="card flex items-center gap-3 p-3 rounded-lg bg-card cursor-pointer hover:bg-raised transition"
         style="border:1px solid rgba(255,255,255,0.06)">
      <div class="shrink-0">${artThumb(track)}</div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium truncate">${_esc(track.title)}</p>
        <p class="text-xs text-white/40 truncate">${_esc(track.artist_name)}</p>
      </div>
      <span class="text-xs text-white/25 tabular-nums shrink-0">${duration}</span>
      <button data-info="${info}" aria-label="Track info" onclick="event.stopPropagation();openInfo(this.dataset.info)"
              class="shrink-0 p-1 text-white/20 hover:text-white/60 transition">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      </button>
      <button data-save="${_esc(track.track_id)}" aria-label="Save to library"
              class="shrink-0 p-1 transition hover:scale-110 ${saved ? 'text-accent' : 'text-white/20 hover:text-white/60'}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="${saved ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
      </button>
    </div>
  `;
}

function _typeBadge(type) {
  return type && type !== 'music'
    ? `<span class="text-[11px] text-white/30 shrink-0 font-medium tracking-wide uppercase">${type}</span>`
    : '';
}

// ── SVG icons ─────────────────────────────────────────────

function _svgMusic() {
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/></svg>`;
}

function _svgMic() {
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`;
}

function _svgBook() {
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`;
}

function _svgDots() {
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>`;
}

function _isSaved(track_id) { return isSaved(track_id); }

function _fmt(sec) {
  sec = parseFloat(sec);
  if (isNaN(sec)) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function _loadRecent() {
  try { return JSON.parse(localStorage.getItem('music_recent')) || []; }
  catch { return []; }
}

function _skeletons(n) {
  return Array.from({ length: n }, () => `<div class="skeleton h-16 w-full"></div>`).join('');
}

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
