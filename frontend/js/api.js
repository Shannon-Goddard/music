const BASE_URL = "https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1";

async function request(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw new Error(`API error ${response.status} on ${path}`);
  return response.json();
}

/** GET /tracks/search?q={query}&limit={n} */
export function searchTracks(query, limit = 20) {
  return request(`/tracks/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

/** GET /tracks/search?genre={genre}&limit={n} */
export function searchByGenre(genre, limit = 20) {
  return request(`/tracks/search?genre=${encodeURIComponent(genre)}&limit=${limit}`);
}
