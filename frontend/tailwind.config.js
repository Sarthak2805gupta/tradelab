/**
 * Tailwind build config — produces static/css/tailwind.css.
 *
 * The site used to load the Tailwind "Play CDN" script, which downloads
 * ~400 KB of JavaScript and compiles every class in the visitor's browser
 * before the page can paint. This config reproduces the exact theme that
 * base.html passed to the CDN (`tailwind.config = {...}`), so the compiled
 * stylesheet renders identically.
 *
 * Rebuild after adding new classes to templates:
 *   npx tailwindcss@3.4.17 -c frontend/tailwind.config.js -i frontend/tailwind.input.css -o static/css/tailwind.css --minify
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        base:   'var(--sa-base, #07090f)',
        panel:  'var(--sa-panel, #0f1420)',
        panel2: 'var(--sa-panel2, #151c2c)',
        accent:  'var(--sa-accent, #34d399)',
        accent2: 'var(--sa-accent2, #fbbf24)',
        danger:  'var(--sa-danger, #fb7185)',
        muted:   'var(--sa-muted, #8a94a7)',
        ink:     'var(--sa-ink, #e6ebf3)',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
};
