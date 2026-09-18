import { describe, expect, it } from 'vitest';
import { getMascotContext, missionReaction } from '../src/mascot/mascotContext.js';
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
