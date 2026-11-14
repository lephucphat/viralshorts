/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Every colour is a channel triplet defined once per theme in
        // src/tokens.css (--c-*), so alpha modifiers like bg-brass/10 compile
        // AND the theme can switch at runtime without rebuilding.
        paper: "oklch(var(--c-paper) / <alpha-value>)",
        paper2: "oklch(var(--c-paper2) / <alpha-value>)",
        paper3: "oklch(var(--c-paper3) / <alpha-value>)",
        ink: "oklch(var(--c-ink) / <alpha-value>)",
        ink2: "oklch(var(--c-ink2) / <alpha-value>)",
        muted: "oklch(var(--c-muted) / <alpha-value>)",
        brass: "oklch(var(--c-brass) / <alpha-value>)",
        brassink: "oklch(var(--c-brassink) / <alpha-value>)",
        brass2: "oklch(var(--c-brass2) / <alpha-value>)",
        scorehi: "oklch(var(--c-score-hi) / <alpha-value>)",
        scoremid: "oklch(var(--c-score-mid) / <alpha-value>)",
        scorelo: "oklch(var(--c-score-lo) / <alpha-value>)",
        coral: "oklch(var(--c-coral) / <alpha-value>)",
        ok: "oklch(var(--c-ok) / <alpha-value>)",
        warn: "oklch(var(--c-warn) / <alpha-value>)",
        danger: "oklch(var(--c-danger) / <alpha-value>)",
        // legacy aliases so untouched files degrade gracefully
        background: "oklch(var(--c-paper) / <alpha-value>)",
        surface: "oklch(var(--c-paper2) / <alpha-value>)",
        primary: "oklch(var(--c-brass) / <alpha-value>)",
        accent: "oklch(var(--c-coral) / <alpha-value>)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        sans: "var(--font-body)",
        serif: "var(--font-display)",
        mono: "var(--font-mono)",
      },
      borderColor: {
        rule: "var(--color-rule)",
        rule2: "var(--color-rule-2)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
        cta: "var(--shadow-cta)",
      },
      backgroundImage: {
        brand: "var(--gradient-brand)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        input: "var(--radius-input)",
      },
      fontSize: {
        micro: ["12.5px", { letterSpacing: "0.04em" }],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade': 'fadeIn 0.4s var(--ease-out)',
        // mobile shell: the nav drawer flies in from the edge, sheets rise
        'slide-in-left': 'slideInLeft 0.24s var(--ease-out)',
        'sheet-up': 'sheetUp 0.26s var(--ease-out)',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideInLeft: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        sheetUp: {
          from: { transform: 'translateY(12px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
