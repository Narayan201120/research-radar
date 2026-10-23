import type { Config } from "tailwindcss";

// Locked token source of truth — see /design/brief.md.
// No subagent may invent colors, radii, shadows, or type values
// outside this file. Ledger palette: paper ground, ink text,
// oxblood signal accent (single accent only), sage secondary,
// rule hairlines. No shadows for hierarchy — rules do the work.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#F7F6F1",
          deep: "#ECEAE2",
        },
        ink: {
          DEFAULT: "#1B2431",
        },
        signal: {
          DEFAULT: "#8C2B2B",
          dark: "#732222",
        },
        sage: {
          DEFAULT: "#5F6E64",
        },
        rule: {
          DEFAULT: "#DFDCD2",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;