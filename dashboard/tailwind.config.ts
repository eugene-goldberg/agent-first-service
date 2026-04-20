import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "trace-thought": "#60a5fa",
        "trace-action": "#f59e0b",
        "trace-observation": "#10b981",
        "trace-final": "#a855f7",
        "trace-error": "#ef4444",
      },
    },
  },
  plugins: [],
};

export default config;
