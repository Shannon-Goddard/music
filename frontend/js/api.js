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

export { PAGE_SIZE };
