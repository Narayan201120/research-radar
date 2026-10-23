import type { Config } from "tailwindcss";

/**
 * Radar scope design system. Every color lives here, nowhere else.
 * deep/panel/well are the blueprint blues; ice/haze carry text;
 * line/linebright draw the instrument linework; signal is the one
 * amber reserved for the sweep, active states, and saved papers.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        deep: "#0E3050",
        panel: "#143C60",
        well: "#0A2438",
        ice: "#EAF4FC",
        haze: "#A9C6DC",
        line: "#3E6E96",
        linebright: "#9FC4DE",
        signal: "#FFB03C",
        signaldeep: "#E89423",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
