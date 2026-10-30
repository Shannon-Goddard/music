const CACHE_NAME = 'music-shell-v2';
const AUDIO_CACHE = 'music-audio-v1';
const BASE = '/music';

const SHELL_ASSETS = [
  `${BASE}/`,
  `${BASE}/index.html`,
  `${BASE}/css/app.css`,
  `${BASE}/js/app.js`,
  `${BASE}/js/player.js`,
  `${BASE}/js/queue.js`,
  `${BASE}/js/scroll.js`,
  `${BASE}/js/library.js`,
  `${BASE}/js/api.js`,
  `${BASE}/js/i18n/en.js`,
  `${BASE}/js/views/home.js`,
  `${BASE}/js/views/search.js`,
  `${BASE}/js/views/library.js`,
  `${BASE}/manifest.json`,
];

// ── Install: cache the UI shell ───────────────────────────

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ────────────────────────

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME && k !== AUDIO_CACHE)
            .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: shell from cache, audio pre-cached, API network-first ─

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Audio streams — serve from cache if available, else network
  if (url.hostname === 'archive.org' && url.pathname.endsWith('.mp3')) {
    event.respondWith(_cacheFirst(request, AUDIO_CACHE));
    return;
  }

  // API calls — always network, no cache
  if (url.hostname.includes('execute-api.amazonaws.com')) {
    event.respondWith(fetch(request));
    return;
  }

  // Shell assets — cache first
  event.respondWith(_cacheFirst(request, CACHE_NAME));
});

async function _cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

// ── Pre-cache next tracks in queue (called from player.js) ─

self.addEventListener('message', event => {
  if (event.data?.type === 'PRECACHE_AUDIO') {
    const urls = event.data.urls || [];
    caches.open(AUDIO_CACHE).then(cache => {
      urls.forEach(url => {
        cache.match(url).then(hit => {
          if (!hit) fetch(url).then(r => { if (r.ok) cache.put(url, r); });
        });
      });
    });
  }
});
