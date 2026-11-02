"""최소 런처 창(tkinter): 첫 비밀번호, 상태, 브라우저 열기, 설정(비밀번호·OpenAI 키), 종료.
업무 화면은 기존 웹 화면(브라우저)을 그대로 쓴다."""
from __future__ import annotations

import os
import queue
import subprocess
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Callable

from . import config as lc
from .keystore import KeystoreError
from .paths import Layout

TITLE = "정보화 설계 도우미 — Windows 시험판"
COST_NOTE = ("AI를 쓰면 입력한 업무 내용과 동의한 문서 원문이 OpenAI 서버로 전송되고, 사용한 만큼 사용료가 청구됩니다. "
             "요청할 때마다 전송 범위를 보여 주고 동의를 받습니다. 키는 이 PC의 현재 Windows 계정에서만 풀리도록 보호(DPAPI)해 저장합니다.")


def _dpi_aware() -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass


class Gui:
    def __init__(self):
        _dpi_aware()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(TITLE)
        font = ("Malgun Gothic", 10) if os.name == "nt" else None
        if font:
            self.root.option_add("*Font", font)
        self.result = ""

    # ---------------------------------------------------------------- 공통
    def error(self, msg: str) -> None:
        messagebox.showerror(TITLE, msg, parent=self.root)

    def info(self, msg: str) -> None:
        messagebox.showinfo(TITLE, msg, parent=self.root)

    def splash(self, text: str) -> Callable[[], None]:
        """시작 중 안내 창. tick()을 부르면 창이 멈추지 않는다."""
        w = tk.Toplevel(self.root)
        w.title(TITLE)
        w.resizable(False, False)
        ttk.Label(w, text=text, padding=24).pack()
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        self._splash = w
        return self.root.update

    def close_splash(self) -> None:
        if getattr(self, "_splash", None):
            self._splash.destroy()
            self._splash = None

    # ---------------------------------------------------------------- 첫 실행
    def ask_first_password(self) -> str | None:
        w = tk.Toplevel(self.root)
        w.title(TITLE + " — 처음 실행")
        w.resizable(False, False)
        frm = ttk.Frame(w, padding=20)
        frm.pack(fill="both")
        ttk.Label(frm, text="처음 실행입니다. 웹 화면 로그인에 쓸 비밀번호를 정해 주세요.", wraplength=420).pack(anchor="w")
        ttk.Label(frm, text=f"· {lc.MIN_PASSWORD}자 이상. 이 PC에만 해시로 저장되며 공용 기본 비밀번호는 없습니다.\n"
                            "· 잊으면 이 창의 [설정]에서 새로 정할 수 있습니다(같은 Windows 계정).",
                  wraplength=420, foreground="#555").pack(anchor="w", pady=(4, 12))
        pw1, pw2 = tk.StringVar(), tk.StringVar()
        ttk.Label(frm, text="비밀번호").pack(anchor="w")
        e1 = ttk.Entry(frm, textvariable=pw1, show="•", width=40)
        e1.pack(anchor="w")
        ttk.Label(frm, text="비밀번호 확인").pack(anchor="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=pw2, show="•", width=40).pack(anchor="w")
        msg = ttk.Label(frm, text="", foreground="#b00020", wraplength=420)
        msg.pack(anchor="w", pady=(8, 0))
        out: dict[str, str | None] = {"pw": None}

        def ok(_e=None):
            try:
                lc.check_password(pw1.get(), pw2.get())
            except lc.ConfigError as e:
                msg.config(text=str(e))
                return
            out["pw"] = pw1.get()
            w.destroy()

        btns = ttk.Frame(frm)
        btns.pack(anchor="e", pady=(12, 0))
        ttk.Button(btns, text="취소", command=w.destroy).pack(side="right")
        ttk.Button(btns, text="시작", command=ok).pack(side="right", padx=6)
        w.bind("<Return>", ok)
        e1.focus_set()
        w.grab_set()
        self.root.wait_window(w)
        return out["pw"]

    # ---------------------------------------------------------------- 실행 중 창
    def run_main(self, url: str, ai_text: str, lay: Layout, cfg: lc.LocalConfig, events: "queue.Queue[str]", jobs: Callable[[], int]) -> str:
        r = self.root
        frm = ttk.Frame(r, padding=20)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="정보화 설계 도우미 (Windows 시험판, 미서명)", font=("Malgun Gothic", 12, "bold") if os.name == "nt" else None).pack(anchor="w")
        ttk.Label(frm, text=f"실행 중 · {url}", foreground="#0a6").pack(anchor="w", pady=(6, 0))
        ttk.Label(frm, text=f"AI: {ai_text}", wraplength=460).pack(anchor="w", pady=(2, 0))
        ttk.Label(frm, text="브라우저 탭을 닫아도 프로그램은 계속 실행됩니다. 다시 보려면 [브라우저 열기]를 누르세요.\n"
                            "끝낼 때는 이 창의 [종료]를 누르세요. 데이터는 이 PC의 사용자 폴더에 저장됩니다.",
                  wraplength=460, foreground="#555").pack(anchor="w", pady=(10, 12))
        row = ttk.Frame(frm)
        row.pack(anchor="w")
        ttk.Button(row, text="브라우저 열기", command=lambda: webbrowser.open(url)).pack(side="left")
        ttk.Button(row, text="설정", command=lambda: self.settings(lay, cfg, jobs)).pack(side="left", padx=6)
        ttk.Button(row, text="데이터 폴더 열기", command=lambda: _open_folder(lay.root)).pack(side="left")
        ttk.Button(row, text="종료", command=lambda: self.quit(jobs)).pack(side="left", padx=6)
        r.protocol("WM_DELETE_WINDOW", lambda: self.quit(jobs))

        def poll():
            try:
                while True:
                    ev = events.get_nowait()
                    if ev == "show":
                        r.deiconify()
                        r.lift()
                        r.attributes("-topmost", True)
                        r.after(300, lambda: r.attributes("-topmost", False))
                    elif ev == "quit":
                        self.result = "quit"
                        r.quit()
                        return
            except queue.Empty:
                pass
            r.after(300, poll)

        r.deiconify()
        r.after(300, poll)
        r.mainloop()
        return self.result or "quit"

    def quit(self, jobs: Callable[[], int]) -> None:
        n = jobs()
        text = "프로그램을 종료할까요? 종료하면 브라우저 화면도 더 이상 동작하지 않습니다. 저장한 내용은 그대로 남습니다."
        if n:
            text += f"\n\n진행 중인 AI·분석 작업 {n}개가 중단됩니다. 다음 실행 때 '중단됨'으로 보이며 다시 시도할 수 있습니다."
        if messagebox.askyesno(TITLE, text, parent=self.root):
            self.result = "quit"
            self.root.quit()

    def _restart_prompt(self, parent, jobs: Callable[[], int]) -> None:
        n = jobs()
        text = "바꾼 설정은 프로그램을 다시 시작하면 적용됩니다. 지금 다시 시작할까요?"
        if n:
            text += f"\n\n진행 중인 AI·분석 작업 {n}개가 중단되며, 다시 시작한 뒤 재시도할 수 있습니다."
        if messagebox.askyesno(TITLE, text, parent=parent):
            self.result = "restart"
            self.root.quit()

    # ---------------------------------------------------------------- 설정
    def settings(self, lay: Layout, cfg: lc.LocalConfig, jobs: Callable[[], int]) -> None:
        w = tk.Toplevel(self.root)
        w.title(TITLE + " — 설정")
        w.resizable(False, False)
        frm = ttk.Frame(w, padding=20)
        frm.pack(fill="both")

        ttk.Label(frm, text="로그인 비밀번호 바꾸기", font=("Malgun Gothic", 10, "bold") if os.name == "nt" else None).pack(anchor="w")
        p1, p2 = tk.StringVar(), tk.StringVar()
        prow = ttk.Frame(frm)
        prow.pack(anchor="w", pady=(4, 0))
        ttk.Entry(prow, textvariable=p1, show="•", width=22).pack(side="left")
        ttk.Entry(prow, textvariable=p2, show="•", width=22).pack(side="left", padx=6)

        def change_pw():
            try:
                lc.check_password(p1.get(), p2.get())
                lc.set_password(lay, cfg, p1.get())
            except (lc.ConfigError, KeystoreError) as e:
                messagebox.showerror(TITLE, str(e), parent=w)
                return
            p1.set("")
            p2.set("")
            self._restart_prompt(w, jobs)

        ttk.Button(prow, text="바꾸기", command=change_pw).pack(side="left")
        ttk.Label(frm, text="새 비밀번호와 확인을 입력합니다. 바꾸면 기존 로그인은 끊깁니다.", foreground="#555").pack(anchor="w")

        ttk.Separator(frm).pack(fill="x", pady=12)
        ttk.Label(frm, text="OpenAI API 키(선택)", font=("Malgun Gothic", 10, "bold") if os.name == "nt" else None).pack(anchor="w")
        try:
            saved = lc.mask(lc.openai_key(lay))
        except KeystoreError as e:
            saved = f"읽을 수 없음({e})"
        status = ttk.Label(frm, text=f"저장된 키: {saved} · 키가 없으면 샘플 모드(규칙 기반, AI 아님)")
        status.pack(anchor="w", pady=(4, 0))
        ttk.Label(frm, text=f"모델: 기본 {cfg.openai_model}, FP 후보 {cfg.openai_model_fp_candidates} (권장 구성, docs/AI_COST.md)", foreground="#555").pack(anchor="w")
        key = tk.StringVar()
        krow = ttk.Frame(frm)
        krow.pack(anchor="w", pady=(6, 0))
        ttk.Entry(krow, textvariable=key, show="•", width=40).pack(side="left")

        def save_key():
            try:
                lc.set_openai_key(lay, key.get())
            except (lc.ConfigError, KeystoreError) as e:
                messagebox.showerror(TITLE, str(e), parent=w)
                return
            key.set("")
            status.config(text=f"저장된 키: {lc.mask(lc.openai_key(lay))} · 다시 시작하면 OpenAI 연결로 바뀝니다")
            self._restart_prompt(w, jobs)

        def clear_key():
            if not messagebox.askyesno(TITLE, "저장된 API 키를 지우고 샘플 모드로 돌아갈까요?", parent=w):
                return
            lc.clear_openai_key(lay)
            status.config(text="저장된 키: 없음 · 다시 시작하면 샘플 모드(외부 AI 전송 없음)")
            self._restart_prompt(w, jobs)

        ttk.Button(krow, text="키 저장", command=save_key).pack(side="left", padx=6)
        ttk.Button(krow, text="키 삭제", command=clear_key).pack(side="left")
        ttk.Label(frm, text=COST_NOTE, wraplength=460, foreground="#8a4b00").pack(anchor="w", pady=(8, 0))
        ttk.Label(frm, text="키를 저장해도 바로 AI를 호출하지 않습니다. 화면에서 AI 버튼을 누르고 동의할 때만 호출합니다.",
                  wraplength=460, foreground="#555").pack(anchor="w", pady=(4, 0))
        ttk.Separator(frm).pack(fill="x", pady=12)
        ttk.Label(frm, text=f"데이터 폴더: {lay.root}", wraplength=460, foreground="#555").pack(anchor="w")
        ttk.Button(frm, text="닫기", command=w.destroy).pack(anchor="e", pady=(12, 0))
        w.transient(self.root)

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def _open_folder(path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # noqa: S606 - 탐색기로 사용자 데이터 폴더 열기
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
