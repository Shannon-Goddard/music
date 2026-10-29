import * as Queue from './queue.js';

const audio = document.getElementById('audio');
const playerEl = document.getElementById('player');
const titleEl = document.getElementById('player-title');
const artistEl = document.getElementById('player-artist');
const artEl = document.getElementById('player-art');
const btnPlay = document.getElementById('btn-play');
const btnNext = document.getElementById('btn-next');
const btnPrev = document.getElementById('btn-prev');
const seekEl = document.getElementById('player-seek');
const currentEl = document.getElementById('player-current');
const durationEl = document.getElementById('player-duration');
const volumeEl = document.getElementById('player-volume');

let sleepTimer = null;
let positionInterval = null;

// ── Playback ──────────────────────────────────────────────

export function play(track) {
  if (!track?.stream_url) return;
  audio.src = track.stream_url;
  audio.play().catch(e => console.warn('Playback error:', e));
  _updateUI(track);
  _updateMediaSession(track);
  playerEl.classList.remove('hidden');
}

export function togglePlay() {
  if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
}

export function playQueue(tracks, startIndex = 0) {
  Queue.setQueue(tracks, startIndex);
  play(Queue.getCurrentTrack());
}

// ── UI Updates ────────────────────────────────────────────

function _updateUI(track) {
  titleEl.textContent = track.title || '';
  artistEl.textContent = track.artist_name || '';
  if (track.cover_art_url) {
    artEl.src = track.cover_art_url;
    artEl.classList.remove('hidden');
  } else {
    artEl.classList.add('hidden');
  }
  btnPlay.textContent = '⏸';
  document.title = `${track.title} — music`;
}

function _fmt(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// ── Media Session API (Bluetooth / hardware controls) ─────

function _updateMediaSession(track) {
  if (!('mediaSession' in navigator)) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: track.title || '',
    artist: track.artist_name || '',
    album: track.album_title || '',
    artwork: track.cover_art_url
      ? [{ src: track.cover_art_url, sizes: '512x512', type: 'image/jpeg' }]
      : [],
  });
  navigator.mediaSession.setActionHandler('play', () => audio.play());
  navigator.mediaSession.setActionHandler('pause', () => audio.pause());
  navigator.mediaSession.setActionHandler('nexttrack', () => _onNext());
  navigator.mediaSession.setActionHandler('previoustrack', () => _onPrev());
  navigator.mediaSession.setActionHandler('seekto', (d) => {
    audio.currentTime = d.seekTime;
  });
}

// ── Event Listeners ───────────────────────────────────────

audio.addEventListener('play', () => { btnPlay.textContent = '⏸'; });
audio.addEventListener('pause', () => { btnPlay.textContent = '▶'; });

audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  seekEl.value = pct;
  currentEl.textContent = _fmt(audio.currentTime);
  durationEl.textContent = _fmt(audio.duration);
});

audio.addEventListener('ended', () => _onNext());

audio.addEventListener('error', () => {
  console.warn('Audio error — skipping to next');
  _onNext();
});

seekEl.addEventListener('input', () => {
  if (audio.duration) {
    audio.currentTime = (seekEl.value / 100) * audio.duration;
  }
});

volumeEl.addEventListener('input', () => {
  audio.volume = volumeEl.value;
});

btnPlay.addEventListener('click', togglePlay);
btnNext.addEventListener('click', _onNext);
btnPrev.addEventListener('click', _onPrev);

function _onNext() {
  const track = Queue.next();
  if (track) play(track);
}

function _onPrev() {
  // If more than 3s in, restart current track instead of going back
  if (audio.currentTime > 3) {
    audio.currentTime = 0;
    return;
  }
  const track = Queue.prev();
  if (track) play(track);
}

// ── Position persistence (continue where you left off) ────

audio.addEventListener('timeupdate', () => {
  // Throttled via interval below
});

positionInterval = setInterval(() => {
  if (!audio.paused && audio.currentTime > 0) {
    Queue.savePosition(audio.currentTime);
  }
}, 10000);

// ── Sleep Timer ───────────────────────────────────────────

export function setSleepTimer(minutes) {
  if (sleepTimer) clearTimeout(sleepTimer);
  if (!minutes) return;

  const ms = minutes * 60 * 1000;
  sleepTimer = setTimeout(() => {
    // Fade out over 10 seconds then pause
    let vol = audio.volume;
    const fade = setInterval(() => {
      vol = Math.max(0, vol - 0.05);
      audio.volume = vol;
      if (vol <= 0) {
        clearInterval(fade);
        audio.pause();
        audio.volume = 1;
      }
    }, 500);
  }, ms);
}

// ── Sleep timer button (cycles 15/30/45/60/off) ───────────

const sleepMinutes = [0, 15, 30, 45, 60];
let sleepIdx = 0;
document.getElementById('btn-sleep').addEventListener('click', () => {
  sleepIdx = (sleepIdx + 1) % sleepMinutes.length;
  const mins = sleepMinutes[sleepIdx];
  setSleepTimer(mins);
  const btn = document.getElementById('btn-sleep');
  btn.title = mins ? `Sleep in ${mins}min` : 'Sleep timer';
  btn.classList.toggle('text-accent', mins > 0);
});
