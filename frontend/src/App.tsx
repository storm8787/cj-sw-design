import { useCallback, useEffect, useState } from "react";
import { api, setUnauthorizedHandler } from "./api";
import { Header, Skeleton } from "./components/Frame";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Workspace from "./pages/Workspace";
import type { SystemInfo } from "./types";

// 간단한 해시 라우팅: #/ (홈), #/p/<프로젝트ID>/<단계>
function parseHash(): { pid: string | null; step: string } {
  const m = location.hash.match(/^#\/p\/([A-Za-z0-9]+)(?:\/(\w+))?/);
  return m ? { pid: m[1], step: m[2] || "overview" } : { pid: null, step: "" };
}

export default function App() {
  const [auth, setAuth] = useState<"unknown" | "in" | "out">("unknown");
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [route, setRoute] = useState(parseHash());

  const loadSystem = useCallback(async () => {
    const me = await api.get<{ authenticated: boolean }>("/api/auth/me");
    if (!me.authenticated) return setAuth("out");
    setSystem(await api.get<SystemInfo>("/api/system"));
    setAuth("in");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuth("out"));
    loadSystem().catch(() => setAuth("out"));
    const h = () => setRoute(parseHash());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, [loadSystem]);

  if (auth === "unknown") return <Skeleton />;
  if (auth === "out" || !system) return <Login onLogin={() => loadSystem()} />;

  const logout = async () => {
    await api.post("/api/auth/logout");
    setAuth("out");
  };

  return (
    <div className="app">
      <Header>
        <span className={`mode ${system.ai.is_real_ai ? "mode-ai" : "mode-sample"}`} title={system.ai.is_real_ai ? `AI 모델: ${system.ai.model}` : "AI 키가 없거나 꺼져 있어 서버 규칙으로 질문·초안을 만듭니다."}>
          {system.mode_label}
        </span>
        <span className="spacer" />
        {!system.auth_disabled && (
          <button className="link light" onClick={logout}>
            로그아웃
          </button>
        )}
        {system.auth_disabled && <span className="mode mode-warn">개발용: 인증 꺼짐</span>}
      </Header>
      <main id="content" tabIndex={-1}>{route.pid ? <Workspace key={route.pid} pid={route.pid} step={route.step} system={system} /> : <Home system={system} />}</main>
    </div>
  );
}
