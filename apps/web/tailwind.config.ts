import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#101214",
          900: "#171a1f",
          800: "#232832",
          700: "#313846",
          600: "#475163"
        },
        signal: {
          ok: "#16875b",
          warn: "#b7791f",
          error: "#c24135"
        }
      },
      boxShadow: {
        panel: "0 1px 2px rgb(16 18 20 / 0.08), 0 10px 30px rgb(16 18 20 / 0.05)"
      }
    }
  },
  plugins: []
};

export default config;

