/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: '#1dd89b',
        'brand-accent': '#60a5fa',
        bg: '#060a10',
        surface: 'rgba(14, 20, 30, 0.85)',
        muted: '#6b7d96',
        text: '#e8edf4',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
