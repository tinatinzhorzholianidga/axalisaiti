// Smoke tests for the CyberHero app served by the Flask shell.
// Every key page is opened in both languages; any console error or
// uncaught page error fails the test.
import { expect, test } from '@playwright/test';

const ROUTES = [
  ['/', 'welcome'],
  ['/tracks', 'tracks'],
  ['/track/kids', 'coming-soon track'],
  ['/guardians', 'guardians map'],
  ['/guardians/mission/g1', 'mission'],
  ['/parents', 'parents hub'],
  ['/parents/a1', 'article'],
  ['/parents/agreement', 'family agreement'],
  ['/courses', 'courses'],
  ['/course/cyber-guardians', 'course'],
  ['/learn/cyber-guardians/g1-phishing-hunter', 'lesson'],
  ['/emergency', 'emergency'],
  ['/certificate', 'certificate verification'],
  ['/does-not-exist', 'not found'],
];

const TITLES = {
  ka: { '/': 'ისწავლე უსაფრთხოება', '/guardians': 'კიბერ დამცველები', '/parents': 'მასწავლებლები და მშობლები', '/emergency': 'გადაუდებელი დახმარება', '/does-not-exist': 'გვერდი ვერ მოიძებნა' },
  en: { '/': 'Learn to stay safe', '/guardians': 'Cyber Guardians', '/parents': 'Teachers & Parents', '/emergency': 'Emergency help', '/does-not-exist': 'Page not found' },
};

function watchErrors(page) {
  const errors = [];
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });
  return errors;
}

for (const lang of ['ka', 'en']) {
  test.describe(`CyberHero pages (${lang})`, () => {
    for (const [route, label] of ROUTES) {
      test(`${label} renders without errors`, async ({ page }) => {
        const errors = watchErrors(page);
        const response = await page.goto(`/cyberhero${route}?lang=${lang}`);
        expect(response.status()).toBe(200);
        await expect(page.locator('#cyberhero-root')).toBeVisible();
        await expect(page.locator('html')).toHaveAttribute('lang', lang);
        // the app has finished loading once the header brand is on screen and the spinner is gone
        await expect(page.locator('.site-header .brand')).toBeVisible();
        await expect(page.locator('.state-spinner')).toHaveCount(0, { timeout: 15000 });
        const expected = TITLES[lang][route];
        if (expected) await expect(page.getByText(expected, { exact: false }).first()).toBeVisible();
        // no inline styles or handlers anywhere (strict CSP)
        expect(await page.locator('[style]').count()).toBe(0);
        expect(await page.locator('[onclick]').count()).toBe(0);
        expect(errors, errors.join('\n')).toEqual([]);
      });
    }
  });
}

test('the page column stays centred on wide screens', async ({ page }) => {
  // The React wrapper (.app-main) owns the page width; the host <main> sits
  // outside .cyberhero-root and must not be what the layout relies on.
  await page.setViewportSize({ width: 1900, height: 1000 });
  await page.goto('/cyberhero/?lang=en');
  await expect(page.locator('.tier-grid .tier-card').first()).toBeVisible();
  const column = await page.locator('.app-main').boundingBox();
  expect(column.width).toBeLessThanOrEqual(1160);
  expect(column.x).toBeGreaterThan(300);
  const grid = await page.locator('.tier-grid').boundingBox();
  expect(grid.x).toBeGreaterThan(column.x);
  expect(grid.x + grid.width).toBeLessThan(column.x + column.width);
  // every card sits inside the column (nothing hangs off the viewport edge)
  for (const card of await page.locator('.tier-grid .tier-card').all()) {
    const box = await card.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(grid.x - 1);
    expect(box.x + box.width).toBeLessThanOrEqual(grid.x + grid.width + 1);
  }
});

test('language toggle switches the whole page', async ({ page }) => {
  await page.goto('/cyberhero/?lang=ka');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ka');
  await page.getByRole('button', { name: 'EN' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByText('Learn to stay safe')).toBeVisible();
  await page.getByRole('button', { name: 'ქარ' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'ka');
});

test('a mission can be started and the first round answered', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/cyberhero/guardians/mission/g1?lang=en');
  await expect(page.locator('.brief-card')).toBeVisible();
  await page.locator('.brief-card .actions button').click();
  await expect(page.locator('.play-card')).toBeVisible();
  const choice = page.locator('.choice-btn').first();
  if (await choice.count()) {
    await choice.click();
    await expect(page.locator('.feedback')).toBeVisible();
  }
  expect(errors, errors.join('\n')).toEqual([]);
});

test('the IO tutor pages are hidden while the feature flag is off', async ({ page }) => {
  await page.goto('/cyberhero/io-chat?lang=en');
  await expect(page.getByText('Page not found')).toBeVisible();
  const api = await page.request.get('/api/v1/cyberhero/knowledge');
  expect(api.status()).toBe(404);
});

test('security headers are present on the shell', async ({ page }) => {
  const response = await page.goto('/cyberhero/?lang=ka');
  const csp = response.headers()['content-security-policy'];
  expect(csp).toContain("default-src 'self'");
  expect(csp).not.toContain('unsafe-inline');
  expect(response.headers()['x-frame-options']).toBe('DENY');
});

test('the mission map is usable on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await page.goto('/cyberhero/guardians?lang=ka');
  await expect(page.locator('.mission-card').first()).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(375);
});
