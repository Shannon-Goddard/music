import { getSaved, toggleSaved } from '../library.js';
import { playQueue } from '../player.js';
import { artThumb } from '../utils.js';
import en from '../i18n/en.js';

export function render(app) {
  const tracks = getSaved();

  app.innerHTML = `
    <div class="flex items-center justify-between mb-5">
      <h2 class="text-base font-semibold">Library</h2>
      ${tracks.length ? `
        <button id="btn-play-library"
                class="flex items-center gap-1.5 text-xs font-medium text-accent hover:opacity-80 transition">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Play all
        </button>` : ''}
    </div>
    ${tracks.length
      ? `<div id="library-list" class="space-y-2">
           ${tracks.map((t, i) => _trackRow(t, i)).join('')}
         </div>`
      : `<div class="flex flex-col items-center justify-center py-20 gap-3 text-white/30">
           <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
             <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
           </svg>
           <p class="text-sm">${en.library_empty}</p>
         </div>`
    }
  `;

  if (!tracks.length) return;

  document.getElementById('btn-play-library')?.addEventListener('click', () => {
    playQueue(tracks, 0);
  });

  document.getElementById('library-list').addEventListener('click', e => {
    const save = e.target.closest('[data-save]');
    if (save) {
      e.stopPropagation();
      const track = tracks.find(t => t.track_id === save.dataset.save);
      if (track) {
        toggleSaved(track);
        // Re-render since removing a saved track changes the list
        render(app);
      }
      return;
    }
    const row = e.target.closest('[data-index]');
    if (row) playQueue(tracks, parseInt(row.dataset.index));
  });
}

function _trackRow(track, index) {
  const duration = track.duration_sec ? _fmt(track.duration_sec) : '';
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
        <p class="text-xs text-white/40 truncate">${_esc(track.artist_name)} · ${_esc(track.album_title || '')}</p>
      </div>
      <span class="text-xs text-white/25 tabular-nums shrink-0">${duration}</span>
      <button data-info="${info}" aria-label="Track info" onclick="event.stopPropagation();openInfo(this.dataset.info)"
              class="shrink-0 p-1 text-white/20 hover:text-white/60 transition">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      </button>
      <button data-save="${_esc(track.track_id)}" aria-label="Remove from library"
              class="shrink-0 p-1 text-accent transition hover:scale-110">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
      </button>
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

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
