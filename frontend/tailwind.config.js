/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // 02_frontend_spec.md § 6.1: header height is 64px.
      spacing: { header: "64px" },
      // § 8: desktop content caps at 1024px.
      maxWidth: { content: "1024px" },
    },
  },
  plugins: [],
};
