import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0f10",
        panel: "#11191a",
        ink: "#edf4ef",
        accent: "#d7ff64",
        caution: "#ffb66b",
        danger: "#ff6a5f"
      },
      boxShadow: {
        panel: "0 24px 80px rgba(0, 0, 0, 0.35)"
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Aptos", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "Consolas", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
