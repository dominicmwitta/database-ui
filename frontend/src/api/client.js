const BASE = '/api';

function getToken() {
  return sessionStorage.getItem('token');
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
  };
}

async function handle(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export async function login({ username, password }) {
  const res = await fetch(`${BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await handle(res);
  sessionStorage.setItem('token', data.token);
  return data;
}

export async function logout() {
  await fetch(`${BASE}/logout`, { method: 'POST', headers: authHeaders() }).catch(() => {});
  sessionStorage.removeItem('token');
}

export async function fetchCategories() {
  const res = await fetch(`${BASE}/categories`, { headers: authHeaders() });
  return handle(res);
}

export async function fetchIndicators(category) {
  const res = await fetch(`${BASE}/indicators?category=${encodeURIComponent(category)}`, {
    headers: authHeaders(),
  });
  return handle(res);
}

export async function fetchLocations() {
  const res = await fetch(`${BASE}/locations`, { headers: authHeaders() });
  return handle(res);
}

export async function fetchUnits(category) {
  const res = await fetch(`${BASE}/units?category=${encodeURIComponent(category)}`, {
    headers: authHeaders(),
  });
  return handle(res);
}

export async function fetchData(params) {
  const res = await fetch(`${BASE}/data`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(params),
  });
  return handle(res);
}
