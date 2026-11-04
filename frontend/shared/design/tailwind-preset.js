// Shared Tailwind preset: maps utility names onto the channels in tokens.css.
// Names the dashboard already used (surface-solid, border-subtle, primary-muted…)
// are kept as aliases so screens that were not redrawn still pick up the new palette.
const c = (name) => `oklch(var(--c-${name}) / <alpha-value>)`
const fixed = (name, alpha) => `oklch(var(--c-${name}) / ${alpha})`

export default {
  theme: {
    extend: {
      colors: {
        bg: c('bg'),
        sidebar: c('sidebar'),
        surface: c('surface'),
        'surface-2': c('surface-2'),
        'surface-3': c('surface-3'),
        'surface-solid': c('surface'),
        border: c('border'),
        'border-strong': c('border-strong'),
        field: c('field'),
        'border-subtle': fixed('border', 0.6),
        text: c('text'),
        'text-secondary': c('text-secondary'),
        muted: c('muted'),
        primary: c('primary'),
        'primary-hover': c('primary-hover'),
        'primary-fg': c('primary-fg'),
        'primary-muted': fixed('primary', 0.07),
        'primary-glow': fixed('primary', 0.12),
        accent: c('accent'),
        'accent-soft': c('accent-soft'),
        focus: c('focus'),
        success: c('success'),
        warning: c('warning'),
        danger: c('danger'),
        info: c('info'),
        scrim: c('scrim'),
      },
      fontFamily: {
        sans: ['General Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SF Mono', 'Cascadia Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        sm: '6px',
        md: '8px',
        lg: '10px',
        xl: '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      transitionTimingFunction: {
        out: 'var(--ease-out)',
      },
      transitionDuration: {
        micro: '120ms',
        short: '220ms',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        caret: { '0%, 100%': { opacity: '0.25' }, '50%': { opacity: '1' } },
      },
      animation: {
        'fade-in': 'fadeIn 220ms var(--ease-out)',
        caret: 'caret 1s ease-in-out infinite',
        'spin-slow': 'spin 1.2s linear infinite',
      },
    },
  },
}
