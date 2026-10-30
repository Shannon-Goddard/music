/**
 * Deterministic cover art gradient from a track/album ID.
 * Same ID always produces the same gradient — consistent across page loads.
 */

// Curated palette pairs [colorA, colorB] — dark, rich, music-appropriate
const _PALETTES = [
  ['#1a3a4a', '#0d1f2d'],
  ['#3a1a2a', '#1f0d15'],
  ['#1a3a2a', '#0d1f15'],
  ['#2a1a3a', '#150d1f'],
  ['#3a2a1a', '#1f150d'],
  ['#1a2a3a', '#0d151f'],
  ['#3a1a1a', '#1f0d0d'],
  ['#1a3a3a', '#0d1f1f'],
  ['#2a3a1a', '#151f0d'],
  ['#3a3a1a', '#1f1f0d'],
  ['#1a1a3a', '#0d0d1f'],
  ['#2a1a1a', '#150d0d'],
];

function _hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(31, h) + str.charCodeAt(i) | 0;
  }
  return Math.abs(h);
}

export function coverGradient(id) {
  const h = _hash(id || 'default');
  const [a, b] = _PALETTES[h % _PALETTES.length];
  const angle = (h % 12) * 30; // 0, 30, 60 ... 330 deg
  return `linear-gradient(${angle}deg, ${a}, ${b})`;
}

/**
 * Returns an art element string — real img if cover_art_url exists,
 * otherwise a deterministic gradient div with the note/eq-bars overlay.
 */
export function artThumb(track, size = 'md') {
  const dim  = size === 'lg' ? 'w-36 h-36' : 'w-10 h-10';
  const icon = size === 'lg' ? 24 : 16;

  if (track.cover_art_url) {
    return `<img src="${_esc(track.cover_art_url)}" class="${dim} rounded object-cover" alt="" />`;
  }

  const grad = coverGradient(track.album_id || track.track_id);
  return `
    <div class="${dim} rounded shrink-0 track-art-placeholder flex items-center justify-center"
         style="background:${grad}">
      <svg class="note-icon" width="${icon}" height="${icon}" viewBox="0 0 24 24"
           fill="rgba(255,255,255,0.25)">
        <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/>
      </svg>
      <div class="eq-bars hidden"><span></span><span></span><span></span></div>
    </div>`;
}

function _esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}
