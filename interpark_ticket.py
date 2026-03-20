"""
자동 티켓팅 v9 - 서버 인증 버전
────────────────────────────────
- GCP 서버에서 로그인 인증
- 1계정 1기기 제한
- 프리셋 로컬 저장

설치: pip install pyautogui requests
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
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
    pyautogui.FAILSAFE = True
    PG_OK = True
except ImportError:
    PG_OK = False

# ── 서버 주소 (GCP 배포 후 변경) ─────────────────────
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

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "presets.json")
DEVICE_FILE = os.path.join(BASE_DIR, ".device_id")


def get_device_id() -> str:
    """이 PC 고유 ID 생성 (MAC + 컴퓨터이름 기반)"""
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "r") as f:
            return f.read().strip()

    # MAC 주소 + 호스트명으로 고유 ID 생성
    mac      = uuid.getnode()
    hostname = platform.node()
    raw      = f"{mac}-{hostname}"
    dev_id   = hashlib.sha256(raw.encode()).hexdigest()[:32]

    with open(DEVICE_FILE, "w") as f:
        f.write(dev_id)
    return dev_id


def load_presets():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_presets(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────
#  로그인 화면
# ─────────────────────────────────────────────────────
class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("🎫 티켓팅 - 로그인")
        self.root.geometry("400x380")
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
                 wraplength=300, justify="center").pack(pady=(6, 0))

        self.login_btn = tk.Button(self.root, text="로그인",
                  font=("Malgun Gothic", 13, "bold"),
                  bg=ACCENT, fg="#000", relief="flat",
                  padx=50, pady=10, cursor="hand2",
                  command=self._login)
        self.login_btn.pack(pady=(12, 0))

        # 서버 연결 상태
        self.server_var = tk.StringVar(value="서버 확인 중...")
        tk.Label(self.root, textvariable=self.server_var,
                 font=("Malgun Gothic", 8), bg=BG, fg=MUTED).pack(pady=(12, 0))

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
            self.root.after(0, lambda: self.server_var.set("❌ 서버 연결 실패 - 인터넷 확인"))

    def _login(self):
        if not REQ_OK:
            messagebox.showerror("오류", "pip install requests 실행 후 재시도")
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
            r = requests.post(
                f"{SERVER_URL}/login",
                json={"password": pw, "device_id": device_id},
                timeout=10
            )
            data = r.json()

            if data.get("success"):
                self.root.after(0, self._open_main)
            else:
                self.attempts += 1
                msg = data.get("msg", "오류 발생")
                if self.attempts >= 5:
                    self.root.after(0, lambda: [
                        messagebox.showerror("접근 차단", "비밀번호 5회 오류\n프로그램을 종료합니다."),
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
        except requests.exceptions.ConnectionError:
            self.root.after(0, lambda: [
                self.err_var.set("❌ 서버에 연결할 수 없습니다\n인터넷 연결을 확인하세요"),
                self.login_btn.config(state="normal", text="로그인")
            ])
        except Exception as e:
            self.root.after(0, lambda: [
                self.err_var.set(f"❌ 오류: {str(e)}"),
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
        self.root.title("🎫 자동 티켓팅 v9")
        self.root.geometry("600x980")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.presets = load_presets()

        self.t_hour = tk.StringVar(value="00")
        self.t_min  = tk.StringVar(value="00")
        self.t_sec  = tk.StringVar(value="00")
        self.t_ms   = tk.StringVar(value="000")

        self.book_x = tk.IntVar(value=0)
        self.book_y = tk.IntVar(value=0)
        self.zone_x = tk.IntVar(value=0)
        self.zone_y = tk.IntVar(value=0)
        self.auto_x = tk.IntVar(value=0)
        self.auto_y = tk.IntVar(value=0)
        self.plus_x = tk.IntVar(value=0)
        self.plus_y = tk.IntVar(value=0)
        self.next_x = tk.IntVar(value=0)
        self.next_y = tk.IntVar(value=0)

        self.seat_count      = tk.StringVar(value="2연석")
        self.selected_preset = tk.StringVar(value="")

        self.stop_flag = False
        self.paused    = False

        self._build()
        self._tick()
        self._update_mouse()

    def _build(self):
        hf = tk.Frame(self.root, bg=BG)
        hf.pack(fill="x", pady=(14, 0))
        tk.Label(hf, text="🎫", font=("Segoe UI", 26), bg=BG).pack()
        tk.Label(hf, text="자동 티켓팅 v9",
                 font=("Malgun Gothic", 15, "bold"), bg=BG, fg=TEXT).pack()
        self.clock_var = tk.StringVar()
        tk.Label(hf, textvariable=self.clock_var,
                 font=("Consolas", 20, "bold"), bg=BG, fg=ACCENT).pack(pady=(3, 0))
        self.mouse_var = tk.StringVar(value="마우스: (0, 0)")
        tk.Label(hf, textvariable=self.mouse_var,
                 font=("Consolas", 9), bg=BG, fg=MUTED).pack()

        # 프리셋
        self._section("⭐ 저장된 좌석 프리셋")
        pf = self._card()
        pl = tk.Frame(pf, bg=CARD); pl.pack(fill="x")
        tk.Label(pl, text="프리셋:", font=("Malgun Gothic", 10),
                 bg=CARD, fg=MUTED).pack(side="left")
        self.preset_menu = tk.OptionMenu(pl, self.selected_preset, "")
        self.preset_menu.config(font=("Malgun Gothic", 10), bg=CARD2, fg=TEXT,
                                activebackground=ACCENT, activeforeground="#000",
                                relief="flat", highlightthickness=0, width=18)
        self.preset_menu["menu"].config(bg=CARD2, fg=TEXT, font=("Malgun Gothic", 10))
        self.preset_menu.pack(side="left", padx=(6, 0))
        self._sbtn(pl, "✅ 불러오기", self._load_preset, GREEN).pack(side="left", padx=(8, 0))
        self._sbtn(pl, "🗑 삭제", self._delete_preset, RED).pack(side="left", padx=(4, 0))
        tk.Label(pf, text="※ 프리셋 선택 후 [불러오기] → 바로 시작 가능",
                 font=("Malgun Gothic", 8), bg=CARD, fg=MUTED).pack(anchor="w", pady=(6, 0))
        self._update_preset_menu()

        # 목표 시각
        self._section("STEP 1  목표 시각")
        tf = self._card()
        for var, lbl, w in [(self.t_hour,"시",3),(self.t_min,"분",3),
                             (self.t_sec,"초",3),(self.t_ms,"ms",4)]:
            col = tk.Frame(tf, bg=CARD); col.pack(side="left", padx=4)
            tk.Label(col, text=lbl, font=("Malgun Gothic", 8), bg=CARD, fg=MUTED).pack()
            tk.Entry(col, textvariable=var, width=w,
                     font=("Consolas", 15, "bold"), bg="#111520", fg=ACCENT,
                     insertbackground=ACCENT, justify="center", relief="flat",
                     highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack()
            if lbl != "ms":
                tk.Label(tf, text=":", font=("Consolas", 17, "bold"),
                         bg=CARD, fg=MUTED).pack(side="left", pady=(13, 0))
        self._sbtn(tf, "+5초", self._set_plus5, YELLOW).pack(side="right")

        # 연석
        self._section("STEP 2  연석 수")
        s2 = self._card()
        rf = tk.Frame(s2, bg=CARD); rf.pack(anchor="w")
        tk.Label(rf, text="연석:", font=("Malgun Gothic", 10),
                 bg=CARD, fg=MUTED).pack(side="left", padx=(0, 10))
        for val in ["1석", "2연석", "4연석"]:
            tk.Radiobutton(rf, text=val, variable=self.seat_count, value=val,
                           font=("Malgun Gothic", 11), bg=CARD, fg=TEXT,
                           selectcolor=BG, activebackground=CARD).pack(side="left", padx=8)

        # 좌표 설정
        self._section("STEP 3  버튼 좌표 설정")
        c3 = self._card()
        tk.Label(c3, text="Ctrl+0 줌100% + 브라우저 최대화 상태에서 캡처!",
                 font=("Malgun Gothic", 9), bg=CARD, fg=YELLOW).pack(anchor="w", pady=(0, 6))

        self._coord_entries = {}
        rows = [
            ("① 예매하기 버튼",    self.book_x, self.book_y, "book"),
            ("② 구역 (블루존 등)", self.zone_x, self.zone_y, "zone"),
            ("③ 자동배정 버튼",    self.auto_x, self.auto_y, "auto"),
            ("④ + 수량버튼",       self.plus_x, self.plus_y, "plus"),
            ("⑤ 다음단계 버튼",    self.next_x, self.next_y, "next"),
        ]
        for label, vx, vy, key in rows:
            row = tk.Frame(c3, bg=CARD); row.pack(fill="x", pady=2)
            sv = tk.StringVar(value="○")
            sl = tk.Label(row, textvariable=sv, font=("Consolas", 12), bg=CARD, fg=MUTED)
            sl.pack(side="left", padx=(0, 4))
            self._coord_entries[key] = (sv, sl, vx, vy)
            tk.Label(row, text=label, font=("Malgun Gothic", 9),
                     bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
            tk.Label(row, text="X", font=("Consolas", 10), bg=CARD, fg=MUTED).pack(side="left")
            tk.Entry(row, textvariable=vx, width=6, font=("Consolas", 11),
                     bg="#111520", fg=TEXT, insertbackground=ACCENT, justify="center",
                     relief="flat", highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack(side="left", padx=(2, 6))
            tk.Label(row, text="Y", font=("Consolas", 10), bg=CARD, fg=MUTED).pack(side="left")
            tk.Entry(row, textvariable=vy, width=6, font=("Consolas", 11),
                     bg="#111520", fg=TEXT, insertbackground=ACCENT, justify="center",
                     relief="flat", highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER).pack(side="left", padx=(2, 8))
            self._sbtn(row, "📍캡처",
                       lambda lbl=label, x=vx, y=vy, k=key: self._capture3(x, y, lbl, k),
                       YELLOW).pack(side="left")

        prow = tk.Frame(c3, bg=CARD); prow.pack(fill="x", pady=(8, 0))
        self._sbtn(prow, "💾 프리셋으로 저장", self._save_preset, PURPLE).pack(side="left")
        tk.Label(prow, text="← 이름 붙여서 저장 (예: 블루존2연석)",
                 font=("Malgun Gothic", 8), bg=CARD, fg=MUTED).pack(side="left", padx=(8, 0))

        # 로그
        self._section("📋 로그")
        self.log_box = scrolledtext.ScrolledText(
            self.root, height=5, font=("Consolas", 9),
            bg="#0d1017", fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
            state="disabled")
        self.log_box.pack(fill="x", padx=20, pady=(0, 4))

        self.status_var = tk.StringVar(value="대기 중")
        self.status_lbl = tk.Label(self.root, textvariable=self.status_var,
                                   font=("Malgun Gothic", 11, "bold"), bg=BG, fg=MUTED)
        self.status_lbl.pack(pady=(0, 4))

        br = tk.Frame(self.root, bg=BG); br.pack(pady=4)
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

        tk.Label(self.root, text="💡 마우스 왼쪽 상단 모서리 → 강제 중단",
                 font=("Malgun Gothic", 8), bg=BG, fg=MUTED).pack(pady=(2, 8))

    def _section(self, t):
        tk.Label(self.root, text=t, font=("Malgun Gothic", 10, "bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", padx=22, pady=(10, 2))

    def _card(self):
        f = tk.Frame(self.root, bg=CARD, padx=12, pady=10)
        f.pack(fill="x", padx=20, pady=(0, 2))
        return f

    def _sbtn(self, parent, text, cmd, color):
        fg = "#000" if color in (ACCENT, YELLOW, GREEN, PURPLE) else "#fff"
        return tk.Button(parent, text=text, font=("Malgun Gothic", 9, "bold"),
                         bg=color, fg=fg, relief="flat", padx=8, pady=3,
                         cursor="hand2", command=cmd)

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

    def _log(self, msg):
        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _do)

    def _set_status(self, msg, color=MUTED):
        self.root.after(0, lambda: (self.status_var.set(msg), self.status_lbl.config(fg=color)))

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

    def _update_coord_states(self):
        for key, (sv, sl, vx, vy) in self._coord_entries.items():
            if vx.get() > 0 or vy.get() > 0:
                sv.set("✅"); sl.config(fg=GREEN)
            else:
                sv.set("○"); sl.config(fg=MUTED)

    def _capture3(self, vx, vy, label, key):
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
            self.root.after(0, self._update_coord_states)
        threading.Thread(target=_do, daemon=True).start()

    def _save_preset(self):
        name = simpledialog.askstring("프리셋 저장", "이름 입력 (예: 블루존2연석)", parent=self.root)
        if not name or not name.strip(): return
        name = name.strip()
        self.presets[name] = {
            "book": [self.book_x.get(), self.book_y.get()],
            "zone": [self.zone_x.get(), self.zone_y.get()],
            "auto": [self.auto_x.get(), self.auto_y.get()],
            "plus": [self.plus_x.get(), self.plus_y.get()],
            "next": [self.next_x.get(), self.next_y.get()],
            "seat_count": self.seat_count.get(),
        }
        save_presets(self.presets)
        self._update_preset_menu()
        self.selected_preset.set(name)
        self._log(f"💾 저장: [{name}]")
        messagebox.showinfo("저장 완료", f"[{name}] 저장 완료!")

    def _load_preset(self):
        name = self.selected_preset.get()
        if not name or name not in self.presets:
            messagebox.showerror("오류", "프리셋을 선택하세요!"); return
        p = self.presets[name]
        self.book_x.set(p["book"][0]); self.book_y.set(p["book"][1])
        self.zone_x.set(p["zone"][0]); self.zone_y.set(p["zone"][1])
        self.auto_x.set(p["auto"][0]); self.auto_y.set(p["auto"][1])
        self.plus_x.set(p["plus"][0]); self.plus_y.set(p["plus"][1])
        self.next_x.set(p["next"][0]); self.next_y.set(p["next"][1])
        self.seat_count.set(p.get("seat_count", "2연석"))
        self._update_coord_states()
        self._log(f"📂 불러옴: [{name}]")
        self._set_status(f"✅ [{name}] 로드 완료", GREEN)

    def _delete_preset(self):
        name = self.selected_preset.get()
        if not name or name not in self.presets:
            messagebox.showerror("오류", "삭제할 프리셋을 선택하세요!"); return
        if messagebox.askyesno("삭제 확인", f"[{name}] 삭제할까요?"):
            del self.presets[name]
            save_presets(self.presets)
            self._update_preset_menu()

    def _update_preset_menu(self):
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        if self.presets:
            for name in self.presets:
                menu.add_command(label=name, command=lambda n=name: self.selected_preset.set(n))
            if self.selected_preset.get() not in self.presets:
                self.selected_preset.set(list(self.presets.keys())[0])
        else:
            menu.add_command(label="(저장된 프리셋 없음)", command=lambda: None)
            self.selected_preset.set("")

    def _start(self):
        if not PG_OK:
            messagebox.showerror("오류", "pip install pyautogui"); return
        if self.book_x.get() == 0:
            messagebox.showerror("오류", "예매하기 버튼 좌표를 설정하세요!"); return
        try:
            h = int(self.t_hour.get()); m = int(self.t_min.get())
            s = int(self.t_sec.get());  ms = int(self.t_ms.get())
        except ValueError:
            messagebox.showerror("오류", "시각을 올바르게 입력하세요."); return

        now = time.localtime()
        target_ts = time.mktime(time.struct_time(
            (now.tm_year, now.tm_mon, now.tm_mday, h, m, s, 0, 0, -1)
        )) + ms / 1000.0
        if target_ts <= time.time():
            target_ts += 86400

        sc = self.seat_count.get()
        plus_clicks = 4 if sc == "4연석" else (2 if sc == "2연석" else 1)

        self.stop_flag = False
        self.paused    = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        cfg = {
            "target_ts"  : target_ts,
            "book"       : (self.book_x.get(), self.book_y.get()),
            "zone"       : (self.zone_x.get(), self.zone_y.get()),
            "auto"       : (self.auto_x.get(), self.auto_y.get()),
            "plus"       : (self.plus_x.get(), self.plus_y.get()),
            "next"       : (self.next_x.get(), self.next_y.get()),
            "plus_clicks": plus_clicks,
        }
        threading.Thread(target=self._run, args=(cfg,), daemon=True).start()

    def _run(self, cfg):
        target_ts = cfg["target_ts"]
        self._log(f"⏳ 목표: {time.strftime('%H:%M:%S', time.localtime(target_ts))}"
                  f".{int((target_ts%1)*1000):03d}")

        while not self.stop_flag:
            remaining = target_ts - time.time()
            if remaining <= 0.05: break
            self._set_status(f"⏳ {remaining:.2f}초 남음", YELLOW)
            time.sleep(max(0.001, remaining * 0.4))
        while not self.stop_flag and time.time() < target_ts:
            pass
        if self.stop_flag: return

        diff = (time.time() - target_ts) * 1000
        self._log(f"⚡ 예매하기 클릭! 오차: {diff:+.2f}ms")
        self._set_status("⚡ 예매하기 클릭!", ACCENT)
        pyautogui.click(*cfg["book"])

        self._log("캡챠 있으면 직접 풀고 [✅ 캡챠 완료] 누르세요")
        self._set_status("⚠ 캡챠 있으면 풀고 '캡챠 완료' 누르세요", YELLOW)
        self.paused = True
        self.root.after(0, lambda: self.captcha_btn.config(state="normal"))
        while self.paused and not self.stop_flag:
            time.sleep(0.1)
        if self.stop_flag: return

        time.sleep(0.8)
        if cfg["zone"][0] > 0:
            self._log("🗺 구역 클릭")
            pyautogui.click(*cfg["zone"])
            time.sleep(0.8)
        if self.stop_flag: return

        if cfg["auto"][0] > 0:
            self._log("🎯 자동배정 클릭")
            pyautogui.click(*cfg["auto"])
            time.sleep(0.8)
        if self.stop_flag: return

        if cfg["plus"][0] > 0:
            n = cfg["plus_clicks"]
            self._log(f"➕ + 버튼 {n}번")
            for i in range(n):
                if self.stop_flag: return
                pyautogui.click(*cfg["plus"])
                time.sleep(0.3)
        if self.stop_flag: return

        time.sleep(0.5)
        if cfg["next"][0] > 0:
            self._log("➡ 다음단계 클릭")
            pyautogui.click(*cfg["next"])
            self._log("🎉 완료! 결제 진행하세요.")
            self._set_status("🎉 완료! 결제 진행하세요", GREEN)

        self.root.after(0, lambda: (
            self.start_btn.config(state="normal"),
            self.stop_btn.config(state="disabled"),
        ))


if __name__ == "__main__":
    if not REQ_OK:
        print("pip install requests")
    if not PG_OK:
        print("pip install pyautogui")
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()
