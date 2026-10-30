const KEY = 'music_library';

export function getSaved() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; }
  catch { return []; }
}

export function isSaved(track_id) {
  return getSaved().some(t => t.track_id === track_id);
}

export function toggleSaved(track) {
  let list = getSaved();
  if (list.some(t => t.track_id === track.track_id)) {
    list = list.filter(t => t.track_id !== track.track_id);
  } else {
    list.unshift(track);
  }
  localStorage.setItem(KEY, JSON.stringify(list));
  return isSaved(track.track_id);
}
