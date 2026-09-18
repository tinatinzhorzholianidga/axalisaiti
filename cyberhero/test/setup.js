import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  try {
    localStorage.clear();
  } catch {
    /* jsdom without storage */
  }
});

// jsdom lacks matchMedia (used by the reduced-motion hook) and WebGL
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false;
    },
  });
}
window.scrollTo = () => {};
HTMLCanvasElement.prototype.getContext = () => null;
