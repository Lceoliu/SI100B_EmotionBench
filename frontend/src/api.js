let csrfToken = '';

export function setCsrfToken(token) {
  csrfToken = token || '';
}

function makeRequestNonce() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
    headers.set('X-Request-Nonce', makeRequestNonce());
    headers.set('X-Request-Time', String(Date.now()));
  }
  const res = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || `请求失败：${res.status}`);
  return payload;
}
