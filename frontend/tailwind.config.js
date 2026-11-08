/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "var(--color-primary)",
          active: "var(--color-primary-active)",
        },
        canvas: {
          DEFAULT: "var(--color-canvas)",
          soft: "var(--color-canvas-soft)",
          deep: "var(--color-canvas-deep)",
        },
        surface: {
          card: "var(--color-surface-card)",
          strong: "var(--color-surface-strong)",
          dark: "var(--color-surface-dark)",
          "dark-elevated": "var(--color-surface-dark-elevated)",
        },
        hairline: {
          DEFAULT: "var(--color-hairline)",
          soft: "var(--color-hairline-soft)",
          strong: "var(--color-hairline-strong)",
        },
        ink: {
          DEFAULT: "var(--color-ink)",
        },
        body: {
          DEFAULT: "var(--color-body)",
          strong: "var(--color-body-strong)",
        },
        muted: {
          DEFAULT: "var(--color-muted)",
          soft: "var(--color-muted-soft)",
        },
        "on-primary": "var(--color-on-primary)",
        "on-dark": "var(--color-on-dark)",
        "on-dark-soft": "var(--color-on-dark-soft)",
        orb: {
          mint: "var(--color-gradient-mint)",
          peach: "var(--color-gradient-peach)",
          lavender: "var(--color-gradient-lavender)",
          sky: "var(--color-gradient-sky)",
          rose: "var(--color-gradient-rose)",
        },
        semantic: {
          success: "var(--color-semantic-success)",
          error: "var(--color-semantic-error)",
        },
      },
      fontFamily: {
        sans: ['"Poppins"', '"Inter"', 'system-ui', 'sans-serif'],
        display: ['"Poppins"', '"Inter"', 'system-ui', 'sans-serif'],
        body: ['"Poppins"', '"Inter"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        pill: "9999px",
        xxl: "24px",
        xl: "16px",
        lg: "12px",
        md: "8px",
        sm: "6px",
        xs: "4px",
      },
      boxShadow: {
        soft: "0 4px 16px rgba(0, 0, 0, 0.04)",
      },
      spacing: {
        section: "96px",
      },
    },
  },
  plugins: [],
}
