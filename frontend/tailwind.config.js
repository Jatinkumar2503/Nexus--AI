/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#09090b', // Custom zinc-950 dark background
        card: 'rgba(24, 24, 27, 0.65)', // Zinc-900 transparent for glassmorphism
        border: 'rgba(63, 63, 70, 0.4)', // Zinc-700 translucent
        primary: '#3b82f6', // Premium bright blue
        accent: '#10b981', // Clean green for ok status
        warning: '#f59e0b', // Warning yellow
        danger: '#ef4444', // Alert red
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
        glow: '0 0 15px rgba(59, 130, 246, 0.5)',
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}
