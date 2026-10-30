const BASE_URL = "https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1";
const PAGE_SIZE = 20;

// Language filter — 'eng' = English + language-agnostic (default), 'all' = no filter
let _lang = localStorage.getItem('music_lang') || 'eng';
export function getLang() { return _lang; }
export function setLang(val) { _lang = val; localStorage.setItem('music_lang', val); }

function _langParam() { return _lang === 'all' ? '&lang=all' : ''; }

async function request(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw new Error(`API error ${response.status} on ${path}`);
  return response.json();
}

/** GET /tracks/search?q={query}&limit={n}&offset={n} */
export function searchTracks(query, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}${_langParam()}`);
}

/** GET /tracks/search?genre={genre}&limit={n}&offset={n} */
export function searchByGenre(genre, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?genre=${encodeURIComponent(genre)}&limit=${limit}&offset=${offset}${_langParam()}`);
}

/** GET /tracks/search?type={type}&limit={n}&offset={n} */
export function searchByType(type, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?type=${encodeURIComponent(type)}&limit=${limit}&offset=${offset}${_langParam()}`);
}

/** GET /artists/search?q={query} */
export function searchArtists(query) {
  return request(`/artists/search?q=${encodeURIComponent(query)}`);
}

/** GET /albums/search?artist_id={id} or ?q={query} */
export function searchAlbums({ artistId, query } = {}) {
  if (artistId) return request(`/albums/search?artist_id=${encodeURIComponent(artistId)}`);
  if (query)    return request(`/albums/search?q=${encodeURIComponent(query)}`);
  throw new Error("searchAlbums requires artistId or query");
}

/** GET /radio?genre={genre}&limit={n} */
export function getRadio(genre, limit = 50) {
  return request(`/radio?genre=${encodeURIComponent(genre)}&limit=${limit}`);
}

export { PAGE_SIZE };
