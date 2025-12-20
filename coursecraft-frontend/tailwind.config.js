/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: "var(--color-surface)",
        "surface-alt": "var(--color-surface-alt)",
        "on-surface": "var(--color-on-surface)",
        "on-surface-strong": "var(--color-on-surface-strong)",

        primary: "var(--color-primary)",
        "on-primary": "var(--color-on-primary)",

        secondary: "var(--color-secondary)",
        "on-secondary": "var(--color-on-secondary)",

        outline: "var(--color-outline)",
        "outline-strong": "var(--color-outline-strong)",

        info: "var(--color-info)",
        "on-info": "var(--color-on-info)",
        success: "var(--color-success)",
        "on-success": "var(--color-on-success)",
        warning: "var(--color-warning)",
        "on-warning": "var(--color-on-warning)",
        danger: "var(--color-danger)",
        "on-danger": "var(--color-on-danger)",
      },
      borderRadius: {
        radius: "var(--radius-radius)",
      },
    },
  },
  plugins: [],
};
// Without this, Tailwind utilities won’t exist.