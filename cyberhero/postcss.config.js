// Every selector is prefixed with `.cyberhero-root` so CyberHero styles can
// never leak into the Bootstrap-based eLearning host page (and vice versa).
import prefixSelector from 'postcss-prefix-selector';

const ROOT = '.cyberhero-root';

export default {
  plugins: [
    prefixSelector({
      prefix: ROOT,
      // the home-page IO host lives outside .cyberhero-root; its stylesheet
      // is scoped by hand under .io-host-root (see src/styles/io-host.css)
      ignoreFiles: [/io-host\.css$/],
      // `@keyframes` step selectors (from/to/percentages) are never touched by
      // the plugin; the transform below handles the root and html/body.
      transform(prefix, selector, prefixedSelector) {
        const trimmed = selector.trim();
        if (trimmed === ROOT || trimmed.startsWith(`${ROOT}.`) || trimmed.startsWith(`${ROOT}:`)
          || trimmed.startsWith(`${ROOT} `) || trimmed.startsWith(`${ROOT}[`)) {
          return trimmed;
        }
        if (trimmed === 'html' || trimmed === 'body' || trimmed === ':root') {
          return ROOT;
        }
        return prefixedSelector;
      },
    }),
  ],
};
