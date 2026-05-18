import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx,html}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Avenir Next"', '"Helvetica Neue"', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
      colors: {
        synkora: {
          50:  '#eefbf6',
          100: '#daf6ea',
          200: '#b9edd9',
          300: '#97e5ca',
          400: '#79dfbc',
          500: '#55c9a0',
          600: '#34ad82',
          700: '#2d8b69',
          800: '#276e55',
          900: '#225446',
        },
        brand: {
          canvas: '#f7f2e7',
          panel: '#fffaf1',
          surface: '#f2ebde',
          line: '#ddd2c4',
          ink: '#171717',
          muted: '#6d675f',
        },
      },
      boxShadow: {
        card: '0 14px 40px rgba(23, 23, 23, 0.08)',
        soft: '0 8px 24px rgba(23, 23, 23, 0.06)',
      },
      animation: {
        'fade-in':    'fadeIn 0.18s ease-out',
        'slide-up':   'slideUp 0.22s cubic-bezier(0.16,1,0.3,1)',
        'bounce-dot': 'bounceDot 1.2s ease-in-out infinite',
        'blink':      'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px) scale(0.98)' },
          to:   { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        bounceDot: {
          '0%, 80%, 100%': { transform: 'scale(0.55)', opacity: '0.35' },
          '40%':            { transform: 'scale(1)',    opacity: '1' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
