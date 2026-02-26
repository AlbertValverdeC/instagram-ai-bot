/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0f1a',
        card: '#111827',
        code: '#1a2236',
        border: '#1e293b',
        text: '#e2e8f0',
        dim: '#94a3b8',
        accent: '#00c8ff',
        purple: '#c084fc',
        green: '#34d399',
        orange: '#fb923c',
        red: '#f87171'
      }
    }
  },
  plugins: []
};
