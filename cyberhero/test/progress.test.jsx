import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { ContentProvider } from '../src/content/ContentProvider.jsx';
import { readRuntime, resetRuntime } from '../src/lib/runtime.js';
import { resetCsrfToken } from '../src/lib/api.js';
import { mergeProgress, ProgressProvider, useProgress } from '../src/store/progress.jsx';
import { jsonResponse, mockFetch, mountRoot } from './helpers.js';

function wrapperFor(root) {
  const runtime = readRuntime(root);
  return function Wrapper({ children }) {
    return (
      <ContentProvider runtime={runtime}>
        <ProgressProvider>{children}</ProgressProvider>
      </ContentProvider>
    );
  };
}

describe('progress store', () => {
  beforeEach(() => {
    resetRuntime();
    resetCsrfToken();
    document.head.innerHTML = '';
  });

  it('merges server progress: best score wins and done never regresses', () => {
    const local = { guardians: { missions: { g1: { done: true, best: 30, total: 60 } }, certName: '' }, lessons: {} };
    const remote = { guardians: { missions: { g1: { done: false, best: 50, total: 60 }, g2: { done: true, best: 10, total: 40 } } }, lessons: { 'c/l': { done: true } } };
    const merged = mergeProgress(local, remote);
    expect(merged.guardians.missions.g1).toEqual({ done: true, best: 50, total: 60 });
    expect(merged.guardians.missions.g2.done).toBe(true);
    expect(merged.lessons['c/l'].done).toBe(true);
  });

  it('keeps anonymous progress in localStorage without calling the server', async () => {
    const root = mountRoot();
    const { calls } = mockFetch();
    const { result } = renderHook(() => useProgress(), { wrapper: wrapperFor(root) });
    act(() => result.current.recordMission('g1', { score: 40, total: 60 }));
    expect(result.current.progress.guardians.missions.g1).toEqual({ done: true, best: 40, total: 60 });
    expect(JSON.parse(localStorage.getItem('cyberhero.progress.v1')).guardians.missions.g1.best).toBe(40);
    await waitFor(() => expect(calls.some((c) => c.url.pathname.endsWith('/bootstrap'))).toBe(true));
    expect(calls.some((c) => c.url.pathname.endsWith('/progress'))).toBe(false);
  });

  it('syncs with the server for signed-in learners', async () => {
    const root = mountRoot({ userId: '5', userName: 'Nino' });
    const { calls } = mockFetch({
      '/api/v1/cyberhero/progress': (url, init) => {
        if (init.method === 'PUT') {
          const body = JSON.parse(init.body);
          return jsonResponse({ guardians: { missions: { ...body.guardians.missions, g9: { done: true, best: 5, total: 20 } } }, lessons: body.lessons || {} });
        }
        return jsonResponse({ guardians: { missions: { g2: { done: true, best: 12, total: 40 } } }, lessons: {} });
      },
    });
    const { result } = renderHook(() => useProgress(), { wrapper: wrapperFor(root) });
    await waitFor(() => expect(result.current.progress.guardians.missions.g2?.done).toBe(true));
    act(() => result.current.recordMission('g1', { score: 40, total: 60 }));
    await waitFor(() => expect(result.current.progress.guardians.missions.g9?.done).toBe(true));
    const put = calls.find((c) => c.url.pathname.endsWith('/progress') && c.init.method === 'PUT');
    expect(put.init.headers['X-CSRFToken']).toBe('meta-csrf');
    expect(result.current.syncState).toBe('synced');
  });
});
