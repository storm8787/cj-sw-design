import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const src = (p: string) => fileURLToPath(new URL(`./src/${p}`, import.meta.url));

/**
 * 정적 시연판(`vite build --mode demo`) 전용: 서버 API·로그인 모듈을 시연용 모듈로 바꿔 끼운다.
 * - src/api.ts → src/demo/api.ts (미리 만든 정적 JSON만 읽음, 저장·실행 거절)
 * - src/App.tsx → src/demo/DemoApp.tsx (로그인 없이 샘플 선택·읽기 전용 화면)
 * 일반 빌드에는 이 플러그인이 없으므로 시연 코드·데이터가 실제 앱 번들에 들어가지 않고, URL로 시연 모드를 켤 수도 없다.
 */
function demoSwap(): Plugin {
  const swap: Record<string, string> = { [src("api.ts")]: src("demo/api.ts"), [src("App.tsx")]: src("demo/DemoApp.tsx") };
  return {
    name: "swd-demo-swap",
    enforce: "pre",
    buildStart() {
      if (!existsSync(fileURLToPath(new URL("./demo-public/demo-data/manifest.json", import.meta.url))))
        this.error("시연 샘플 데이터가 없습니다. 먼저 `npm run demo:data`(= cd backend && uv run python -m tools.demo_data)로 생성하세요.");
    },
    async resolveId(source, importer, options) {
      if (!importer || importer.startsWith(src("demo/"))) return null;
      const r = await this.resolve(source, importer, { ...options, skipSelf: true });
      return r && swap[r.id] ? swap[r.id] : null;
    },
    transformIndexHtml: (html) =>
      html.replace("<title>정보화 설계 도우미</title>", '<title>정보화 설계 도우미 — 샘플 시연판</title>\n    <meta name="description" content="가상 데이터로 기능 흐름과 결과를 보여주는 정적 시연판(AI 호출·서버 저장 없음)" />'),
  };
}

export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    // 시연판은 GitHub 프로젝트 Pages 경로(/cj-sw-design/)에서 열린다. 다른 경로는 DEMO_BASE로 지정.
    base: demo ? process.env.DEMO_BASE || "/cj-sw-design/" : "/",
    publicDir: demo ? "demo-public" : "public",
    plugins: [react(), ...(demo ? [demoSwap()] : [])],
    server: {
      port: 5173,
      proxy: { "/api": "http://127.0.0.1:8000" },
    },
    build: { outDir: demo ? "dist-demo" : "dist", sourcemap: false, emptyOutDir: true },
  };
});
