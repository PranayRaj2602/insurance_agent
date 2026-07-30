/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:     { deep: '#0d0f1a', card: '#161827', hover: '#1e2235' },
        teal:   { DEFAULT: '#2dd4bf', dark: '#14b8a6', light: '#5eead4' },
        orange: { DEFAULT: '#f5a623', dark: '#d97706' },
        border: '#252840',
        hi:     '#f0f2ff',
        mid:    '#9ca3b8',
        muted:  '#6b7280',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
