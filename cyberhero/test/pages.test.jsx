import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App.jsx';
import { ContentProvider } from '../src/content/ContentProvider.jsx';
import { I18nProvider } from '../src/i18n/I18nContext.jsx';
import { readRuntime, resetRuntime } from '../src/lib/runtime.js';
import { resetCsrfToken } from '../src/lib/api.js';
import { ProgressProvider } from '../src/store/progress.jsx';
import { trackHint } from '../src/mascot/mascotContext.js';
import { fixture, mockFetch, mountRoot } from './helpers.js';

function renderApp(path, attrs = {}) {
  const root = mountRoot(attrs);
  const runtime = readRuntime(root);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ContentProvider runtime={runtime}>
        <I18nProvider runtime={runtime} initialLang={attrs.locale || 'ka'} navigate={() => {}}>
          <ProgressProvider>
            <App />
          </ProgressProvider>
        </I18nProvider>
      </ContentProvider>
    </MemoryRouter>,
  );
}

describe('pages', () => {
  beforeEach(() => {
    resetRuntime();
    resetCsrfToken();
    document.head.innerHTML = '';
    mockFetch();
  });

  it('renders the welcome page with tracks from the API, in Georgian by default', async () => {
    renderApp('/');
    const guardians = fixture('tracks').items.find((t) => t.id === 'guardians');
    await waitFor(() => expect(screen.getByText(guardians.name.ka)).toBeInTheDocument());
    expect(document.documentElement.lang).toBe('ka');
    expect(document.querySelectorAll('[style]').length).toBe(0);
  });

  it('hovering a track card makes IO say a hint about that track', async () => {
    renderApp('/', { locale: 'en' });
    const tiers = fixture('tracks').items;
    const guardians = tiers.find((t) => t.id === 'guardians');
    const kids = tiers.find((t) => t.id === 'kids');
    const mascot = fixture('mascot');
    await waitFor(() => expect(screen.getByText(guardians.name.en)).toBeInTheDocument());
    // the corner widget mounts a moment after first paint (lazy three.js)
    const bubble = await screen.findByRole('status', {}, { timeout: 5000 });
    const card = screen.getByText(guardians.name.en).closest('a');
    fireEvent.mouseEnter(card);
    const expected = trackHint(mascot, guardians, 0).en;
    await waitFor(() => expect(bubble.textContent).toContain(expected.slice(0, 24)), { timeout: 4000 });
    // a second look gives the next hint, keyboard focus works too, leaving restores his tips
    fireEvent.mouseLeave(card);
    const kidsCard = screen.getByText(kids.name.en).closest('a');
    fireEvent.focus(kidsCard);
    const kidsHint = trackHint(mascot, kids, 0).en;
    await waitFor(() => expect(bubble.textContent).toContain(kidsHint.slice(0, 24)), { timeout: 4000 });
    fireEvent.blur(kidsCard);
    await waitFor(() => expect(bubble.textContent).not.toContain(kidsHint.slice(0, 24)), { timeout: 4000 });
  });

  it('renders in English when the shell says so', async () => {
    renderApp('/', { locale: 'en' });
    const guardians = fixture('tracks').items.find((t) => t.id === 'guardians');
    await waitFor(() => expect(screen.getByText(guardians.name.en)).toBeInTheDocument());
    expect(screen.getAllByRole('link', { name: /eLearning/ })[0]).toHaveAttribute('href', '/');
  });

  it('lists the guardians missions with their tone classes', async () => {
    renderApp('/guardians');
    const first = fixture('missions').items[0];
    await waitFor(() => expect(screen.getByText(first.name.ka)).toBeInTheDocument());
    const card = screen.getByText(first.name.ka).closest('a');
    expect(card.className).toContain(`tone-${first.color}`);
  });

  it('shows the mission briefing and starts the first round', async () => {
    renderApp('/guardians/mission/g1');
    const mission = fixture('missions/g1');
    await waitFor(() => expect(screen.getByText(mission.brief.ka)).toBeInTheDocument());
    screen.getByRole('button', { name: /→/ }).click();
    await waitFor(() => expect(document.querySelector('.play-card')).not.toBeNull());
  });

  it('renders a parent/teacher read as a lesson of the Teachers & Parents course', async () => {
    renderApp('/learn/teachers-parents/a1', { locale: 'en' });
    const lesson = fixture('courses/teachers-parents/lessons/a1');
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: lesson.title.en })).toBeInTheDocument());
    expect(document.querySelector('.article-body .callout')).not.toBeNull();
    expect(screen.getByRole('button', { name: /Print this page/ })).toBeInTheDocument();
  });

  it('sends the old article links to the course', async () => {
    renderApp('/parents/a1', { locale: 'en' });
    const lesson = fixture('courses/teachers-parents/lessons/a1');
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: lesson.title.en })).toBeInTheDocument());
    renderApp('/parents', { locale: 'en' });
    const course = fixture('courses/teachers-parents');
    await waitFor(() => expect(screen.getByRole('heading', { level: 2, name: course.title.en })).toBeInTheDocument());
  });

  it('shows the emergency page with the configured number', async () => {
    renderApp('/emergency', { emergencyPhone: '112' });
    await waitFor(() => expect(screen.getByRole('link', { name: /112/ })).toHaveAttribute('href', 'tel:112'));
  });

  it('hides the IO chat behind the feature flag', async () => {
    renderApp('/io-chat', { locale: 'en' });
    await waitFor(() => expect(screen.getByText('Page not found')).toBeInTheDocument());
  });

  it('shows a friendly 404 for unknown routes', async () => {
    renderApp('/nope/nothing', { locale: 'en' });
    await waitFor(() => expect(screen.getByText('Page not found')).toBeInTheDocument());
  });
});
