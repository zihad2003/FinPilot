/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a2332",
        paper: "#f3efe4",
        card: "#fffdf8",
        line: "#e4dccb",
        pine: "#1f6b4a",
        moss: "#e7f2eb",
        clay: "#8f3d2b",
        sand: "#a16207",
      },
      fontFamily: {
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Outfit", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
