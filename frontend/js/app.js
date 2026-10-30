import './player.js';
import { render as renderHome } from './views/home.js';
import { render as renderSearch } from './views/search.js';
import { render as renderLibrary } from './views/library.js';
import { togglePlay } from './player.js';

const app = document.getElementById('app');

// ── Router ────────────────────────────────────────────────

async function route() {
  const hash = location.hash || '#/';
  const [path, ...rest] = hash.slice(1).split('?');
  const params = Object.fromEntries(new URLSearchParams(rest.join('?')));

  if (document.startViewTransition) {
    document.startViewTransition(() => _dispatch(path, params));
  } else {
    _dispatch(path, params);
  }
}

async function _dispatch(path, params) {
  app.innerHTML = '';

  // Update active nav state
  document.querySelectorAll('.nav-link, .bottom-nav-item').forEach(el => {
    const href = el.getAttribute('href');
    el.classList.toggle('active', href === `#${path}` || (href === '#/' && (path === '/' || path === '')));
  });

  if (path === '/' || path === '') {
    await renderHome(app);
  } else if (path === '/search') {
    await renderSearch(app, params.q || '');
  } else if (path === '/library') {
    renderLibrary(app);
  } else {
    app.innerHTML = `<p class="text-white/50 mt-12 text-center">Page not found.</p>`;
  }
}

// ── Search form ───────────────────────────────────────────

document.getElementById('search-form').addEventListener('submit', e => {
  e.preventDefault();
  const q = document.getElementById('search-input').value.trim();
  if (q) location.hash = `#/search?q=${encodeURIComponent(q)}`;
});

// ── Theme: respect system preference on first load ────────

if (!localStorage.getItem('music_theme')) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.classList.toggle('dark', prefersDark);
} else {
  document.documentElement.classList.toggle('dark', localStorage.getItem('music_theme') === 'dark');
}

// ── Service Worker registration ───────────────────────────

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/music/service-worker.js').catch(e => {
    console.warn('SW registration failed:', e);
  });
}

// ── Keyboard shortcuts ──────────────────────────────────

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const audio = document.getElementById('audio');
  switch (e.key) {
    case ' ':
      e.preventDefault();
      togglePlay();
      break;
    case 'ArrowRight':
      e.preventDefault();
      if (audio.duration) audio.currentTime = Math.min(audio.currentTime + 10, audio.duration);
      break;
    case 'ArrowLeft':
      e.preventDefault();
      audio.currentTime = Math.max(audio.currentTime - 10, 0);
      break;
    case 'n': case 'N':
      document.getElementById('btn-next').click();
      break;
    case 'p': case 'P':
      document.getElementById('btn-prev').click();
      break;
  }
});

// ── Now playing row indicator ─────────────────────────────

document.addEventListener('trackchange', e => {
  document.querySelectorAll('[data-track-id]').forEach(row => {
    row.classList.toggle('now-playing', row.dataset.trackId === e.detail.track_id);
  });
});

// ── Boot ──────────────────────────────────────────────────

window.addEventListener('hashchange', route);
route();
