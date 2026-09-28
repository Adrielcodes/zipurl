async function request(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

export function shortenUrl(url, alias) {
  return request("/api/links", {
    method: "POST",
    body: JSON.stringify({ url, alias: alias || undefined }),
  });
}

export function getLink(code) {
  return request(`/api/links/${encodeURIComponent(code)}`);
}
