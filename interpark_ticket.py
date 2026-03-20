"""
자동 티켓팅 v10 - 이미지 매칭 + 팀/좌석 프리셋
────────────────────────────────
- 팀 선택 → 좌석 선택 → 연석 선택 → 시작
- 이미지 매칭으로 버튼 자동 클릭
- 좌표 캡처 불필요

설치: pip install pyautogui pillow requests
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import time
import json
import os
import hashlib
import uuid
import platform

try:
    import requests
    REQ_OK = True
except ImportError:
    REQ_OK = False

try:
    import pyautogui
    import PIL
    from PIL import ImageGrab
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0
    PG_OK = True
except ImportError:
    PG_OK = False

SERVER_URL = "http://34.22.92.18:8000"

BG     = "#0b0e14"
CARD   = "#1a1e2a"
CARD2  = "#1f2535"
ACCENT = "#00e5ff"
GREEN  = "#00e676"
RED    = "#ff4d6d"
YELLOW = "#ffab40"
PURPLE = "#b388ff"
TEXT   = "#e8eaf0"
MUTED  = "#5a6070"
BORDER = "#1e2535"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
IMG_DIR   = os.path.join(BASE_DIR, "images")
DEVICE_FILE = os.path.join(BASE_DIR, ".device_id")

# ── 팀 & 좌석 구성 ───────────────────────────────────
TEAMS = {
    "삼성 라이온즈": {
        "seats": ["1루_익사이팅석", "3루_내야지정석", "3루_익사이팅석", "블루존", "원정응원석"],
    },
    "LG 트윈스": {
        "seats": [],
    },
    "한화 이글스": {
        "seats": [],
    },
    "KT 위즈": {
        "seats": [],
    },
}


def get_device_id():
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "r") as f:
            return f.read().strip()
    mac = uuid.getnode()
    hostname = platform.node()
    dev_id = hashlib.sha256(f"{mac}-{hostname}".encode()).hexdigest()[:32]
    with open(DEVICE_FILE, "w") as f:
        f.write(dev_id)
    return dev_id


def get_server_time_offset():
    try:
        from email.utils import parsedate_to_datetime
        before = time.time()
        r = requests.head("https://www.ticketlink.co.kr", timeout=5)
        after  = time.time()
        server_time_str = r.headers.get("Date", "")
        if not server_time_str:
            return 0.0
        server_ts = parsedate_to_datetime(server_time_str).timestamp()
        latency   = (after - before) / 2
        return server_ts - (before + latency)
    except Exception:
        return 0.0


def img_path(team, seat, btn):
    """이미지 파일 경로 반환"""
    safe_team = team.replace(" ", "_")
    safe_seat = seat.replace(" ", "_")
    return os.path.join(IMG_DIR, safe_team, safe_seat, f"{btn}.png")


# ─────────────────────────────────────────────────────
#  로그인 화면
# ─────────────────────────────────────────────────────
class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("🎫 티켓팅 - 로그인")
        self.root.geometry("400x360")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.eval("tk::PlaceWindow . center")
        self.pw_var   = tk.StringVar()
        self.show_pw  = tk.BooleanVar(value=False)
        self.attempts = 0
        self._build()

    def _build(self):
        tk.Label(self.root, text="🎫", font=("Segoe UI", 44), bg=BG).pack(pady=(28, 0))
        tk.Label(self.root, text="자동 티켓팅",
                 font=("Malgun Gothic", 18, "bold"), bg=BG, fg=TEXT).pack()
        tk.Label(self.root, text="비밀번호를 입력하세요",
                 font=("Malgun Gothic", 10), bg=BG, fg=MUTED).pack(pady=(4, 20))

        pf = tk.Frame(self.root, bg=BG); pf.pack(padx=50, fill="x")
        self.pw_entry = tk.Entry(pf, textvariable=self.pw_var,
                                  show="●", font=("Consolas", 14),
                                  bg=CARD, fg=TEXT, insertbackground=ACCENT,
                                  relief="flat", highlightthickness=2,
                                  highlightcolor=ACCENT,
                                  highlightbackground=BORDER,
                                  justify="center")
        self.pw_entry.pack(fill="x", ipady=8)
        self.pw_entry.bind("<Return>", lambda e: self._login())
        self.pw_entry.focus()

        tk.Checkbutton(self.root, text="비밀번호 표시",
                       variable=self.show_pw,
                       font=("Malgun Gothic", 9), bg=BG, fg=MUTED,
                       selectcolor=BG, activebackground=BG,
                       command=self._toggle_show).pack(pady=(6, 0))

        self.err_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.err_var,
                 font=("Malgun Gothic", 9), bg=BG, fg=RED,
                 wraplength=300, justify="center").pack(pady=(4, 0))

        self.login_btn = tk.Button(self.root, text="로그인",
                  font=("Malgun Gothic", 13, "bold"),
                  bg=ACCENT, fg="#000", relief="flat",
                  padx=50, pady=10, cursor="hand2",
                  command=self._login)
        self.login_btn.pack(pady=(10, 0))

        self.server_var = tk.StringVar(value="서버 확인 중...")
        tk.Label(self.root, textvariable=self.server_var,
                 font=("Malgun Gothic", 8), bg=BG, fg=MUTED).pack(pady=(10, 0))
        threading.Thread(target=self._check_server, daemon=True).start()

    def _toggle_show(self):
        self.pw_entry.config(show="" if self.show_pw.get() else "●")

    def _check_server(self):
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=5)
            if r.status_code == 200:
                self.root.after(0, lambda: self.server_var.set("✅ 서버 연결됨"))
            else:
                self.root.after(0, lambda: self.server_var.set("⚠ 서버 응답 오류"))
        except Exception:
            self.root.after(0, lambda: self.server_var.set("❌ 서버 연결 실패"))

    def _login(self):
        if not REQ_OK:
            messagebox.showerror("오류", "pip install requests")
            return
        pw = self.pw_var.get().strip()
        if not pw:
            self.err_var.set("비밀번호를 입력하세요")
            return
        self.login_btn.config(state="disabled", text="확인 중...")
        self.err_var.set("")
        threading.Thread(target=self._do_login, args=(pw,), daemon=True).start()

    def _do_login(self, pw):
        try:
            device_id = get_device_id()
            r = requests.post(f"{SERVER_URL}/login",
                              json={"password": pw, "device_id": device_id},
                              timeout=10)
            data = r.json()
            if data.get("success"):
                self.root.after(0, self._open_main)
            else:
                self.attempts += 1
                msg = data.get("msg", "오류 발생")
                if self.attempts >= 5:
                    self.root.after(0, lambda: [
                        messagebox.showerror("접근 차단", "5회 오류\n종료합니다."),
                        self.root.quit()
                    ])
                else:
                    remaining = 5 - self.attempts
                    self.root.after(0, lambda m=msg: [
                        self.err_var.set(f"❌ {m}\n(남은 시도: {remaining}회)"),
                        self.pw_var.set(""),
                        self.login_btn.config(state="normal", text="로그인"),
                        self.pw_entry.focus()
                    ])
        except Exception as e:
            self.root.after(0, lambda: [
                self.err_var.set(f"❌ 서버 연결 실패\n인터넷을 확인하세요"),
                self.login_btn.config(state="normal", text="로그인")
            ])

    def _open_main(self):
        self.root.destroy()
        main_root = tk.Tk()
        App(main_root)
        main_root.mainloop()


# ─────────────────────────────────────────────────────
#  메인 티켓팅 화면
# ─────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("🎫 자동 티켓팅 v10")
        self.root.geometry("560x860")
        self.root.configure(bg=BG)
        self.root.resizable(False, True)

        self.t_hour = tk.StringVar(value="00")
        self.t_min  = tk.StringVar(value="00")
        self.t_sec  = tk.StringVar(value="00")
        self.t_ms   = tk.StringVar(value="000")

        # 예매 버튼 좌표 (정각 클릭용)
        self.book_x = tk.IntVar(value=0)
        self.book_y = tk.IntVar(value=0)
        # 구역 버튼 좌표
        self.zone_x = tk.IntVar(value=0)
        self.zone_y = tk.IntVar(value=0)

        self.team_var  = tk.StringVar(value=list(TEAMS.keys())[0])
        self.seat_var  = tk.StringVar(value="")
        self.count_var = tk.StringVar(value="2연석")
        self.time_offset = 0.0

        self.stop_flag = False
        self.paused    = False

        self._build()
        self._tick()
        self._update_mouse()
        self._on_team_change()

    def _build(self):
        # 스크롤 가능한 캔버스 설정
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 실제 내용이 들어갈 프레임
        self.frame = tk.Frame(canvas, bg=BG)
        frame_id = canvas.create_window((0, 0), window=self.frame, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(frame_id, width=canvas.winfo_width())
        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")

        canvas.bind("<Configure>", _on_resize)
        self.frame.bind("<Configure>", _on_frame_configure)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 이제 self.frame 에 위젯 추가
        # 헤더
        hf = tk.Frame(self.frame, bg=BG)
        hf.pack(fill="x", pady=(14, 0))
        tk.Label(hf, text="🎫", font=("Segoe UI", 26), bg=BG).pack()
        tk.Label(hf, text="자동 티켓팅 v10",
                 font=("Malgun Gothic", 15, "bold"), bg=BG, fg=TEXT).pack()
        self.clock_var = tk.StringVar()
        tk.Label(hf, textvariable=self.clock_var,
                 font=("Consolas", 20, "bold"), bg=BG, fg=ACCENT).pack(pady=(3, 0))
        self.mouse_var = tk.StringVar(value="마우스: (0, 0)")
        tk.Label(hf, textvariable=self.mouse_var,
                 font=("Consolas", 9), bg=BG, fg=MUTED).pack()

        # ── STEP 1: 팀 선택
        self._section("STEP 1  팀 선택")
        s1 = self._card()
        team_list = list(TEAMS.keys())
        tm = tk.Frame(s1, bg=CARD); tm.pack(fill="x")
        for i, team in enumerate(team_list):
            rb = tk.Radiobutton(tm, text=team, variable=self.team_var, value=team,
                           font=("Malgun Gothic", 11), bg=CARD, fg=TEXT,
                           selectcolor=BG, activebackground=CARD,
                           command=self._on_team_change)
            rb.grid(row=i//2, column=i%2, sticky="w", padx=16, pady=4)

        # ── STEP 2: 좌석 선택
        self._section("STEP 2  좌석 선택")
        s2 = self._card()
        self.seat_frame = tk.Frame(s2, bg=CARD)
        self.seat_frame.pack(fill="x")
        self.img_status_var = tk.StringVar(value="")
        self.img_status_lbl = tk.Label(s2, textvariable=self.img_status_var,
                                        font=("Malgun Gothic", 9), bg=CARD, fg=MUTED)
        self.img_status_lbl.pack(anchor="w", pady=(6, 0))

        # ── STEP 3: 연석 수
        self._section("STEP 3  연석 수")
        s3 = self._card()
        rf = tk.Frame(s3, bg=CARD); rf.pack(anchor="w")
        tk.Label(rf, text="연석:", font=("Malgun Gothic", 10),
                 bg=CARD, fg=MUTED).pack(side="left", padx=(0, 10))
        for val in ["1석", "2연석", "4연석"]:
            tk.Radiobutton(rf, text=val, variable=self.count_var, value=val,
                           font=("Malgun Gothic", 11), bg=CARD, fg=TEXT,
                           selectcolor=BG, activebackground=CARD).pack(side="left", padx=8)

        # ── STEP 4: 예매 버튼 + 구역 좌표
        self._section("STEP 4  좌표 설정 (예매버튼 + 구역)")
        s4 = self._card()
        tk.Label(s4, text="예매하기 버튼과 구역 버튼은 이미지마다 위치가 달라서 좌표로 설정",
                 font=("Malgun Gothic", 8), bg=CARD, fg=MUTED).pack(anchor="w", pady=(0,6))

        for label, vx, vy in [
            ("① 예매하기 버튼", self.book_x, self.book_y),
            ("② 구역 버튼",     self.zone_x, self.zone_y),
        ]:
            row = tk.Frame(s4, bg=CARD); row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=("Malgun Gothic", 9),
                     bg=CARD, fg=TEXT, width=14, anchor="w").pack(side="left")
            tk.Label(row, text="X", font=("Consolas", 10),
                     bg=CARD, fg=MUTED).pack(side="left")
            tk.Entry(row, textvariable=vx, width=6, font=("Consolas", 11),
                     bg="#111520", fg=TEXT, insertbackground=ACCENT, justify="center",
                     relief="flat", highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack(side="left", padx=(2,6))
            tk.Label(row, text="Y", font=("Consolas", 10),
                     bg=CARD, fg=MUTED).pack(side="left")
            tk.Entry(row, textvariable=vy, width=6, font=("Consolas", 11),
                     bg="#111520", fg=TEXT, insertbackground=ACCENT, justify="center",
                     relief="flat", highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack(side="left", padx=(2,8))
            self._sbtn(row, "📍캡처",
                       lambda x=vx, y=vy, l=label: self._capture3(x, y, l),
                       YELLOW).pack(side="left")

        # ── STEP 5: 목표 시각
        self._section("STEP 5  목표 시각")
        tf = self._card()
        for var, lbl, w in [(self.t_hour,"시",3),(self.t_min,"분",3),
                             (self.t_sec,"초",3),(self.t_ms,"ms",4)]:
            col = tk.Frame(tf, bg=CARD); col.pack(side="left", padx=4)
            tk.Label(col, text=lbl, font=("Malgun Gothic", 8),
                     bg=CARD, fg=MUTED).pack()
            tk.Entry(col, textvariable=var, width=w,
                     font=("Consolas", 15, "bold"), bg="#111520", fg=ACCENT,
                     insertbackground=ACCENT, justify="center", relief="flat",
                     highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack()
            if lbl != "ms":
                tk.Label(tf, text=":", font=("Consolas", 17, "bold"),
                         bg=CARD, fg=MUTED).pack(side="left", pady=(13, 0))
        self._sbtn(tf, "+5초", self._set_plus5, YELLOW).pack(side="right")

        # 서버 시간 동기화
        self.offset_var = tk.StringVar(value="미동기화")
        self._sbtn(tf, "🕐 서버시간 동기화", self._sync_time, ACCENT).pack(side="right", padx=(0,6))
        tk.Label(tf, textvariable=self.offset_var,
                 font=("Malgun Gothic", 8), bg=CARD, fg=MUTED).pack(side="right", padx=(0,4))

        # 로그
        self._section("📋 로그")
        self.log_box = scrolledtext.ScrolledText(
            self.frame, height=5, font=("Consolas", 9),
            bg="#0d1017", fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
            state="disabled")
        self.log_box.pack(fill="x", padx=20, pady=(0, 4))

        self.status_var = tk.StringVar(value="대기 중")
        self.status_lbl = tk.Label(self.frame, textvariable=self.status_var,
                                   font=("Malgun Gothic", 11, "bold"), bg=BG, fg=MUTED)
        self.status_lbl.pack(pady=(0, 4))

        br = tk.Frame(self.frame, bg=BG); br.pack(pady=4)
        self.start_btn = tk.Button(br, text="▶  시작",
                                   font=("Malgun Gothic", 13, "bold"),
                                   bg=ACCENT, fg="#000", relief="flat",
                                   padx=24, pady=11, cursor="hand2",
                                   command=self._start)
        self.start_btn.pack(side="left", padx=6)

        self.captcha_btn = tk.Button(br, text="✅ 캡챠 완료",
                                     font=("Malgun Gothic", 13, "bold"),
                                     bg=GREEN, fg="#000", relief="flat",
                                     padx=14, pady=11, cursor="hand2",
                                     command=self._captcha_done, state="disabled")
        self.captcha_btn.pack(side="left", padx=6)

        self.stop_btn = tk.Button(br, text="■  중단",
                                  font=("Malgun Gothic", 13, "bold"),
                                  bg=RED, fg="#fff", relief="flat",
                                  padx=14, pady=11, cursor="hand2",
                                  command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)

        tk.Label(self.frame, text="💡 마우스 왼쪽 상단 모서리 → 강제 중단",
                 font=("Malgun Gothic", 8), bg=BG, fg=MUTED).pack(pady=(2, 16))

    def _section(self, t):
        tk.Label(self.frame, text=t, font=("Malgun Gothic", 10, "bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", padx=22, pady=(10, 2))

    def _card(self):
        f = tk.Frame(self.frame, bg=CARD, padx=12, pady=10)
        f.pack(fill="x", padx=20, pady=(0, 2))
        return f

    def _sbtn(self, parent, text, cmd, color):
        fg = "#000" if color in (ACCENT, YELLOW, GREEN, PURPLE) else "#fff"
        return tk.Button(parent, text=text, font=("Malgun Gothic", 9, "bold"),
                         bg=color, fg=fg, relief="flat", padx=8, pady=3,
                         cursor="hand2", command=cmd)

    def _on_team_change(self):
        team  = self.team_var.get()
        seats = TEAMS[team]["seats"]

        for w in self.seat_frame.winfo_children():
            w.destroy()

        if seats:
            self.seat_var.set(seats[0])
            for i, seat in enumerate(seats):
                rb = tk.Radiobutton(self.seat_frame, text=seat,
                                    variable=self.seat_var, value=seat,
                                    font=("Malgun Gothic", 10), bg=CARD, fg=TEXT,
                                    selectcolor=BG, activebackground=CARD,
                                    command=self._check_images)
                rb.grid(row=i//2, column=i%2, sticky="w", padx=8, pady=2)
        else:
            self.seat_var.set("")
            tk.Label(self.seat_frame, text="⚠ 준비 중인 팀입니다",
                     font=("Malgun Gothic", 10), bg=CARD, fg=YELLOW).pack(anchor="w")

        self._check_images()

    def _check_images(self):
        """선택한 팀/좌석의 이미지 파일 존재 여부 확인"""
        team = self.team_var.get()
        seat = self.seat_var.get()
        if not seat:
            return
        missing = []
        for btn in ["zone", "auto", "plus", "next"]:
            if not os.path.exists(img_path(team, seat, btn)):
                missing.append(btn)
        if not missing:
            self.img_status_var.set("✅ 모든 이미지 준비됨 → 바로 시작 가능!")
            self.img_status_lbl.config(fg=GREEN)
        else:
            self.img_status_var.set(f"⚠ 이미지 없음: {', '.join(missing)} → 좌표로 대체됩니다")
            self.img_status_lbl.config(fg=YELLOW)

    def _tick(self):
        now = time.time(); lt = time.localtime(now); ms = int((now%1)*1000)
        self.clock_var.set(f"{lt.tm_hour:02d}:{lt.tm_min:02d}:{lt.tm_sec:02d}.{ms:03d}")
        self.root.after(10, self._tick)

    def _update_mouse(self):
        if PG_OK:
            try:
                x, y = pyautogui.position()
                self.mouse_var.set(f"마우스: ({x}, {y})")
            except Exception: pass
        self.root.after(100, self._update_mouse)

    def _set_plus5(self):
        t = time.localtime(time.time() + 5)
        self.t_hour.set(f"{t.tm_hour:02d}"); self.t_min.set(f"{t.tm_min:02d}")
        self.t_sec.set(f"{t.tm_sec:02d}");   self.t_ms.set("000")

    def _sync_time(self):
        self.offset_var.set("동기화 중...")
        def _do():
            offset = get_server_time_offset()
            self.time_offset = offset
            if abs(offset) < 0.001:
                msg = "✅ PC시간 = 서버시간"
            elif offset > 0:
                msg = f"✅ 서버 {offset*1000:.0f}ms 빠름 보정"
            else:
                msg = f"✅ 서버 {abs(offset)*1000:.0f}ms 느림 보정"
            self._log(f"🕐 동기화: {msg}")
            self.root.after(0, lambda: self.offset_var.set(msg))
        threading.Thread(target=_do, daemon=True).start()

    def _log(self, msg):
        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _do)

    def _set_status(self, msg, color=MUTED):
        self.root.after(0, lambda: (
            self.status_var.set(msg),
            self.status_lbl.config(fg=color)
        ))

    def _captcha_done(self):
        self.paused = False
        self._log("캡챠 완료 → 재개")
        self.root.after(0, lambda: self.captcha_btn.config(state="disabled"))

    def _stop(self):
        self.stop_flag = True
        self._log("⛔ 중단")
        self.root.after(0, lambda: (
            self.start_btn.config(state="normal"),
            self.stop_btn.config(state="disabled"),
            self.captcha_btn.config(state="disabled"),
        ))

    def _capture3(self, vx, vy, label):
        if not PG_OK: return
        self._log(f"3초 후 [{label}] 위에 마우스 올려두세요!")
        def _do():
            for i in range(3, 0, -1):
                self._set_status(f"📍 {i}초 후 [{label}] 캡처...", YELLOW)
                time.sleep(1)
            x, y = pyautogui.position()
            vx.set(x); vy.set(y)
            self._log(f"✅ [{label}] 좌표: ({x}, {y})")
            self._set_status(f"✅ {label} 캡처 완료", GREEN)
        threading.Thread(target=_do, daemon=True).start()

    # ── 시작 ─────────────────────────────────────────
    def _start(self):
        if not PG_OK:
            messagebox.showerror("오류", "pip install pyautogui pillow"); return
        if self.book_x.get() == 0:
            messagebox.showerror("오류", "예매하기 버튼 좌표를 설정하세요!"); return
        if not self.seat_var.get():
            messagebox.showerror("오류", "좌석을 선택하세요!"); return
        try:
            h = int(self.t_hour.get()); m = int(self.t_min.get())
            s = int(self.t_sec.get());  ms = int(self.t_ms.get())
        except ValueError:
            messagebox.showerror("오류", "시각을 올바르게 입력하세요."); return

        now = time.localtime()
        target_ts = time.mktime(time.struct_time(
            (now.tm_year, now.tm_mon, now.tm_mday, h, m, s, 0, 0, -1)
        )) + ms / 1000.0 - self.time_offset
        if target_ts <= time.time():
            target_ts += 86400

        sc = self.count_var.get()
        plus_clicks = 4 if sc == "4연석" else (2 if sc == "2연석" else 1)

        self.stop_flag = False
        self.paused    = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        cfg = {
            "target_ts"  : target_ts,
            "book"       : (self.book_x.get(), self.book_y.get()),
            "zone"       : (self.zone_x.get(), self.zone_y.get()),
            "team"       : self.team_var.get(),
            "seat"       : self.seat_var.get(),
            "plus_clicks": plus_clicks,
        }
        self._log(f"▶ {cfg['team']} | {cfg['seat']} | {sc}")
        threading.Thread(target=self._run, args=(cfg,), daemon=True).start()

    # ── 핵심 실행 ─────────────────────────────────────
    def _run(self, cfg):
        target_ts = cfg["target_ts"]
        self._log(f"⏳ 목표: {time.strftime('%H:%M:%S', time.localtime(target_ts))}"
                  f".{int((target_ts%1)*1000):03d}")

        # 워밍업
        while not self.stop_flag:
            remaining = target_ts - time.time()
            if remaining <= 0.05: break
            self._set_status(f"⏳ {remaining:.2f}초 남음", YELLOW)
            if remaining < 3:
                try: pyautogui.position()
                except: pass
            time.sleep(max(0.001, remaining * 0.4))
        while not self.stop_flag and time.time() < target_ts:
            pass
        if self.stop_flag: return

        # 예매하기 클릭 (좌표)
        diff = (time.time() - target_ts) * 1000
        self._log(f"⚡ 예매하기 클릭! 오차: {diff:+.2f}ms")
        self._set_status("⚡ 예매하기 클릭!", ACCENT)
        pyautogui.click(*cfg["book"])

        # 캡챠 대기
        self._log("캡챠 있으면 직접 풀고 [✅ 캡챠 완료] 누르세요")
        self._set_status("⚠ 캡챠 풀고 '캡챠 완료' 누르세요", YELLOW)
        self.paused = True
        self.root.after(0, lambda: self.captcha_btn.config(state="normal"))
        while self.paused and not self.stop_flag:
            time.sleep(0.1)
        if self.stop_flag: return

        team = cfg["team"]
        seat = cfg["seat"]

        # 구역 클릭 (좌표)
        time.sleep(0.5)
        if cfg["zone"][0] > 0:
            self._log("🗺 구역 클릭")
            pyautogui.click(*cfg["zone"])
            time.sleep(0.5)
        if self.stop_flag: return

        # 자동배정 클릭 (이미지 매칭)
        self._click_image(team, seat, "auto", "자동배정", timeout=5)
        time.sleep(0.3)
        if self.stop_flag: return

        # + 버튼 N번 (이미지 매칭)
        n = cfg["plus_clicks"]
        self._log(f"➕ + 버튼 {n}번 클릭")
        for i in range(n):
            if self.stop_flag: return
            self._click_image(team, seat, "plus", f"+({i+1}/{n})", timeout=3)
            time.sleep(0.15)
        if self.stop_flag: return

        # 다음단계 클릭 (이미지 매칭)
        time.sleep(0.3)
        self._click_image(team, seat, "next", "다음단계", timeout=5)

        self._log("🎉 완료! 결제 진행하세요.")
        self._set_status("🎉 완료! 결제 진행하세요", GREEN)
        self.root.after(0, lambda: (
            self.start_btn.config(state="normal"),
            self.stop_btn.config(state="disabled"),
        ))

    def _click_image(self, team, seat, btn, label, timeout=3.0):
        """이미지 매칭으로 버튼 클릭"""
        path = img_path(team, seat, btn)
        if os.path.exists(path):
            start = time.time()
            while time.time() - start < timeout:
                if self.stop_flag: return False
                try:
                    loc = pyautogui.locateOnScreen(path, confidence=0.8)
                    if loc:
                        cx, cy = pyautogui.center(loc)
                        pyautogui.click(cx, cy)
                        elapsed = (time.time() - start) * 1000
                        self._log(f"✅ [{label}] 이미지 클릭 ({elapsed:.0f}ms)")
                        return True
                except Exception:
                    pass
                time.sleep(0.05)
            self._log(f"⚠ [{label}] 이미지 못 찾음")
        else:
            self._log(f"⚠ [{label}] 이미지 파일 없음: {path}")
        return False


if __name__ == "__main__":
    os.makedirs(IMG_DIR, exist_ok=True)
    if not REQ_OK:
        print("pip install requests")
    if not PG_OK:
        print("pip install pyautogui pillow")
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()
