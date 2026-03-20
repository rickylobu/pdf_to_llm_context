/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Mapped to CSS variables so the dynamic theme from theme.json applies.
        // Use these as fallbacks only — runtime theming is done via CSS vars.
        primary:    'var(--color-primary)',
        secondary:  'var(--color-secondary)',
        accent:     'var(--color-accent)',
        surface:    'var(--color-surface)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      maxWidth: {
        reader: 'var(--reader-max-width)',
      },
    },
  },
  plugins: [],
}
