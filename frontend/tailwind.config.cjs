/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f5f0e8",
        paper: "#fffaf2",
        ink: "#161514",
        clay: "#cf5e30",
        cedar: "#1d5f50",
        dusk: "#22354d",
        line: "#e2d3bf",
      },
      fontFamily: {
        sans: ["Space Grotesk", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 10px 32px rgba(22, 21, 20, 0.08)",
      },
      animation: {
        rise: "rise .45s ease-out both",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
