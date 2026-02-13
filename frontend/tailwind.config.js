/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'brand': '#6366f1',         // indigo-500
        'brand-dark': '#4338ca',    // indigo-700
        'core': '#3b82f6',          // blue-500   — core tasks
        'deferrable': '#f59e0b',    // amber-500  — deferrable tasks
        'deletion': '#ef4444',      // red-500    — deletion candidates
        'success': '#22c55e',       // green-500
        'muted': '#94a3b8',         // slate-400
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
