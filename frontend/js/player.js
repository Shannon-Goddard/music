import * as Queue from './queue.js';

const audio     = document.getElementById('audio');
const playerEl  = document.getElementById('player');

// Desktop elements
const titleEl   = document.getElementById('player-title');
const artistEl  = document.getElementById('player-artist');
const artEl     = document.getElementById('player-art');
const artWrap   = document.getElementById('player-art-wrap');
const btnPlay   = document.getElementById('btn-play');
const iconPlay  = document.getElementById('icon-play');
const iconPause = document.getElementById('icon-pause');
const btnNext   = document.getElementById('btn-next');
const btnPrev   = document.getElementById('btn-prev');
const btnShuffle = document.getElementById('btn-shuffle');
const btnRepeat  = document.getElementById('btn-repeat');
const seekEl    = document.getElementById('player-seek');
const currentEl = document.getElementById('player-current');
const durationEl = document.getElementById('player-duration');
const volumeEl  = document.getElementById('player-volume');

// Mobile elements
const titleElM   = document.getElementById('player-title-m');
const artistElM  = document.getElementById('player-artist-m');
const artElM     = document.getElementById('player-art-m');
const artWrapM   = document.getElementById('player-art-wrap-m');
const btnPlayM   = document.getElementById('btn-play-m');
const iconPlayM  = document.getElementById('icon-play-m');
const iconPauseM = document.getElementById('icon-pause-m');
const btnNextM   = document.getElementById('btn-next-m');
const btnPrevM   = document.getElementById('btn-prev-m');
const btnShuffleM = document.getElementById('btn-shuffle-m');
const btnRepeatM  = document.getElementById('btn-repeat-m');
const seekElM    = document.getElementById('player-seek-m');
const currentElM = document.getElementById('player-current-m');
const durationElM = document.getElementById('player-duration-m');

let shuffleOn = false;
let repeatOn  = false;

let sleepTimer = null;
let positionInterval = null;

// ── Playback ──────────────────────────────────────────────

export function play(track) {
  if (!track?.stream_url) return;
  audio.src = track.stream_url;
  audio.play().catch(e => console.warn('Playback error:', e));
  _updateUI(track);
  _updateMediaSession(track);
  _saveRecent(track);
  playerEl.classList.remove('hidden');
  document.body.classList.add('player-visible');
}

function _saveRecent(track) {
  try {
    const RECENT_KEY = 'music_recent';
    const MAX = 20;
    let list = JSON.parse(localStorage.getItem(RECENT_KEY)) || [];
    list = list.filter(t => t.track_id !== track.track_id); // dedupe
    list.unshift(track);                                     // newest first
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX)));
  } catch { /* storage full or unavailable */ }
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
  // Desktop
  titleEl.textContent  = track.title || '';
  artistEl.textContent = track.artist_name || '';
  if (track.cover_art_url) {
    artEl.src = track.cover_art_url;
    artWrap.classList.remove('hidden');
  } else {
    artWrap.classList.add('hidden');
  }
  // Mobile
  titleElM.textContent  = track.title || '';
  artistElM.textContent = track.artist_name || '';
  if (track.cover_art_url) {
    artElM.src = track.cover_art_url;
    artWrapM.classList.remove('hidden');
  } else {
    artWrapM.classList.add('hidden');
  }
  _setPlaying(true);
  document.title = `${track.title} — music`;
  // Notify any visible track rows
  document.dispatchEvent(new CustomEvent('trackchange', { detail: { track_id: track.track_id } }));
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

audio.addEventListener('play',  () => { _setPlaying(true);  document.body.classList.remove('paused'); });
audio.addEventListener('pause', () => { _setPlaying(false); document.body.classList.add('paused'); });

function _setPlaying(playing) {
  iconPlay.classList.toggle('hidden', playing);
  iconPause.classList.toggle('hidden', !playing);
  iconPlayM.classList.toggle('hidden', playing);
  iconPauseM.classList.toggle('hidden', !playing);
}

audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  seekEl.value  = pct;
  seekElM.value = pct;
  const t = _fmt(audio.currentTime);
  const d = _fmt(audio.duration);
  currentEl.textContent  = t;
  currentElM.textContent = t;
  durationEl.textContent  = d;
  durationElM.textContent = d;
});

audio.addEventListener('ended', () => _onNext());

audio.addEventListener('error', () => {
  console.warn('Audio error — skipping to next');
  _onNext();
});

seekEl.addEventListener('input',  () => { if (audio.duration) audio.currentTime = (seekEl.value  / 100) * audio.duration; });
seekElM.addEventListener('input', () => { if (audio.duration) audio.currentTime = (seekElM.value / 100) * audio.duration; });

volumeEl.addEventListener('input', () => { audio.volume = volumeEl.value; });

btnPlay.addEventListener('click',  togglePlay);
btnPlayM.addEventListener('click', togglePlay);
btnNext.addEventListener('click',  _onNext);
btnNextM.addEventListener('click', _onNext);
btnPrev.addEventListener('click',  _onPrev);
btnPrevM.addEventListener('click', _onPrev);

function _onNext() {
  if (repeatOn) { audio.currentTime = 0; audio.play(); return; }
  const track = shuffleOn ? Queue.random() : Queue.next();
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
  btn.classList.toggle('text-white/30', mins === 0);
});

// ── Shuffle / Repeat ──────────────────────────────────────

btnShuffle.addEventListener('click',  _toggleShuffle);
btnShuffleM.addEventListener('click', _toggleShuffle);
btnRepeat.addEventListener('click',   _toggleRepeat);
btnRepeatM.addEventListener('click',  _toggleRepeat);

function _toggleShuffle() {
  shuffleOn = !shuffleOn;
  [btnShuffle, btnShuffleM].forEach(b => {
    b.classList.toggle('text-accent', shuffleOn);
    b.classList.toggle('text-white/30', !shuffleOn);
  });
}

function _toggleRepeat() {
  repeatOn = !repeatOn;
  [btnRepeat, btnRepeatM].forEach(b => {
    b.classList.toggle('text-accent', repeatOn);
    b.classList.toggle('text-white/30', !repeatOn);
  });
}
