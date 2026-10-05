"""처음 켰을 때(또는 우클릭 "사용법 / 처음 설정") 뜨는 안내.
1) Tutorial: 닉네임, Claude 연결 확인, 개인정보 선택 (작은 창)
2) Tour: 위젯 위를 어둡게 덮고 버튼마다 동그랗게 구멍을 뚫어 설명 (몸 dangam.pyw의 Dangam 객체를 받아서 씀)"""
import shutil, subprocess, sys
import tkinter as tk
import dangam_core as core

FONT = ("맑은 고딕", 10)
TITLE = ("맑은 고딕", 13, "bold")
KEY = "#010203"          # 오버레이에서 구멍으로 뚫리는 색 (-transparentcolor)

PAGES = [
    ("처음 만나서 반가워요", "text", """바탕화면을 떠다니는 캐릭터 위젯이에요. 말을 걸면 AI가 캐릭터 말투로 대답해 주고, 파일 정리나 코딩 같은 컴퓨터 일도 시킬 수 있어요.

먼저 이름 정하기와 계정 확인을 하고, 그다음에 위젯 위에서 버튼을 하나씩 짚어 드릴게요. 언제든 '건너뛰기'로 닫을 수 있고, 나중에 캐릭터 우클릭 → '사용법 / 처음 설정'으로 다시 볼 수 있어요."""),
    ("뭐라고 불러 드릴까요?", "nick", """캐릭터가 부를 이름(닉네임)을 적어 주세요. 비워 두면 '사용자'라고 불러요.
말투 설정과 대사 안의 {닉네임} 자리에 들어가요."""),
    ("Claude 계정이 있으면 좋아요", "cli", """대답은 컴퓨터에 깔린 Claude Code(`claude` 명령)가 만들어요. 그래서 Claude 구독이나 API 계정으로 로그인돼 있어야 해요. 이 위젯의 기본 두뇌예요.

아직 없으면 https://claude.com/claude-code 에서 설치하고, 터미널에서 `claude`를 한 번 실행해 로그인해 주세요. 사용량은 본인 Claude 계정에서 나가요."""),
    ("ChatGPT 계정도 있으면 좋아요 (선택)", "codex", """ChatGPT 계정이 있으면 Codex CLI를 설치해서 GPT로도 대답시킬 수 있어요. 터미널에서 `npm install -g @openai/codex`로 설치하고 `codex`를 한 번 실행해 로그인하면 돼요.

둘 다 연결해 두면 Claude 사용량이 가득 찼을 때 GPT로 자동으로 넘어가는 '자동' 모드를 쓸 수 있어요. 하나만 있어도 괜찮아요. 캐릭터를 AI로 만들 때(+ 새 캐릭터)는 chatgpt.com 로그인이 필요해요."""),
    ("알아 둘 것 (개인정보)", "privacy", """- 일을 시킬 때는 권한 확인 없이 파일을 고치고 명령을 실행해요. 중요한 폴더는 맡기기 전에 백업해 주세요.
- 대화 내용과 보낸 파일은 사용하는 AI 서비스(Claude 등)의 서버로 가요. 기록은 이 폴더 안(history.json, archive)에 저장돼요.
- 폰 접속용 작은 서버가 이 PC에서 돌아가고, 접속하려면 비밀 토큰이 필요해요. 토큰은 state.json에 있으니 그 파일은 남에게 주지 마세요."""),
]

FACE_FLOW = ["happy", "normal", "curious", "smug", "normal", "happy", "curious", "happy"]   # 단계별 안내 캐릭터 표정

# (대상, 제목, 설명). 대상: char / bubble / entry / 버튼 태그 / None(전체)
STEPS = [
    ("char", "캐릭터", """클릭하면 말풍선이 열리고 닫혀요. 더블클릭은 쓰다듬기, 마우스로 잡아서 휙 던지기도 돼요. Ctrl+Alt+Q로 숨기고 다시 부를 수 있어요."""),
    ("char", "우클릭 메뉴", """캐릭터를 우클릭하면 메뉴가 떠요.
- 멈추기: 답 쓰는 중에 멈춰요 (Esc도 같아요)
- 대화 기록 자세히: 큰 창 열기
- 새 대화 / 지난 대화 / 이름 짓기: 대화방 관리
- 움직임: 중력(떨어지고 창 위에 앉기)과 장난 정도
- 카톡 모드: 큰 창을 메신저 느낌으로 바꾸기
- 숨기기 / 사용법 / 종료"""),
    ("bubble", "말풍선", """캐릭터의 대답이 여기 떠요. 길면 마우스 휠로 넘기고, 글을 클릭하면 한 번에 다 보여 줘요. 답하는 중에 Esc를 누르면 멈춰요."""),
    ("entry", "입력창", """여기에 쓰고 Enter로 보내요. Shift+Enter는 줄바꿈이에요.
Ctrl+V로 클립보드 사진을 붙이고, 파일은 캐릭터에게 끌어다 놓으면 첨부돼요. 첨부하면 입력창 위에 줄이 생기고 ✕로 뺄 수 있어요."""),
    ("backendbtn", "대화 엔진", """지금 어떤 AI가 대답하는지 보여 줘요. 누르면 Claude와 GPT가 바뀌어요 (GPT는 codex가 깔려 있을 때만). '자동'은 Claude 한도가 차면 GPT로 넘어가요. 세부 모델은 자세히 창 설정에서 골라요."""),
    ("histbtn", "기록", """누르면 말풍선이 지난 대화 기록으로 바뀌어요. 다시 누르면('닫기') 돌아와요."""),
    ("detailbtn", "자세히", """큰 창이 열려요. 대화 검색, 일기장, 기억 노트, 설정, 폰에서 여는 QR, 캐릭터 바꾸기와 + 새 캐릭터가 여기 있어요."""),
    ("char", "이런 일도 시킬 수 있어요", """- 질문, 글 다듬기, 코딩 도움
- 파일 읽기, 정리, 이름 바꾸기, 형식 바꾸기 (예: 폴더 안의 PPT를 PDF로)
- "말투 파일 열어 줘", "persona.md 고쳐 줘"처럼 위젯 파일도 말로 열고 고치기
- 코드를 읽고 고치고, 명령을 실행해서 오류 찾기
- 알람/타이머: "30분 뒤에 알려 줘"
- 오래 기억할 것(취향, 일정)은 기억 노트에 저장
- 하루가 끝나면 일기를 쓰고, 가끔 먼저 말도 걸어요

"끝"을 누르면 '자세히' 창도 이어서 짚어 드릴게요."""),
]


def claude_found():
    return bool(shutil.which("claude")) or core.CLAUDE != "claude"


class Tutorial:
    def __init__(self, root, brain, pal, body=None):
        self.root, self.brain, self.pal, self.body, self.i = root, brain, pal, body, 0
        self.nick = tk.StringVar(value=core.NICK if core.NICK != "사용자" else "")
        self.screen = tk.BooleanVar(value=core.TALK_SCREEN)
        self.win = w = tk.Toplevel(root)
        w.title("단감 위젯 처음 설정")
        w.attributes("-topmost", True)
        w.configure(bg=pal["fill"])
        w.geometry("460x470+%d+%d" % ((w.winfo_screenwidth() - 460) // 2, (w.winfo_screenheight() - 470) // 2))
        w.resizable(False, False)
        w.protocol("WM_DELETE_WINDOW", self.finish)
        self.title = tk.Label(w, font=TITLE, bg=pal["fill"], fg=pal["accent"], anchor="w")
        self.title.pack(fill="x", padx=22, pady=(20, 6))
        self.content = tk.Frame(w, bg=pal["fill"])
        self.content.pack(fill="both", expand=True, padx=22)
        bar = tk.Frame(w, bg=pal["fill"])
        bar.pack(fill="x", padx=22, pady=14)
        self.dots = tk.Label(bar, font=FONT, bg=pal["fill"], fg=pal["muted"])
        self.dots.pack(side="left")
        self.next_b = tk.Button(bar, font=FONT, width=12, command=self.next)
        self.next_b.pack(side="right")
        self.prev_b = tk.Button(bar, text="이전", font=FONT, width=6, command=self.prev)
        self.prev_b.pack(side="right", padx=6)
        self.skip_b = tk.Button(bar, text="건너뛰기", font=FONT, relief="flat", bg=pal["fill"], fg=pal["muted"],
                                command=self.finish)
        self.skip_b.pack(side="right", padx=6)
        self.show()

    def label(self, text):
        tk.Label(self.content, text=text, font=FONT, bg=self.pal["fill"], fg=self.pal["ink"], justify="left",
                 anchor="nw", wraplength=410).pack(fill="x", anchor="w")

    def show(self):
        for c in self.content.winfo_children():
            c.destroy()
        title, kind, text = PAGES[self.i]
        self.title.configure(text=title)
        self.label(text)
        if kind == "nick":
            e = tk.Entry(self.content, textvariable=self.nick, font=("맑은 고딕", 12), width=24)
            e.pack(anchor="w", pady=14)
            e.focus_set()
        elif kind == "cli":
            self.status = tk.Label(self.content, font=("맑은 고딕", 11, "bold"), bg=self.pal["fill"], anchor="w")
            self.status.pack(fill="x", pady=(14, 6))
            row = tk.Frame(self.content, bg=self.pal["fill"])
            row.pack(anchor="w")
            tk.Button(row, text="다시 확인", font=FONT, command=self.check_cli).pack(side="left")
            tk.Button(row, text="터미널에서 claude 열기 (로그인)", font=FONT, command=self.open_claude).pack(side="left", padx=8)
            self.check_cli()
        elif kind == "codex":
            self.cstatus = tk.Label(self.content, font=("맑은 고딕", 11, "bold"), bg=self.pal["fill"], anchor="w")
            self.cstatus.pack(fill="x", pady=(14, 6))
            ok = bool(shutil.which("codex"))
            self.cstatus.configure(text="codex 명령을 찾았어요 ✔" if ok else "codex 명령이 없어요 (없어도 괜찮아요)",
                                   fg="#2e9e5b" if ok else self.pal["muted"])
        elif kind == "privacy":
            tk.Checkbutton(self.content, variable=self.screen, font=FONT, bg=self.pal["fill"], fg=self.pal["ink"],
                           selectcolor=self.pal["entry"], activebackground=self.pal["fill"], anchor="w", justify="left",
                           wraplength=400,
                           text="캐릭터가 먼저 말 걸 때 화면(스크린샷)을 보게 하기. 켜면 화면이 AI 서비스 서버로 가요. 기본은 꺼짐"
                           ).pack(fill="x", pady=14, anchor="w")
        last = self.i == len(PAGES) - 1
        self.next_b.configure(text="위젯 둘러보기" if last and self.body else "시작하기" if last else "다음")
        self.prev_b.configure(state="disabled" if self.i == 0 else "normal")
        self.skip_b.pack_forget()
        if not last:
            self.skip_b.pack(side="right", padx=6)
        self.dots.configure(text="●" * (self.i + 1) + "○" * (len(PAGES) - self.i - 1))

    def check_cli(self):
        ok = claude_found()
        self.status.configure(text="claude 명령을 찾았어요 ✔" if ok else "claude 명령을 못 찾았어요 ✘",
                              fg="#2e9e5b" if ok else "#d6453d")

    def open_claude(self):
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", "claude"])
            else:
                subprocess.Popen(["x-terminal-emulator", "-e", "claude"])
        except OSError:
            pass

    def next(self):
        if self.i == len(PAGES) - 1:
            return self.finish(tour=True)
        self.i += 1
        self.show()

    def prev(self):
        self.i = max(0, self.i - 1)
        self.show()

    def finish(self, tour=False):
        name = self.nick.get().strip()
        core.set_nick(name)
        core.set_talk_screen(self.screen.get())
        self.brain.set_body_state(nick=name, talk_screen=bool(self.screen.get()), tutorial_done=True)
        self.win.destroy()
        if tour is True and self.body:
            self.root.after(200, lambda: Tour(self.body))


class Tour:
    """위젯 위를 반투명 검정으로 덮고, 설명하는 버튼 자리만 동그랗게 뚫어 보여 줌."""
    M = 70   # 위젯 둘레로 얼마나 더 덮을지(px)

    def __init__(self, body):
        self.b, self.i = body, 0
        self.pal = body.pal
        # 도는 동안 위젯이 움직이거나 말 걸지 않게 잠시 끔
        self.saved = (body.gravity.get(), body.play.get())
        body.gravity.set(False)
        body.play.set("off")
        body.falling = False
        body.touring = True
        self.ov = tk.Toplevel(body.root)
        self.ov.overrideredirect(True)
        self.ov.attributes("-topmost", True)
        self.ov.attributes("-alpha", 0.62)
        self.ov.attributes("-transparentcolor", KEY)
        self.ov.configure(bg="black")
        self.cv = tk.Canvas(self.ov, bg="black", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.card = tk.Toplevel(body.root)
        self.card.overrideredirect(True)
        self.card.attributes("-topmost", True)
        self.card.configure(bg=self.pal["accent"])
        inner = tk.Frame(self.card, bg=self.pal["fill"])
        inner.pack(padx=2, pady=2)
        self.t_title = tk.Label(inner, font=("맑은 고딕", 12, "bold"), bg=self.pal["fill"], fg=self.pal["accent"], anchor="w")
        self.t_title.pack(fill="x", padx=16, pady=(14, 4))
        self.t_text = tk.Label(inner, font=FONT, bg=self.pal["fill"], fg=self.pal["ink"], justify="left", anchor="nw",
                               wraplength=300)
        self.t_text.pack(fill="x", padx=16)
        bar = tk.Frame(inner, bg=self.pal["fill"])
        bar.pack(fill="x", padx=16, pady=12)
        self.count = tk.Label(bar, font=(FONT[0], 9), bg=self.pal["fill"], fg=self.pal["muted"])
        self.count.pack(side="left")
        self.next_b = tk.Button(bar, font=FONT, width=7, command=self.next)
        self.next_b.pack(side="right")
        self.prev_b = tk.Button(bar, text="이전", font=FONT, width=5, command=self.prev)
        self.prev_b.pack(side="right", padx=6)
        self.close_b = tk.Button(bar, text="그만 보기", font=FONT, relief="flat", bg=self.pal["fill"], fg=self.pal["muted"],
                                 command=self.end)
        self.close_b.pack(side="right", padx=4)
        # 설명해 주는 캐릭터 (배경이 투명한 작은 창, 표정은 단계마다 바뀜)
        self.guide = tk.Toplevel(body.root)
        self.guide.overrideredirect(True)
        self.guide.attributes("-topmost", True)
        self.guide.attributes("-transparentcolor", KEY)
        self.guide.configure(bg=KEY)
        self.gcv = tk.Canvas(self.guide, bg=KEY, highlightthickness=0, width=160, height=160)
        self.gcv.pack()
        self.gimg = self.gcv.create_image(0, 0, anchor="nw")
        self.card.bind("<Escape>", lambda e: self.end())
        self.ov.bind("<Escape>", lambda e: self.end())
        self.step()

    # 말풍선이 열려 있어야 버튼이 보임 (자동 닫힘 타이머가 닫았을 수도 있어서 매 단계 확인)
    def ensure_open(self):
        b = self.b
        if b.hist:
            b.toggle_hist()
        if not b.open:
            b.open = True
        b.show("지금은 안내 중이에요. 옆에 뜬 설명 카드를 봐 주세요!")
        b.root.update_idletasks()
        b.root.update()

    def box(self, key):
        """대상의 화면 좌표 (x1, y1, x2, y2)와 모양(oval/round)"""
        b, cv = self.b, self.b.cv
        ox, oy = b.root.winfo_rootx(), b.root.winfo_rooty()
        if key == "char":
            x1, y1, x2, y2 = cv.bbox(b.char)
            w, h = x2 - x1, y2 - y1
            x1, x2, y1, y2 = x1 + w * .12, x2 - w * .12, y1 + h * .04, y2 - h * .02
            shape = "oval"
        elif key == "bubble":
            x1, y1, x2, y2 = cv.bbox(b.twin)
            x1, y1, x2, y2, shape = x1 - 14, y1 - 28, x2 + 14, y2 + 16, "round"
        elif key == "entry":
            x1, y1, x2, y2 = cv.bbox(b.ewin)
            x1, y1, x2, y2, shape = x1 - 14, y1 - 9, x2 + 14, y2 + 9, "round"
        else:
            x1, y1, x2, y2 = cv.bbox(key)
            ry = max((y2 - y1) / 2 + 12, 16)
            rx = max((x2 - x1) / 2 + 14, ry)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            x1, y1, x2, y2, shape = cx - rx, cy - ry, cx + rx, cy + ry, "oval"
        return x1 + ox, y1 + oy, x2 + ox, y2 + oy, shape

    def step(self):
        b = self.b
        key, title, text = STEPS[self.i]
        self.ensure_open()
        r = b.root
        M = self.M
        sx, sy = r.winfo_rootx() - M, r.winfo_rooty() - M
        sw, sh = r.winfo_width() + 2 * M, r.winfo_height() + 2 * M
        self.ov.geometry(f"{sw}x{sh}+{sx}+{sy}")
        cv = self.cv
        cv.delete("all")
        cv.create_rectangle(0, 0, sw, sh, fill="black", outline="")
        x1, y1, x2, y2, shape = self.box(key)
        x1, y1, x2, y2 = x1 - sx, y1 - sy, x2 - sx, y2 - sy
        if shape == "oval":
            cv.create_oval(x1, y1, x2, y2, fill=KEY, outline="")
        else:
            rad = 18
            pts = [x1 + rad, y1, x2 - rad, y1, x2, y1, x2, y1 + rad, x2, y2 - rad, x2, y2, x2 - rad, y2, x1 + rad, y2,
                   x1, y2, x1, y2 - rad, x1, y1 + rad, x1, y1]
            cv.create_polygon(pts, smooth=True, fill=KEY, outline="")
        self.t_title.configure(text=title)
        self.t_text.configure(text=text)
        last = self.i == len(STEPS) - 1
        self.next_b.configure(text="자세히 창" if last else "다음")
        self.prev_b.configure(state="disabled" if self.i == 0 else "normal")
        self.close_b.pack_forget()
        if not last:
            self.close_b.pack(side="right", padx=4)
        self.count.configure(text=f"{self.i + 1} / {len(STEPS)}")
        # 설명 카드는 오버레이 바깥(왼쪽, 모자라면 오른쪽)에서 대상 높이에 맞춤
        self.card.update_idletasks()
        cw, ch = self.card.winfo_reqwidth(), self.card.winfo_reqheight()
        scr_w, scr_h = r.winfo_screenwidth(), r.winfo_screenheight()
        px = sx - cw - 12
        if px < 8:
            px = min(sx + sw + 12, scr_w - cw - 8)
        py = max(8, min((y1 + y2) / 2 + sy - ch / 2, scr_h - ch - 48))
        self.card.geometry(f"+{int(px)}+{int(py)}")
        self.ov.lift()
        self.card.lift()
        self.card.update_idletasks()
        self.card.geometry(f"+{int(px)}+{int(py)}")   # 처음 뜰 때 0,0으로 가는 걸 다시 눌러 줌
        # 캐릭터는 카드 바깥쪽(위젯 반대편)에 서서 말하는 것처럼 카드 아랫줄에 맞춤
        gw = 160
        gx = px - gw + 8 if px < sx else px + cw - 8
        if gx < 0 or gx + gw > scr_w:
            gx = px if px < sx else px + cw - gw
        gy = max(8, min(py + ch - gw, scr_h - gw - 48))
        face = FACE_FLOW[self.i % len(FACE_FLOW)]
        self.gcv.itemconfigure(self.gimg, image=b.imgs.get(face, b.imgs["normal"]))
        self.guide.geometry(f"{gw}x{gw}+{int(gx)}+{int(gy)}")
        self.guide.lift()
        self.card.lift()
        self.card.focus_force()

    def next(self):
        if self.i == len(STEPS) - 1:
            return self.end(detail=True)
        self.i += 1
        self.step()

    def prev(self):
        self.i = max(0, self.i - 1)
        self.step()

    def end(self, detail=False):
        b = self.b
        b.touring = False
        b.gravity.set(self.saved[0])
        b.play.set(self.saved[1])
        self.ov.destroy()
        self.guide.destroy()
        self.card.destroy()
        if detail:
            b.show("이어서 자세히 창을 보여 드릴게요!")
            b.open_detail(tour=True)
        else:
            b.show("다 보셨나요? 이제 마음껏 말 걸어 주세요!")
