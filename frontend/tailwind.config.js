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
        // Instagram gradient palette
        'ig-pink': '#E1306C',
        'ig-purple': '#833AB4',
        'ig-orange': '#F77737',
        'ig-yellow': '#FCAF45',
        purple: '#c084fc',
        green: '#34d399',
        orange: '#fb923c',
        red: '#f87171',
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      backgroundImage: {
        'ig-gradient': 'linear-gradient(135deg, #833AB4 0%, #E1306C 50%, #F77737 100%)',
        'ig-gradient-subtle':
          'linear-gradient(135deg, rgba(131,58,180,0.15) 0%, rgba(225,48,108,0.15) 50%, rgba(247,119,55,0.15) 100%)',
        'ig-gradient-border':
          'linear-gradient(135deg, rgba(131,58,180,0.4) 0%, rgba(225,48,108,0.4) 50%, rgba(247,119,55,0.4) 100%)',
      },
      boxShadow: {
        'glow-primary': '0 0 15px rgba(0,191,255,0.25)',
        'glow-ig': '0 0 20px rgba(225,48,108,0.3)',
      },
    },
  },
  plugins: [],
};
