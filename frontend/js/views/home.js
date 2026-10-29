import { searchByGenre } from '../api.js';
import { playQueue } from '../player.js';
import { loadSession } from '../queue.js';
import en from '../i18n/en.js';

const GENRES = ['music', 'electronic', 'rock', 'experimental', 'ambient', 'blues', 'jazz', 'industrial'];
const MOODS = [
  { label: '⚡ Energetic', value: 'energetic' },
  { label: '😌 Calm',      value: 'calm' },
  { label: '🌙 Melancholic', value: 'melancholic' },
  { label: '🎉 Happy',     value: 'happy' },
  { label: '🎸 Intense',   value: 'intense' },
];

export async function render(app) {
  const session = loadSession();
  const recentRaw = _loadRecent();

  app.innerHTML = `
    ${session.track_id ? _resumeBar(session) : ''}

    ${recentRaw.length ? `
      <section class="mb-8">
        <h2 class="text-sm font-semibold text-white/50 uppercase tracking-wider mb-3">${en.home_recent}</h2>
        <div class="scroll-row">
          ${recentRaw.map((t, i) => _miniCard(t, i, 'recent')).join('')}
        </div>
      </section>` : ''}

    <section class="mb-8">
      <h2 class="text-sm font-semibold text-white/50 uppercase tracking-wider mb-3">${en.home_genre}</h2>
      <div class="scroll-row">
        ${GENRES.map(g => _genreCard(g)).join('')}
      </div>
    </section>

    <section class="mb-8">
      <h2 class="text-sm font-semibold text-white/50 uppercase tracking-wider mb-3">${en.home_mood}</h2>
      <div class="scroll-row">
        ${MOODS.map(m => _moodCard(m)).join('')}
      </div>
    </section>

    <section id="genre-results" class="mb-8 hidden">
      <h2 id="genre-results-title" class="text-sm font-semibold text-white/50 uppercase tracking-wider mb-3"></h2>
      <div id="genre-results-list" class="space-y-2">${_skeletons(5)}</div>
    </section>
  `;

  // Genre card click
  app.querySelectorAll('[data-genre]').forEach(el => {
    el.addEventListener('click', () => _loadGenre(el.dataset.genre));
  });

  // Recent track click
  app.querySelectorAll('[data-recent]').forEach(el => {
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.recent);
      playQueue(recentRaw, idx);
    });
  });

  // Resume button
  app.querySelector('#btn-resume')?.addEventListener('click', () => {
    const tracks = JSON.parse(localStorage.getItem('music_queue') || '{}').queue || [];
    if (tracks.length) playQueue(tracks, 0);
  });
}

async function _loadGenre(genre) {
  const section = document.getElementById('genre-results');
  const title = document.getElementById('genre-results-title');
  const list = document.getElementById('genre-results-list');

  section.classList.remove('hidden');
  title.textContent = genre;
  list.innerHTML = _skeletons(5);

  try {
    const data = await searchByGenre(genre, 20);
    const results = data.results || [];
    if (!results.length) {
      list.innerHTML = `<p class="text-white/50">No tracks found for ${genre}</p>`;
      return;
    }
    list.innerHTML = results.map((t, i) => _trackRow(t, i)).join('');
    list.addEventListener('click', e => {
      const row = e.target.closest('[data-index]');
      if (row) playQueue(results, parseInt(row.dataset.index));
    });
  } catch {
    list.innerHTML = `<p class="text-white/50">${en.search_error}</p>`;
  }
}

function _resumeBar(session) {
  return `
    <div class="flex items-center justify-between bg-card rounded-lg px-4 py-3 mb-6">
      <p class="text-sm">${en.home_continue}</p>
      <button id="btn-resume" class="text-sm text-accent font-medium hover:underline">Resume ▶</button>
    </div>
  `;
}

function _genreCard(genre) {
  const colors = ['bg-purple-900','bg-blue-900','bg-green-900','bg-yellow-900','bg-red-900','bg-pink-900','bg-indigo-900','bg-teal-900'];
  const color = colors[Math.abs(_hash(genre)) % colors.length];
  return `
    <button data-genre="${genre}"
      class="card flex-shrink-0 w-32 h-20 ${color} rounded-lg flex items-end p-3 font-semibold text-sm hover:opacity-90 transition">
      ${genre}
    </button>
  `;
}

function _moodCard({ label, value }) {
  return `
    <button data-genre="${value}"
      class="card flex-shrink-0 px-4 py-2 bg-card rounded-full text-sm hover:bg-white/10 transition">
      ${label}
    </button>
  `;
}

function _miniCard(track, index, type) {
  const art = track.cover_art_url
    ? `<img src="${_esc(track.cover_art_url)}" class="w-full h-full object-cover" alt="" />`
    : `<div class="w-full h-full bg-white/10 flex items-center justify-center text-2xl">♪</div>`;
  return `
    <button data-${type}="${index}"
      class="card flex-shrink-0 w-36 text-left">
      <div class="w-36 h-36 rounded-lg overflow-hidden mb-2">${art}</div>
      <p class="text-xs font-medium truncate">${_esc(track.title)}</p>
      <p class="text-xs text-white/40 truncate">${_esc(track.artist_name)}</p>
    </button>
  `;
}

function _trackRow(track, index) {
  return `
    <div data-index="${index}"
         class="card flex items-center gap-3 p-3 rounded-lg bg-card cursor-pointer hover:bg-white/10 transition">
      <div class="w-10 h-10 rounded bg-white/10 flex items-center justify-center text-white/30">♪</div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium truncate">${_esc(track.title)}</p>
        <p class="text-xs text-white/50 truncate">${_esc(track.artist_name)}</p>
      </div>
    </div>
  `;
}

function _loadRecent() {
  try {
    return JSON.parse(localStorage.getItem('music_recent')) || [];
  } catch { return []; }
}

function _skeletons(n) {
  return Array.from({ length: n }, () => `<div class="skeleton h-16 w-full"></div>`).join('');
}

function _hash(str) {
  return str.split('').reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0);
}

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
