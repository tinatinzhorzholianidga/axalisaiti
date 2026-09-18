import { beforeEach, describe, expect, it } from 'vitest';
import { langSwitchUrl, readRuntime, resetRuntime } from '../src/lib/runtime.js';
import { mountRoot } from './helpers.js';

describe('runtime', () => {
  beforeEach(() => resetRuntime());

  it('reads every data attribute from the root element', () => {
    const root = mountRoot({ locale: 'en', userId: '7', userName: 'Nino', flags: '{"CYBERHERO_IO_CHAT_ENABLED":true}', tutorModelUrl: '/models/io/' });
    const rt = readRuntime(root);
    expect(rt.basename).toBe('/cyberhero');
    expect(rt.locale).toBe('en');
    expect(rt.userId).toBe('7');
    expect(rt.userName).toBe('Nino');
    expect(rt.flags.CYBERHERO_IO_CHAT_ENABLED).toBe(true);
    expect(rt.tutorModelUrl).toBe('/models/io/');
  });

  it('falls back to safe defaults when attributes are missing or broken', () => {
    const root = mountRoot({ flags: '{not json', locale: 'fr' });
    const rt = readRuntime(root);
    expect(rt.locale).toBe('ka');
    expect(rt.flags).toEqual({});
    expect(rt.emergencyPhone).toBe('112');
  });

  it('builds a language switch URL on the current page', () => {
    window.history.replaceState({}, '', '/cyberhero/guardians?x=1');
    expect(langSwitchUrl('en', readRuntime(mountRoot()))).toBe('/cyberhero/guardians?x=1&lang=en');
  });
});
