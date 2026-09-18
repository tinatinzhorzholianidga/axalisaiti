import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { vi } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(here, '..', 'mock', 'fixtures');

export function fixture(name) {
  return JSON.parse(readFileSync(join(FIXTURES, `${name.replace(/\//g, '__')}.json`), 'utf8'));
}

/** Install a fetch mock that answers from the fixtures (like mock/api.js). */
export function mockFetch(overrides = {}) {
  const calls = [];
  const impl = vi.fn(async (input, init = {}) => {
    const url = new URL(String(input), 'http://localhost');
    calls.push({ url, init });
    const handler = overrides[url.pathname];
    if (handler) return handler(url, init);
    if (url.pathname === '/api/v1/auth/csrf') return jsonResponse({ csrf_token: 'test-csrf' });
    const prefix = '/api/v1/cyberhero/';
    if (!url.pathname.startsWith(prefix)) return jsonResponse({ error: { code: 404, message: 'nope' } }, 404);
    const path = url.pathname.slice(prefix.length);
    try {
      const data = fixture(path);
      const filter = url.searchParams.get('track') || url.searchParams.get('shelf');
      if (filter && Array.isArray(data.items)) {
        const key = url.searchParams.get('track') ? 'track' : 'shelf';
        return jsonResponse({ ...data, items: data.items.filter((i) => String(i[key]).toLowerCase() === filter.toLowerCase()) });
      }
      return jsonResponse(data);
    } catch {
      return jsonResponse({ error: { code: 404, message: `no fixture ${path}` } }, 404);
    }
  });
  globalThis.fetch = impl;
  return { impl, calls };
}

export function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
}

/** Create the root element the app reads its runtime from. */
export function mountRoot(attrs = {}) {
  document.body.innerHTML = '';
  const meta = document.createElement('meta');
  meta.name = 'csrf-token';
  meta.content = 'meta-csrf';
  document.head.appendChild(meta);
  const root = document.createElement('div');
  root.id = 'cyberhero-root';
  root.className = 'cyberhero-root';
  const defaults = {
    basename: '/cyberhero',
    locale: 'ka',
    apiBase: '/api/v1/cyberhero',
    staticBase: '/static/cyberhero',
    siteBase: '/',
    loginUrl: '/auth/login?next=/cyberhero/',
    flags: '{"CYBERHERO_IO_CHAT_ENABLED":false}',
    emergencyPhone: '112',
  };
  for (const [key, value] of Object.entries({ ...defaults, ...attrs })) root.dataset[key] = value;
  document.body.appendChild(root);
  return root;
}
