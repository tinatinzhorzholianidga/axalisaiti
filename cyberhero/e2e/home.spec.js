// IO, the welcome host, on the eLearning home page (served by Flask, not by
// the CyberHero shell): the bundle's second entry mounts on #io-host-root,
// greets, reacts to the two path cards and stays CSP-clean.
import { expect, test } from '@playwright/test';
import { HINTS } from '../src/host/hints.js';

const INLINE_STYLE = /<[a-z][^>]*\sstyle=/i;
const INLINE_HANDLER = /<[a-z][^>]*\son[a-z]+=/i;
const INLINE_SCRIPT = /<script(?![^>]*\ssrc=)[^>]*>/i;

function watchErrors(page) {
  const errors = [];
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });
  return errors;
}

const pool = (lang, ...keys) => keys.flatMap((key) => HINTS[key].map((line) => line[lang]));

for (const lang of ['ka', 'en']) {
  test(`IO hosts the home page (${lang})`, async ({ page }) => {
    const errors = watchErrors(page);
    const response = await page.goto(`/?lang=${lang}`);
    expect(response.status()).toBe(200);
    const html = await response.text();
    // the server-rendered page is inline-free (strict CSP) and carries the host's runtime
    expect(html).not.toMatch(INLINE_STYLE);
    expect(html).not.toMatch(INLINE_HANDLER);
    expect(html).not.toMatch(INLINE_SCRIPT);
    expect(html).toContain(`data-locale="${lang}"`);
    expect(html).toContain('data-doors="basic,kids"');
    await expect(page.locator('html')).toHaveAttribute('lang', lang);

    // the host mounted in the corner with his stage
    const root = page.locator('#io-host-root');
    await expect(root.locator('.io-host')).toBeVisible();
    const stage = root.locator('.mascot-canvas'); // IO himself (the close button is the other button)
    await expect(stage).toBeVisible();
    await expect(stage).toHaveAttribute('role', 'button');
    await expect(stage).toHaveAttribute('tabindex', '0');

    // he greets on arrival (the live region carries the whole line)
    const live = root.getByRole('status');
    await expect(live).not.toHaveText('', { timeout: 10000 });
    expect(pool(lang, 'morning', 'afternoon', 'evening', 'greeting')).toContain((await live.textContent()).trim());

    // hovering a door makes him talk about it, choosing it gets a goodbye
    await page.locator('[data-io-path="kids"]').hover();
    await expect
      .poll(async () => (await live.textContent()).trim())
      .toMatch(new RegExp(pool(lang, 'hoverKids').map((l) => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')));
    await page.locator('[data-io-path="basic"]').hover();
    await expect
      .poll(async () => (await live.textContent()).trim())
      .toMatch(new RegExp(pool(lang, 'hoverBasic').map((l) => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')));

    // keyboard: Enter on IO walks his orientation lines
    await stage.focus();
    await page.keyboard.press('Enter');
    await expect
      .poll(async () => (await live.textContent()).trim())
      .toMatch(new RegExp(pool(lang, 'pickPath').map((l) => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')));

    // the doors are real links: the basic course and CyberHero
    await expect(page.locator('[data-io-path="basic"]')).toHaveAttribute('href', /\/courses\//);
    await expect(page.locator('[data-io-path="kids"]')).toHaveAttribute('href', '/cyberhero/');
    expect(errors, errors.join('\n')).toEqual([]);
  });
}

test('IO floats in the bottom-right corner and follows the scroll', async ({ page }) => {
  await page.goto('/?lang=en');
  const bot = page.locator('#io-host-root .io-host-bot');
  await expect(bot).toBeVisible();
  await page.waitForTimeout(1200); // let the fly-in finish before measuring
  const viewport = page.viewportSize();
  const before = await bot.boundingBox();
  expect(before.x + before.width).toBeGreaterThan(viewport.width - 60);
  expect(before.y + before.height).toBeGreaterThan(viewport.height - 60);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(200);
  const after = await bot.boundingBox();
  expect(Math.abs(after.y - before.y)).toBeLessThan(2); // still on screen, same spot
  // hide him, bring him back
  await page.getByRole('button', { name: 'Hide IO' }).click();
  await expect(page.locator('#io-host-root .io-host')).toHaveCount(0);
  await page.getByRole('button', { name: 'Show IO' }).click();
  await expect(page.locator('#io-host-root .io-host')).toBeVisible();
});

test('choosing a door says goodbye and navigates', async ({ page }) => {
  await page.goto('/?lang=en');
  const live = page.locator('#io-host-root').getByRole('status');
  await expect(live).not.toHaveText('', { timeout: 10000 });
  await page.locator('[data-io-path="kids"]').click();
  await page.waitForURL(/\/cyberhero\/?(\?.*)?$/);
  await expect(page.locator('#cyberhero-root')).toBeVisible();
});

test('the home page is usable on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await page.goto('/?lang=ka');
  await expect(page.locator('#io-host-root .io-host')).toBeVisible();
  await expect(page.locator('[data-io-path="basic"]')).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(375);
});
