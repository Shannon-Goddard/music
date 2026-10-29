import './player.js';
import { render as renderHome } from './views/home.js';
import { render as renderSearch } from './views/search.js';

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

  if (path === '/' || path === '') {
    await renderHome(app);
  } else if (path === '/search') {
    await renderSearch(app, params.q || '');
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
  navigator.serviceWorker.register('/service-worker.js').catch(e => {
    console.warn('SW registration failed:', e);
  });
}

// ── Boot ──────────────────────────────────────────────────

window.addEventListener('hashchange', route);
route();
