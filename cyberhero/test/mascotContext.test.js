import { describe, expect, it } from 'vitest';
import { getMascotContext, missionReaction, trackHint } from '../src/mascot/mascotContext.js';
import { fixture } from './helpers.js';

const mascot = fixture('mascot');

describe('mascot context', () => {
  it('matches tips to the mission topics', () => {
    const ctx = getMascotContext('/guardians/mission/g1', mascot);
    expect(ctx.tips.length).toBeGreaterThan(0);
    expect(ctx.tips.every((tip) => tip.topics.includes('phishing'))).toBe(true);
  });

  it('talks to adults in the parents hub', () => {
    const ctx = getMascotContext('/parents', mascot);
    expect(ctx.tips.some((tip) => tip.topics.includes('parents'))).toBe(true);
  });

  it('uses the context openers', () => {
    expect(getMascotContext('/guardians', mascot).opener).toEqual(mascot.reactions.guardians);
    expect(getMascotContext('/track/kids', mascot).opener).toEqual(mascot.reactions.building);
    expect(getMascotContext('/', mascot).opener).toBeUndefined();
  });

  it('survives an empty payload', () => {
    expect(getMascotContext('/guardians', undefined).tips).toEqual([]);
    expect(missionReaction({ reactions: {} }, 3)).toBeNull();
    expect(missionReaction(mascot, 1)).toEqual(mascot.reactions.mission[1 % mascot.reactions.mission.length]);
  });
});

describe('track hints', () => {
  const tier = { id: 'kids', intro: { en: 'Short missions with Fufu.', ka: 'მოკლე მისიები ფუფუსთან.' }, desc: { en: 'Fun games.', ka: 'თამაშები.' } };

  it('walks through the admin-edited lines for the hovered track', () => {
    const lines = [
      { en: 'one', ka: 'ერთი' },
      { en: 'two', ka: 'ორი' },
    ];
    const withHints = { ...mascot, reactions: { ...mascot.reactions, tracks: { kids: lines } } };
    expect(trackHint(withHints, tier, 0)).toEqual(lines[0]);
    expect(trackHint(withHints, tier, 1)).toEqual(lines[1]);
    expect(trackHint(withHints, tier, 2)).toEqual(lines[0]);
  });

  it('serves the seeded hints for every track', () => {
    for (const id of ['guardians', 'parents', 'kids', 'cadets', 'campus', 'work', 'seniors']) {
      const first = trackHint(mascot, { id }, 0);
      expect(first?.en, id).toBeTruthy();
      expect(first?.ka, id).toBeTruthy();
      expect(trackHint(mascot, { id }, 3)).toEqual(first); // the pool wraps around
    }
  });

  it('falls back to the track intro, then its description, then nothing (admin-created tracks)', () => {
    const fresh = { ...tier, id: 'admin-made' }; // no hints in the mascot payload
    expect(trackHint(mascot, fresh, 0)).toEqual(tier.intro);
    expect(trackHint(mascot, { id: 'x', desc: tier.desc }, 3)).toEqual(tier.desc);
    expect(trackHint(mascot, { id: 'x' }, 0)).toBeNull();
    expect(trackHint(undefined, fresh, 0)).toEqual(tier.intro);
    expect(trackHint(mascot, null, 0)).toBeNull();
  });

  it('ignores blank lines an admin left behind', () => {
    const withBlank = { reactions: { tracks: { kids: [{ en: '', ka: '' }, { en: 'real', ka: 'ნამდვილი' }] } } };
    expect(trackHint(withBlank, tier, 0)).toEqual({ en: 'real', ka: 'ნამდვილი' });
  });
});
