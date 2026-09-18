import { beforeEach, describe, expect, it } from 'vitest';
import { apiGet, apiPut, apiUrl, ApiError, resetCsrfToken } from '../src/lib/api.js';
import { resetRuntime } from '../src/lib/runtime.js';
import { jsonResponse, mockFetch, mountRoot } from './helpers.js';

describe('api client', () => {
  beforeEach(() => {
    resetRuntime();
    resetCsrfToken();
    document.head.innerHTML = '';
    mountRoot();
  });

  it('builds URLs under the configured API base with a locale parameter', () => {
    expect(apiUrl('/missions', { track: 'guardians', locale: 'en' })).toBe('/api/v1/cyberhero/missions?track=guardians&locale=en');
  });

  it('sends same-origin credentials on reads', async () => {
    const { calls } = mockFetch();
    const data = await apiGet('/tracks');
    expect(data.items.length).toBeGreaterThan(0);
    expect(calls[0].init.credentials).toBe('same-origin');
  });

  it('adds the CSRF header from the page meta tag on writes', async () => {
    const { calls } = mockFetch({ '/api/v1/cyberhero/progress': () => jsonResponse({ guardians: { missions: {} }, lessons: {} }) });
    await apiPut('/progress', { guardians: { missions: {} } });
    const write = calls.find((c) => c.url.pathname.endsWith('/progress'));
    expect(write.init.method).toBe('PUT');
    expect(write.init.headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('raises ApiError with the server message', async () => {
    mockFetch();
    await expect(apiGet('/missions/does-not-exist')).rejects.toBeInstanceOf(ApiError);
  });
});
