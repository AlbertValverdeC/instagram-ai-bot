/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#00bfff',
        'background-dark': '#0a0f1a',
        'secondary-dark': '#131b24',
        'surface-dark': '#1c2630',
        'border-dark': '#2a3642',
        'text-subtle': '#94a3b8',
        // Keep old aliases for modals that still use them
        bg: '#0a0f1a',
        card: '#131b24',
        code: '#1c2630',
        border: '#2a3642',
        text: '#e2e8f0',
        dim: '#94a3b8',
        accent: '#00bfff',
        purple: '#c084fc',
        green: '#34d399',
        orange: '#fb923c',
        red: '#f87171',
      },
      fontFamily: {
        display: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
