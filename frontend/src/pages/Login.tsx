import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      await api.post("/api/auth/login", { password: pw });
      onLogin();
    } catch (x) {
      setErr((x as Error).message);
    }
  };
  return (
    <div className="login">
      <form onSubmit={submit} className="card">
        <h1>정보화 설계 도우미</h1>
        <p className="muted">관리자 비밀번호로 로그인하세요.</p>
        <label className="field">
          <span className="field-label">비밀번호</span>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus autoComplete="current-password" />
        </label>
        {err && <div className="error">{err}</div>}
        <button className="primary" type="submit">
          로그인
        </button>
      </form>
    </div>
  );
}
