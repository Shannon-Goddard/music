import { searchTracks } from '../api.js';
import { playQueue } from '../player.js';
import en from '../i18n/en.js';

export async function render(app, query) {
  app.innerHTML = `
    <h2 class="text-lg font-semibold mb-4">Results for <span class="text-accent">"${_esc(query)}"</span></h2>
    <div id="results" class="space-y-2">
      ${_skeletons(5)}
    </div>
  `;

  let data;
  try {
    data = await searchTracks(query);
  } catch {
    document.getElementById('results').innerHTML =
      `<p class="text-white/50">${en.search_error}</p>`;
    return;
  }

  const { results = [] } = data;

  if (!results.length) {
    document.getElementById('results').innerHTML =
      `<p class="text-white/50">${en.search_no_results} "${_esc(query)}"</p>`;
    return;
  }

  document.getElementById('results').innerHTML = results.map((t, i) =>
    _trackRow(t, i)
  ).join('');

  // Wire up click to play entire result set as a queue
  document.getElementById('results').addEventListener('click', e => {
    const row = e.target.closest('[data-index]');
    if (!row) return;
    playQueue(results, parseInt(row.dataset.index));
  });
}

function _trackRow(track, index) {
  const duration = track.duration_sec ? _fmt(track.duration_sec) : '';
  const art = track.cover_art_url
    ? `<img src="${_esc(track.cover_art_url)}" class="w-10 h-10 rounded object-cover bg-white/10" alt="" />`
    : `<div class="w-10 h-10 rounded bg-white/10 flex items-center justify-center text-white/30 text-lg">♪</div>`;

  return `
    <div data-index="${index}"
         class="card flex items-center gap-3 p-3 rounded-lg bg-card cursor-pointer hover:bg-white/10 transition">
      ${art}
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium truncate">${_esc(track.title)}</p>
        <p class="text-xs text-white/50 truncate">${_esc(track.artist_name)} · ${_esc(track.album_title)}</p>
      </div>
      <div class="flex items-center gap-3 text-xs text-white/40">
        <span>${_esc(track.genre || '')}</span>
        <span>${duration}</span>
      </div>
    </div>
  `;
}

function _fmt(sec) {
  sec = parseFloat(sec);
  if (isNaN(sec)) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function _skeletons(n) {
  return Array.from({ length: n }, () =>
    `<div class="skeleton h-16 w-full"></div>`
  ).join('');
}

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
