import typography from '@tailwindcss/typography'
import preset from '../shared/design/tailwind-preset.js'

/** @type {import('tailwindcss').Config} */
export default {
  presets: [preset],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      spacing: {
        sidebar: '260px',
      },
    },
  },
  plugins: [typography],
}
