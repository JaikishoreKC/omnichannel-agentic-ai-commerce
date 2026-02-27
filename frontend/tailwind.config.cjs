/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Premium Palette
        brand: {
          light: "#4f46e5", // Indigo 600
          DEFAULT: "#4338ca", // Indigo 700
          dark: "#3730a3", // Indigo 800
        },
        surface: {
          50: "#ffffff",
          100: "#fafafa",
          200: "#f5f5f5",
          300: "#e5e5e5",
          400: "#a3a3a3",
          500: "#737373",
        },
        accent: {
          light: "#ec4899", // Pink 500
          DEFAULT: "#db2777", // Pink 600
          dark: "#be185d", // Pink 700
        },
        canvas: "#ffffff",
        paper: "#f8fafc",
        ink: "#0f172a", // Slate 900
        clay: "#f97316", // Orange 500
        cedar: "#10b981", // Emerald 500
        dusk: "#334155", // Slate 700
        line: "#e2e8f0",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "system-ui", "sans-serif"],
      },
      boxShadow: {
        premium: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        glass: "0 8px 32px 0 rgba(31, 38, 135, 0.07)",
        panel: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
      },
      animation: {
        rise: "rise .45s ease-out both",
        "fade-in": "fadeIn .3s ease-out both",
        "slide-up": "slideUp .4s ease-out both",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(20px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
