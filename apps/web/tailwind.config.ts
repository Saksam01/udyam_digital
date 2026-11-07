import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#FFF2F2", 100: "#FFE1E1", 200: "#FFC9CB", 500: "#ED1C24", 600: "#D2131B", 700: "#A80F15", 800: "#C0111A" },
        ink: { 900: "#17171C", 700: "#3E3E47", 500: "#6B6B76", 400: "#9696A0" },
        line: { 100: "#F0F0F3", 200: "#E6E6EB" },
        surface: { 0: "#FFFFFF", 50: "#F6F6F8" },
        success: { 50: "#E3F6EC", 600: "#0E8A4E" },
        warning: { 50: "#FFF1DC", 600: "#B86A00" },
        danger: { 50: "#FDECEC", 600: "#C62828" },
        info: { 50: "#E6F0FF", 600: "#1C64D8" },
        aqua: { 50: "#E0F5F4", 600: "#0F7C78" },
        slate2: { 50: "#EEF0F4", 600: "#3E3E47" },
        sidebar: { 900: "#1A1A1F", 800: "#26262D", 700: "#2E2E36" },
      },
      fontFamily: {
        sans: [
          "Anek Latin",
          "Anek Devanagari",
          "Anek Tamil",
          "Anek Telugu",
          "Anek Bangla",
          "Anek Kannada",
          "Anek Gurmukhi",
          "system-ui",
          "sans-serif",
        ],
      },
      borderRadius: {
        card: "20px",
        btn: "14px",
        hero: "28px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(23,23,28,.04), 0 8px 24px -12px rgba(23,23,28,.10)",
        float: "0 16px 48px -16px rgba(23,23,28,.28)",
        bar: "0 -1px 0 #E6E6EB, 0 -12px 32px -16px rgba(23,23,28,.18)",
      },
    },
  },
  plugins: [],
};

export default config;
