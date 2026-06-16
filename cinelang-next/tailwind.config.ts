import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          50: '#fefdfb',
          100: '#fafaf8',
          200: '#f5f0eb',
          300: '#ede6dd',
        },
        cinema: {
          50:  '#fef3ee',
          100: '#fde3d1',
          200: '#fbc4a2',
          300: '#f89d6d',
          400: '#f47036',
          500: '#e85d2f',
          600: '#d44922',
          700: '#b2381b',
          800: '#8e2f19',
          900: '#762b1a',
        },
        warm: {
          50:  '#fafaf9',
          100: '#f5f5f4',
          200: '#e7e5e4',
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',
        },
      },
      fontFamily: {
        heading: ['"Playfair Display"', 'Georgia', 'serif'],
        body:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      boxShadow: {
        'warm-sm': '0 1px 3px 0 rgba(28,25,23,0.07)',
        'warm':    '0 4px 12px 0 rgba(28,25,23,0.08)',
        'warm-lg': '0 8px 24px 0 rgba(28,25,23,0.10)',
        'warm-xl': '0 16px 40px 0 rgba(28,25,23,0.12)',
      },
      animation: {
        'fade-in':   'fadeIn .25s ease',
        'slide-up':  'slideUp .3s ease',
        'flip':      'flip .5s ease',
        'eq':        'eq .9s ease-in-out infinite',
        'shimmer':   'shimmer 1.5s linear infinite',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:   { from: { opacity: '0' },                        to: { opacity: '1' } },
        slideUp:  { from: { opacity: '0', transform: 'translateY(10px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        eq:       { '0%,100%': { height: '4px' }, '25%': { height: '14px' }, '50%': { height: '8px' }, '75%': { height: '18px' } },
        shimmer:  { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        pulseDot: { '0%,100%': { opacity: '1' }, '50%': { opacity: '.4' } },
      },
    },
  },
  plugins: [],
}

export default config
