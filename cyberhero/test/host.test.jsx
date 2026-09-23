import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HINTS } from '../src/host/hints.js';
import { CYCLE, MOOD, createHost, mentionsKids, timeOfDay } from '../src/host/hostBrain.js';
import HomeHost, { attachDoors } from '../src/host/HomeHost.jsx';

/* ---- IO's lines (the checks the IO-for-main-page project ran as
   `npm run check`, kept here so `npm test` guards the copy) ------------ */
const REQUIRED = [
  'greeting', 'whoAmI', 'pickPath', 'basicCourse', 'kidsPlatform', 'login', 'certificate', 'language',
  'aboutDga', 'encouragement', 'hoverBasic', 'hoverKids', 'morning', 'afternoon', 'evening', 'farewell',
];
const MAX_LEN = 110;
const TIP_WORDS = /(პაროლ|ფიშინგ|ანტივირუს|password|phishing|antivirus|two-factor|2fa|update your|განაახლ)/i;
const EMOJI = /\p{Extended_Pictographic}/gu;
const lines = REQUIRED.flatMap((key) => (HINTS[key] || []).map((line, i) => [key, i, line]));

describe("IO's home-page lines", () => {
  it('has every category in both languages', () => {
    for (const key of REQUIRED) expect(HINTS[key]?.length, key).toBeGreaterThan(0);
    for (const [key, i, line] of lines) {
      expect(line.en?.trim(), `${key}[${i}].en`).toBeTruthy();
      expect(line.ka?.trim(), `${key}[${i}].ka`).toBeTruthy();
    }
  });

  it('fits the bubble: <= 110 characters, at most one emoji', () => {
    for (const [key, i, line] of lines) {
      for (const l of ['en', 'ka']) {
        expect(line[l].length, `${key}[${i}].${l}`).toBeLessThanOrEqual(MAX_LEN);
        expect((line[l].match(EMOJI) || []).length, `${key}[${i}].${l}`).toBeLessThanOrEqual(1);
      }
    }
  });

  it('gives no cyber-security tips on the home page', () => {
    for (const [key, i, line] of lines) {
      if (key === 'basicCourse') continue;
      for (const l of ['en', 'ka']) expect(line[l], `${key}[${i}].${l}`).not.toMatch(TIP_WORDS);
    }
  });

  it('follows the Georgian typography rules (em dash, „…“ quotes, no leaked Latin)', () => {
    for (const [key, i, line] of lines) {
      for (const l of ['en', 'ka']) expect(line[l], `${key}[${i}].${l}`).not.toMatch(/ - /);
      const stripped = line.ka.replace(/English|CyberHero|IO|DGA|elearning\.gov\.ge/g, '');
      expect(stripped, `${key}[${i}].ka`).not.toMatch(/[a-z]/i);
      expect(line.ka, `${key}[${i}].ka`).not.toMatch(/["”]/);
      expect((line.ka.match(/„/g) || []).length, `${key}[${i}].ka`).toBe((line.ka.match(/“/g) || []).length);
    }
  });
});

/* ---- the brain --------------------------------------------------------- */
describe('host brain', () => {
  it('greets by the time of day and introduces himself second', () => {
    expect(timeOfDay(new Date(2026, 0, 1, 9))).toBe('morning');
    expect(timeOfDay(new Date(2026, 0, 1, 15))).toBe('afternoon');
    expect(timeOfDay(new Date(2026, 0, 1, 21))).toBe('evening');
    const host = createHost({ date: new Date(2026, 0, 1, 21) });
    const hello = host.greet();
    expect(hello.key).toBe('evening');
    expect(hello.mood).toBe(MOOD.evening);
    expect(HINTS.evening).toContain(hello.line);
    expect(host.intro().key).toBe('whoAmI');
  });

  it('walks the click cycle without repeating a line until its pool is exhausted', () => {
    const host = createHost({ seed: 3 });
    const keys = CYCLE.map(() => host.next().key);
    expect(keys).toEqual(CYCLE);
    const peek = createHost({ seed: 0 });
    const seen = new Set();
    for (let i = 0; i < HINTS.hoverBasic.length; i += 1) {
      const pick = peek.hover('basic');
      expect(pick.key).toBe('hoverBasic');
      seen.add(pick.line);
    }
    expect(seen.size).toBe(HINTS.hoverBasic.length);
    expect(seen.has(peek.hover('basic').line)).toBe(true); // the pool wraps around
  });

  it('reacts to the doors and says goodbye', () => {
    const host = createHost();
    expect(host.hover('kids').key).toBe('hoverKids');
    expect(host.hover('kids').mood).toBe('excited');
    expect(host.farewell().key).toBe('farewell');
  });

  it('never mentions CyberHero when that door is not on the page', () => {
    const host = createHost({ doors: ['basic'] });
    const said = [host.greet(), host.intro(), host.hover('basic'), host.hover('kids'), host.farewell(), host.farewell()];
    for (let i = 0; i < CYCLE.length * 2; i += 1) said.push(host.next());
    const keys = new Set(said.filter(Boolean).map((pick) => pick.key));
    expect(keys.has('kidsPlatform')).toBe(false);
    expect(keys.has('pickPath')).toBe(false);
    expect(keys.has('basicCourse')).toBe(true);
    for (const pick of said.filter(Boolean)) {
      expect(mentionsKids(pick.line), `${pick.key}: ${pick.line.en}`).toBe(false);
      expect(`${pick.line.en} ${pick.line.ka}`).not.toMatch(/CyberHero|კიბერგმირ/);
    }
    // with both doors the lines about CyberHero are back
    const both = createHost();
    expect(CYCLE.map(() => both.next().key)).toEqual(CYCLE);
  });

  it('does not point a signed-in visitor to the sign-in button', () => {
    const host = createHost({ signedIn: true });
    const keys = CYCLE.map(() => host.next()?.key);
    expect(keys).not.toContain('login');
    expect(keys).toContain('certificate');
  });
});

/* ---- IO on the page ---------------------------------------------------- */
describe('HomeHost', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = '<a href="/courses/" data-io-path="basic">Basic</a><a href="/cyberhero/" data-io-path="kids">Kids</a>';
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('greets on arrival, reacts to a hovered door and waves goodbye', () => {
    render(<HomeHost lang="en" label="IO" />);
    // no WebGL in jsdom: the friendly sticker stands in for the 3D stage
    expect(document.querySelector('.mascot-fallback')).not.toBeNull();
    // IO is a keyboard-operable button
    expect(screen.getByRole('button', { name: 'IO' })).toHaveAttribute('tabindex', '0');
    const live = screen.getByRole('status');
    expect(live).toHaveTextContent('');
    act(() => vi.advanceTimersByTime(600));
    const greetings = [...HINTS.morning, ...HINTS.afternoon, ...HINTS.evening, ...HINTS.greeting].map((l) => l.en);
    expect(greetings).toContain(live.textContent);

    const kids = document.querySelector('[data-io-path="kids"]');
    act(() => {
      kids.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false }));
    });
    expect(HINTS.hoverKids.map((l) => l.en)).toContain(live.textContent);

    act(() => {
      kids.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(HINTS.farewell.map((l) => l.en)).toContain(live.textContent);
  });

  it('can be hidden and brought back with the chip', () => {
    render(<HomeHost lang="en" label="IO" closeLabel="Hide IO" openLabel="Show IO" />);
    act(() => vi.advanceTimersByTime(600));
    fireEvent.click(screen.getByRole('button', { name: 'Hide IO' }));
    expect(screen.queryByRole('status')).toBeNull();
    expect(document.querySelector('.io-host')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show IO' }));
    expect(document.querySelector('.io-host')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'IO' })).toBeInTheDocument();
  });

  it('speaks Georgian by default', () => {
    render(<HomeHost />);
    act(() => vi.advanceTimersByTime(600));
    expect(screen.getByRole('status').textContent).toMatch(/[ა-ჰ]/);
  });

  it('attachDoors wires the doors to the host and detaches them again', () => {
    const io = { current: { hover: vi.fn(), unhover: vi.fn(), farewell: vi.fn() } };
    const off = attachDoors(io);
    const basic = document.querySelector('[data-io-path="basic"]');
    const kids = document.querySelector('[data-io-path="kids"]');
    basic.dispatchEvent(new MouseEvent('mouseenter'));
    expect(io.current.hover).toHaveBeenCalledWith('basic', 'mouse');
    kids.dispatchEvent(new FocusEvent('focus'));
    expect(io.current.hover).toHaveBeenCalledWith('kids', 'focus');
    basic.dispatchEvent(new MouseEvent('mouseleave'));
    expect(io.current.unhover).toHaveBeenCalledWith('mouse');
    // a plain click is a choice; a modifier-click (new tab) leaves IO where he is
    basic.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    expect(io.current.farewell).toHaveBeenCalledTimes(1);
    basic.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ctrlKey: true }));
    basic.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 1 }));
    expect(io.current.farewell).toHaveBeenCalledTimes(1);
    off();
    basic.dispatchEvent(new MouseEvent('mouseenter'));
    kids.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    expect(io.current.hover).toHaveBeenCalledTimes(2);
    expect(io.current.farewell).toHaveBeenCalledTimes(1);
  });

  it('keeps keyboard focus on the widget when IO is hidden and shown', () => {
    render(<HomeHost lang="en" label="IO" closeLabel="Hide IO" openLabel="Show IO" />);
    act(() => vi.advanceTimersByTime(600));
    fireEvent.click(screen.getByRole('button', { name: 'Hide IO' }));
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Show IO' }));
    fireEvent.click(screen.getByRole('button', { name: 'Show IO' }));
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'IO' }));
  });
});
