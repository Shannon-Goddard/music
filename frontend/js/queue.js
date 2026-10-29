const STORAGE_KEY = "music_queue";
const SESSION_KEY = "music_session";

let queue = [];
let currentIndex = 0;

export function setQueue(tracks, startIndex = 0) {
  queue = tracks;
  currentIndex = startIndex;
  _persist();
}

export function getQueue() { return queue; }
export function getCurrentIndex() { return currentIndex; }
export function getCurrentTrack() { return queue[currentIndex] || null; }

export function next() {
  if (currentIndex < queue.length - 1) {
    currentIndex++;
    _persist();
    return getCurrentTrack();
  }
  return null;
}

export function prev() {
  if (currentIndex > 0) {
    currentIndex--;
    _persist();
    return getCurrentTrack();
  }
  return null;
}

export function addToQueue(track) {
  queue.push(track);
  _persist();
}

/** Save position every 10s for "continue where you left off" */
export function savePosition(positionSec) {
  const session = _loadSession();
  session.position_sec = positionSec;
  session.track_id = getCurrentTrack()?.track_id;
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function loadSession() {
  return _loadSession();
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(STORAGE_KEY);
}

function _persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ queue, currentIndex }));
}

function _loadSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY)) || {};
  } catch {
    return {};
  }
}

// Restore queue from localStorage on module load
try {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
  if (saved?.queue?.length) {
    queue = saved.queue;
    currentIndex = saved.currentIndex || 0;
  }
} catch { /* ignore */ }
