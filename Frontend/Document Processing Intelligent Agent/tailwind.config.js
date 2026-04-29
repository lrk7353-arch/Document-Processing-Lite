/** @type {import('tailwindcss').Config} */
export default {
  // 告诉 Tailwind 扫描哪些文件，生成对应的样式
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}", // 包含 JS/TS/JSX/TSX 文件
  ],
  theme: {
    extend: {
      // 如果需要自定义颜色、字体或 spacing，可以在这里扩展
      colors: {
        primary: "#3b82f6", // 示例：自定义主色
        secondary: "#f97316",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [
    // 如果需要 Tailwind 插件可以加在这里
  ],
}
