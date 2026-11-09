import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        furni: {
          primary: '#173B35',
          'primary-hover': '#112C28',
          secondary: '#285F4D',
          'secondary-hover': '#214D3E',
          accent: '#A47E53', // Warm walnut accent
          bg: '#F4F6F3',
          surface: '#FFFFFF',
          text: '#252D29',
          muted: '#63736C',
          border: '#DCE2DC',
          'border-light': '#EAEFE9',
          danger: '#DC2626',
          warning: '#D97706',
          success: '#16A34A',
          info: '#2563EB',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(23, 59, 53, 0.05), 0 1px 2px -1px rgba(23, 59, 53, 0.05)',
        'card-hover': '0 8px 16px -4px rgba(23, 59, 53, 0.08), 0 4px 6px -2px rgba(23, 59, 53, 0.03)',
      },
    },
  },
  plugins: [],
};

export default config;
