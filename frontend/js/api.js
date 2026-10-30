const BASE_URL = "https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1";
const PAGE_SIZE = 20;

async function request(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw new Error(`API error ${response.status} on ${path}`);
  return response.json();
}

/** GET /tracks/search?q={query}&limit={n}&offset={n} */
export function searchTracks(query, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`);
}

/** GET /tracks/search?genre={genre}&limit={n}&offset={n} */
export function searchByGenre(genre, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?genre=${encodeURIComponent(genre)}&limit=${limit}&offset=${offset}`);
}

/** GET /tracks/search?type={type}&limit={n}&offset={n} */
export function searchByType(type, limit = PAGE_SIZE, offset = 0) {
  return request(`/tracks/search?type=${encodeURIComponent(type)}&limit=${limit}&offset=${offset}`);
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

export { PAGE_SIZE };
