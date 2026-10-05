"""단감 윈도우 위젯 (몸). 생각하는 건 전부 dangam_core.Brain이 하고, 여기는 화면/마우스/윈도우 기능만."""
import ctypes, itertools, json, math, os, random, re, subprocess, sys, time, traceback, webbrowser
import tkinter as tk
import tkinter.font as tkfont
import tkinter.simpledialog as simpledialog
import winsys
import voice
import dangam_core as core
import dangam_tutorial
from dangam_core import FACES, FACE_DIR, ATTACH_DIR, HERE

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"  # 자세히 창을 앱 모드 창으로 띄움

BG = "#ff00ff"      # 이 색은 투명하게 뚫림
BW = 250            # 말풍선 너비
MAXH = 260          # 말풍선 글자 영역 최대 높이 (넘치면 휠로 스크롤)
FACE_Y = 65         # 그림 위쪽에서 얼굴까지 거리, 말풍선 꼬리가 여기를 가리킴
# 3D 아바타(avatar3d/, Electron): 캐릭터 자리에 3D 창을 겹쳐 띄우고, 위젯은 모델 모양 그림(마스크)으로 클릭을 받음
AV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatar3d")
AV_EXE = os.path.join(AV_DIR, "node_modules", "electron", "dist", "electron.exe")
AV_SIZE, AV_FACE_Y = (160, 280), 30
AV_SIZE_VT, AV_FACE_Y_VT = (210, 210), 55   # 버튜버(상반신) 모드: 정사각형 창, 머리가 위쪽
AV_PORT, AV_MY_PORT = 47891, 47892
PALETTES = {  # 말풍선 색. 테마는 자동(윈도우 설정 따라감)/라이트/다크
    "light": {"fill": "#fffafd", "line": "#f0a6ca", "ink": "#4a3b52", "accent": "#e27bb0", "muted": "#b08aa0",
              "entry": "#ffffff", "me": "#4a5a99", "me_who": "#7a8cc9", "sys": "#aaa0b0"},
    "dark": {"fill": "#2a2632", "line": "#c9789f", "ink": "#ece6f2", "accent": "#f5a3c7", "muted": "#9a8fa5",
             "entry": "#211e28", "me": "#a9b8f0", "me_who": "#8d9be0", "sys": "#7d7388"},
}
FONT = ("맑은 고딕", 10)

# 말풍선 마크다운: 글자는 기호를 뺀 plain으로, 모양은 (시작, 끝, 태그) 목록으로 따로 돌려줌 (한 글자씩 나오는 효과가 plain 길이 기준이라)
_MD_INLINE = re.compile(r"`([^`\n]+)`|\*\*(?!\s)(.+?)(?<!\s)\*\*(?!\*)|\*(?!\s)(.+?)(?<!\s)\*|~~(.+?)~~|\[([^\]\n]+)\]\(https?://[^\s)]+\)")


def _md_inline(s, flags, base):
    out, spans, pos = "", [], 0
    for m in _MD_INLINE.finditer(s):
        out += s[pos:m.start()]
        pos = m.end()
        if m.group(1) is not None:
            inner, f = m.group(1), "c"
        elif m.group(2) is not None:
            inner, f = m.group(2), "b"
        elif m.group(3) is not None:
            inner, f = m.group(3), "i"
        elif m.group(4) is not None:
            inner, f = m.group(4), "s"
        else:
            inner, f = m.group(5), ""
        nf = flags | set(f)
        if "c" in nf:
            txt, sub = inner, []
        else:
            txt, sub = _md_inline(inner, nf, base + len(out))
        start = base + len(out)
        out += txt
        if nf:
            spans.append((start, base + len(out), "m_" + "".join(sorted(nf))))
        spans.extend(sub)
    return out + s[pos:], spans


def md_parse(text):
    """-> (plain, spans). spans = [(시작, 끝, 태그이름)] (plain 글자 위치 기준)."""
    plain, spans = "", []
    for line in text.replace("\r", "").split("\n"):
        if line.strip().startswith("```"):
            continue
        tag, flags = None, set()
        m = re.match(r"\s*(-{3,}|\*{3,}|_{3,})\s*$", line)
        if m:
            line, tag = "─" * 14, "m_hr"
        elif re.match(r"\s*#{1,4}\s+", line):
            line, flags = re.sub(r"^\s*#{1,4}\s+", "", line), {"h"}
        elif re.match(r"\s*>\s?", line):
            line, tag = re.sub(r"^\s*>\s?", "", line), "m_q"
        elif re.match(r"\s*(?:[-+]|\*(?=\s))\s+", line):
            line, tag = "• " + re.sub(r"^\s*(?:[-+]|\*)\s+", "", line), "m_li"
        elif re.match(r"\s*\d+[.)]\s+", line):
            line, tag = re.sub(r"^\s*", "", line), "m_li"
        text_line, sub = _md_inline(line, flags, len(plain))
        if "h" in flags:
            sub.append((len(plain), len(plain) + len(text_line), "m_h"))
        if tag:
            sub.append((len(plain), len(plain) + len(text_line), tag))
        spans.extend(sub)
        plain += text_line + "\n"
    return plain.rstrip("\n"), spans


IN_MAX = 4          # 입력창 최대 줄 수
BOB = 4             # 둥실거리는 높이(px)
BOB_SEC = 2.6       # 한 번 둥실하는 데 걸리는 시간(초)
TYPE_MS = 28        # 글자 하나 나오는 간격(ms)
HOTKEY = (0x0001 | 0x0002, ord("Q"))   # Ctrl+Alt+Q: 숨기기/부르기 (MOD_ALT | MOD_CONTROL). Ctrl+Alt+R은 다른 프로그램이 이미 씀
JUMP = 10           # 폴짝 뛰는 높이(px)
JUMP_SEC = 0.35     # 폴짝 뛰는 시간(초)

# 던지기/중력
GRAVITY = 2400      # 떨어지는 가속도 (px/s²)
BOUNCE = 0.35       # 바닥에 부딪히면 튀어 오르는 비율
SINK = 6            # 창 모서리/작업표시줄에 앉을 때 살짝 파묻히는 정도(px)

# 게임 서버 감시 (꺼지면 알려 줌)
WATCH = []   # ("이름", r"실행 파일 경로") 를 넣으면 꺼졌을 때 알려 줌
WATCH_SEC = 15
# 장난치기 (혼자 돌아다니기, 커서 밀기, 앉은 창 흔들기)
PLAY_SEC = {"calm": (40, 120), "wild": (5, 15)}   # 장난 간격(초): 얌전히 / 난리 모드
WALK = 110             # 걷는 속도(px/s), 난리 모드는 3배
PLAY_LINES = {
    "nudge": [
    ("curious", "잠깐 비켜 주실래요?"),
    ("normal", "살짝 밀어 볼게요."),
],
    "shake": [
    ("happy", "흔들흔들~"),
    ("curious", "창이 흔들리죠?"),
],
    "jump": [
    ("happy", "폴짝!"),
    ("happy", "영차."),
],
    "grab": [
    ("smug", "마우스 잠깐 빌릴게요."),
    ("curious", "이쪽으로 가져가 볼까요."),
],
    "climb": [
    ("happy", "이 창 위에 올라가 볼게요."),
    ("normal", "여기가 좋겠어요."),
],
    "hide": [
    ("smug", "숨바꼭질이에요. 찾아보세요."),
    ("curious", "저 어디 있게요?"),
],
    "found": [
    ("happy", "들켰네요."),
    ("surprised", "벌써 찾으셨어요?"),
],
    "pinball": [
    ("surprised", "으앗, 멈춰 주세요!"),
    ("surprised", "어지러워요!"),
],
}


def protocol_registered():
    """dotcompanion:// 주소로 위젯을 켤 수 있게 등록돼 있는지 (자세히 창의 "위젯 켜기" 버튼용)."""
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\dotcompanion\shell\open\command").Close()
        return True
    except OSError:
        return False


def register_protocol():
    """dotcompanion:// 를 이 위젯 실행으로 등록 (HKCU라 관리자 권한 필요 없음, 키 하나 지우면 원래대로)."""
    import winreg
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\dotcompanion") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "URL:DotCompanion")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\dotcompanion\shell\open\command") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, f'"{exe}" "{os.path.join(HERE, "dangam.pyw")}"')


def windows_theme():
    try:   # 윈도우 설정 > 개인 설정 > 색 > 앱 모드
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
    except OSError:
        return "light"


class LOGFONTW(ctypes.Structure):
    _fields_ = [(n, ctypes.c_long) for n in ("lfHeight", "lfWidth", "lfEscapement", "lfOrientation", "lfWeight")] + \
               [(n, ctypes.c_byte) for n in ("lfItalic", "lfUnderline", "lfStrikeOut", "lfCharSet",
                                             "lfOutPrecision", "lfClipPrecision", "lfQuality", "lfPitchAndFamily")] + \
               [("lfFaceName", ctypes.c_wchar * 32)]


def ime_font(widget):
    """한글 조합 중인 글자는 입력기가 따로 그림. 입력기 글꼴을 위젯 글꼴과 맞춤."""
    try:
        imm = ctypes.windll.imm32
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = [ctypes.c_void_p]
        imm.ImmSetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        imm.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        hwnd = widget.winfo_id()
        himc = imm.ImmGetContext(hwnd)
        if not himc:
            return False
        lf = LOGFONTW(lfHeight=-round(FONT[1] * widget.winfo_fpixels("1i") / 72), lfWeight=400,
                      lfCharSet=-127, lfFaceName=FONT[0])  # -127 == 129 (HANGUL_CHARSET)
        ok = imm.ImmSetCompositionFontW(himc, ctypes.byref(lf))
        imm.ImmReleaseContext(hwnd, himc)
        return bool(ok)
    except Exception:
        return False


def kakao_app_id():
    """자세히 창 "앱으로 설치"로 만든 카톡 모드 앱의 Edge app-id (시작 메뉴 바로가기에서 읽음). 없으면 None."""
    import glob
    found = glob.glob(os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\**\카톡 모드*.lnk"), recursive=True)         + glob.glob(os.path.join(os.path.expanduser("~"), "Desktop", "카톡 모드*.lnk"))   # Edge가 바탕화면에만 만들기도 함
    try:
        raw = open(found[0], "rb").read()
    except (IndexError, OSError):
        return None
    for text in (raw.decode("utf-16-le", "ignore"), raw[1:].decode("utf-16-le", "ignore"), raw.decode("latin-1")):
        m = re.search(r"--app-id=([a-p]{32})", text)
        if m:
            return m.group(1)
    return None


def rounded(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class Dangam:
    def __init__(self, port=core.DETAIL_PORT):
        fresh = not os.path.exists(core.STATE_FILE)   # 처음 켠 것 (state.json이 아직 없음)
        self.brain = core.Brain({"context": winsys.active_window, "screenshot": core.screenshot,
                                 "system_theme": windows_theme, "protocol": protocol_registered,
                                 "voice_test": lambda: self.root.after(0, self.test_voice)}, port=port)
        state = self.brain.state
        self.open = False
        self.hidden = False          # 단축키로 숨긴 상태
        self.touring = False         # 사용법 안내(어두운 오버레이) 중
        self.message = "불렀어? 여기다 쓰면 돼. 사진은 Ctrl+V, 파일은 나한테 끌어다 놔. 우클릭은 메뉴."
        self.spans = []                  # 마크다운 모양 목록 (md_parse)
        self.shown = len(self.message)   # 한 글자씩 보여 줄 때 지금까지 보인 글자 수
        self.attach = []             # 다음에 보낼 첨부 파일 경로들
        self.servers = None          # 게임 서버 켜짐 여부 {이름: bool}

        self.root = root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.wm_attributes("-transparentcolor", BG)
        self.gravity = tk.BooleanVar(value=state.get("gravity", True))
        play = state.get("play", "calm")
        self.play = tk.StringVar(value={True: "calm", False: "off"}.get(play, play))   # off / calm / wild (예전엔 True/False)
        self.walk_cmd_until = 0      # AI가 시킨 걷기는 이 시각까지 말풍선이 열려 있어도 계속
        self.walk_sign = self.av_walk = 0   # 걷는 방향(-1/0/1), 3D 창에 마지막으로 알린 방향
        self.walk = None             # 걷는 중이면 (목표 x 또는 "cursor", 끝낼 시각)
        self.theme_var = tk.StringVar(value=self.brain.theme)

        self.av3d = tk.BooleanVar(value=state.get("av3d", False) and os.path.isfile(AV_EXE))
        self.vt = tk.BooleanVar(value=state.get("vt", False))   # 3D 상반신(버튜버) 모드: 걷지 않고 앉아서 움직임
        self.av_scale = min(2.0, max(0.75, float(state.get("av_scale", 1.0))))   # 3D 몸 크기 배율
        self.av_bust = tk.DoubleVar(value=min(8.0, max(0.5, float(state.get("av_bust", 1.0)))))   # 3D 아바타 크기 조절
        self.av_proc = self.av_sock = None
        self.av_img = None
        self.av_moving = None
        self.face_y = self.av_face_y()
        self.load_faces()
        self.cw, self.ch = self.imgs["normal"].width(), self.imgs["normal"].height()
        self.cv = cv = tk.Canvas(root, bg=BG, highlightthickness=0)
        cv.pack()
        self.char = cv.create_image(0, 0, image=self.imgs["normal"], anchor="nw")
        self.jump_at = 0             # 마지막으로 폴짝 뛴 시각
        self.click_job = None
        self.dbl = False
        self.hist = False            # 말풍선이 대화 기록 보기 상태인지

        # 던지기/중력 상태
        self.falling, self.dragging = True, False    # 켜지면 일단 바닥(또는 창 위)까지 떨어짐
        self.vx = self.vy = 0.0
        self.perch, self.perch_rect = None, None     # 앉아 있는 창 (작업표시줄이면 "floor")
        self.samples = []                            # 드래그 속도 계산용 (시각, x, y)
        self.last_frame = time.time()

        self.text = tk.Text(cv, wrap="word", font=FONT, relief="flat", bd=0,
                            highlightthickness=0, cursor="arrow", state="disabled")
        self.entry = tk.Text(cv, height=1, wrap="word", font=FONT,
                             relief="flat", bd=0, highlightthickness=0, undo=True)
        small = (FONT[0], 8, "bold")
        self.text.tag_config("who_me", font=small, justify="right")
        self.text.tag_config("me", justify="right", lmargin1=30, lmargin2=30)
        self.text.tag_config("who_dangam", font=small)
        self.text.tag_config("dangam", rmargin=20)
        self.text.tag_config("sys", font=small, justify="center")
        self.text.tag_config("m_q", lmargin1=12, lmargin2=12)
        self.text.tag_config("m_li", lmargin1=2, lmargin2=14)
        self.mdfonts, self.mdtags = [], []
        for n in range(1, 6):
            for combo in itertools.combinations("bchis", n):   # b굵게 c코드 h제목 i기울임 s취소선
                f = tkfont.Font(family="Consolas" if "c" in combo else FONT[0], size=11 if "h" in combo else 10,
                                weight="bold" if ("b" in combo or "h" in combo) else "normal",
                                slant="italic" if "i" in combo else "roman", overstrike="s" in combo)
                self.mdfonts.append(f)
                name = "m_" + "".join(combo)
                self.mdtags.append(name)
                self.text.tag_config(name, font=f)
        self.apply_theme()
        self.line_h = tkfont.Font(font=FONT).metrics("linespace")
        self.in_lines = 1
        self.twin = cv.create_window(0, 0, window=self.text, anchor="nw", state="hidden")
        self.ewin = cv.create_window(0, 0, window=self.entry, anchor="nw", state="hidden")
        self.entry.bind("<Return>", self.send)
        self.entry.bind("<Shift-Return>", lambda e: None)   # Shift+Enter는 줄바꿈 (기본 동작)
        self.entry.bind("<KeyRelease>", lambda e: self.root.after_idle(self.fit_input))
        self.entry.bind("<FocusIn>", lambda e: ime_font(self.entry))
        self.entry.bind("<<Paste>>", self.paste)
        root.bind("<Escape>", lambda e: self.brain.stop() if self.busy else self.toggle(False))   # 답 쓰는 중이면 멈추기

        cv.tag_bind(self.char, "<ButtonPress-1>", self.press)
        cv.tag_bind(self.char, "<B1-Motion>", self.drag)
        cv.tag_bind(self.char, "<ButtonRelease-1>", self.release)
        cv.tag_bind(self.char, "<Double-Button-1>", self.pat)
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label="멈추기  (답 쓰는 중에 Esc)", command=self.brain.stop)
        menu.add_separator()
        menu.add_command(label="대화 기록 자세히  (일기장·설정은 여기서)", command=self.open_detail)
        menu.add_command(label="새 대화", command=self.new_chat)
        rooms_menu = tk.Menu(menu, tearoff=0, postcommand=lambda: self.fill_rooms(rooms_menu))
        menu.add_cascade(label="지난 대화", menu=rooms_menu)
        menu.add_command(label="이 대화방 이름 짓기", command=self.rename_room)
        menu.add_separator()
        move_menu = tk.Menu(menu, tearoff=0)
        move_menu.add_checkbutton(label="중력 (떨어지기/창 위에 앉기)", variable=self.gravity, command=self.gravity_changed)
        move_menu.add_separator()
        for value, label in (("off", "장난 안 함"), ("calm", "장난: 얌전히 (가끔 돌아다니기)"), ("wild", "장난: 난리 모드 (커서 밀기/창 흔들기)")):
            move_menu.add_radiobutton(label=label, value=value, variable=self.play, command=self.save_pos)
        menu.add_cascade(label="움직임", menu=move_menu)
        self.kakao = tk.BooleanVar(value=state.get("kakao", False))
        menu.add_checkbutton(label="카톡 모드 (자세히 창)", variable=self.kakao,
                             command=lambda: self.brain.set_body_state(kakao=self.kakao.get()))
        self.backend_var = tk.StringVar(value=self.brain.backend_mode)   # 다른 곳에서 쓰면 남겨 둠
        self.plain_var = tk.BooleanVar(value=self.brain.plain)
        self.char_var = tk.StringVar(value=self.brain.char)
        self.char_menu = tk.Menu(menu, tearoff=0, postcommand=self.fill_chars)
        if os.path.isfile(AV_EXE):
            av_menu = tk.Menu(menu, tearoff=0)
            av_menu.add_checkbutton(label="3D로 보기", variable=self.av3d, command=self.av_toggle)
            av_menu.add_checkbutton(label="버튜버 모드 (상반신)", variable=self.vt, command=self.vt_toggle)
            av_menu.add_command(label="크게", command=lambda: self.av_scale_by(0.25))
            av_menu.add_command(label="작게", command=lambda: self.av_scale_by(-0.25))
            self.model_menu = tk.Menu(av_menu, tearoff=0, postcommand=self.fill_models)
            av_menu.add_cascade(label="모델 바꾸기", menu=self.model_menu)
            av_menu.add_separator()
            av_menu.add_command(label="춤추기 (음악)", command=lambda: self.av_send(dance=True))
            av_menu.add_command(label="춤추기 (조용히)", command=lambda: self.av_send(dance=False))
            av_menu.add_command(label="춤 멈추기", command=lambda: self.av_send(dance="stop"))
            menu.add_cascade(label="3D 아바타", menu=av_menu)
        menu.add_command(label="숨기기  (Ctrl+Alt+Q로 다시 부르기)", command=self.hide)
        menu.add_command(label="사용법 / 처음 설정", command=self.open_tutorial)
        menu.add_separator()
        menu.add_command(label="종료", command=root.destroy)
        def popup_menu(e):
            # 3D 창이 맨 위에 떠서 메뉴를 가리므로, 메뉴가 열려 있는 동안만 잠깐 숨김
            self.av_send(show=False)
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()
                root.after(150, self.av_rect)
        cv.tag_bind(self.char, "<Button-3>", popup_menu)

        self.text.bind("<Button-1>", lambda e: self.reveal(len(self.message)))  # 말풍선 클릭하면 바로 다 보임
        cv.bind("<Button-1>", self.button_click)
        for tag in (self.char, "histbtn", "detailbtn", "backendbtn", "clearatt", "voicebtn"):
            cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))

        self.render()
        wa = winsys.work_area(0, 0)
        cx, feet = state.get("pos", (wa[2] - self.cw / 2 - 20, wa[3]))   # 지난번 위치 (없으면 주 모니터 오른쪽 아래)
        self.place_char(cx, feet)
        root.update_idletasks()
        # 파일 끌어다 놓기: 단감/말풍선/입력창 어디에 떨궈도 받음 (돌려받은 콜백은 붙잡아 둬야 함)
        self.drops = []              # 드롭/단축키는 다른 스레드에서 오니까 여기 모았다가 frame()에서 처리
        self.drop_hooks = [winsys.accept_files(int(w.winfo_id()), lambda f: self.drops.append(("drop", f)))
                           for w in (cv, self.text, self.entry)]
        winsys.hotkey(*HOTKEY, lambda: self.drops.append(("hotkey",)), lambda: self.drops.append(("hotkey_fail",)))

        self.brain.start()
        if self.av3d.get():
            self.av_start()
        self.bob()
        self.schedule_talk()
        self.schedule_play()
        root.after(800, self.open_tutorial if fresh else self.greet)
        self.away_from = None       # 자리 비움 시작 시각
        self.db_warned = False
        self.ticks = 0
        self.tick()

    @property
    def busy(self):
        return self.brain.busy

    # ── 주기적으로 확인하는 것들 (5초마다) ──
    def tick(self):
        try:
            self.watch_away()
            if not self.hidden and not self.touring and self.root.winfo_ismapped():   # 안내 중엔 오버레이가 위에 있게
                winsys.keep_on_top(self.root.winfo_id())
            if self.ticks % (WATCH_SEC // 5) == 0:
                self.watch_servers()
            if self.brain.theme == "auto" and PALETTES[self.brain.effective_theme()] is not self.pal:   # 윈도우 테마가 바뀜
                self.apply_theme()
        except Exception:
            traceback.print_exc()        # error.log
        self.ticks += 1
        self.root.after(5000, self.tick)

    def watch_away(self):
        """AWAY_MIN분 넘게 입력 없다가 다시 입력이 오면 돌아온 걸로 보고 말 걸기."""
        idle = winsys.idle_seconds()
        if idle >= core.AWAY_MIN * 60:
            self.away_from = self.away_from or time.time() - idle
            if not self.open and not self.busy:
                self.face("sleepy")                      # 사용자 없으면 꾸벅꾸벅
        elif self.away_from and idle < 5:
            away, self.away_from = time.time() - self.away_from, None
            if not self.busy:
                self.face("normal")
            self.root.after(3000, self.welcome, away)   # 잠금 화면 풀리는 동안 기다림

    def welcome(self, away):
        if self.busy or self.hidden:
            return
        if core.TALK_AI:
            self.brain.welcome(away)
        else:
            key, text = random.choice(core.char_lines(self.brain.char, "WELCOMES", core.WELCOMES))
            self.pop(key, text.format(d=core.away_text(away)))

    def watch_servers(self):
        """게임 서버가 꺼지면(튕기면) 알려 줌. 켜질 때도 한마디."""
        exes = winsys.running_exes()
        now = {name: path.lower() in exes for name, path in WATCH}
        if self.servers is not None:
            down = [n for n in now if self.servers[n] and not now[n]]
            up = [n for n in now if now[n] and not self.servers[n]]
            if down:
                self.alert("surprised", f"앗, {', '.join(down)}가 꺼졌어! 사용자가 끈 거야? 아니면 튕긴 거야.")
            elif up:
                self.pop("happy", f"{', '.join(up)} 켜진 거 봤어. 꺼지면 바로 알려 줄게~")
        self.servers = now

    def save_pos(self):
        cx, feet = self.char_pos()
        self.brain.set_body_state(pos=[round(cx), round(feet)], gravity=self.gravity.get(), play=self.play.get())

    # ── 숨기기/부르기 (Ctrl+Alt+Q) ──
    def hotkey_pressed(self):
        if self.hidden:                  # 숨어 있으면 → 나와서 말풍선 열기
            self.unhide()
            self.toggle(True)
        elif not self.open:              # 나와 있으면 → 말풍선 열기
            self.toggle(True)
        else:                            # 말풍선까지 열려 있으면 → 숨기
            self.hide()

    def hide(self):
        self.hidden, self.open = True, False
        self.render()
        self.root.withdraw()
        self.av_send(show=False)

    def unhide(self):
        if self.hidden:
            self.hidden = False
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.av_rect()

    def alert(self, key, text):
        """꼭 봐야 하는 알림 (알람, 서버 꺼짐): 숨어 있어도 나오고, 자동으로 안 닫히고, 소리도 냄."""
        self.unhide()
        winsys.beep()
        self.pop(key, text, sticky=True, note=False)

    # ── 첨부 (Ctrl+V 사진, 끌어다 놓은 파일) ──
    def paste(self, e=None):
        try:
            from PIL import ImageGrab
            clip = ImageGrab.grabclipboard()
        except Exception:
            return None
        if isinstance(clip, list):               # 탐색기에서 복사한 파일들
            self.add_attach(clip)
        elif hasattr(clip, "save"):              # 캡처한 사진
            self.add_attach([core.paste_image(clip)])
        else:
            return None                          # 글자면 원래대로 붙여넣기
        return "break"

    def add_attach(self, files):
        self.attach = (self.attach + [f for f in core.save_attachments(files) if f not in self.attach])[-10:]
        self.unhide()
        self.open = True
        self.render()
        self.entry.focus_force()

    def clear_attach(self):
        self.attach = []
        self.render()

    # ── 먼저 말 걸기 ──
    def open_tutorial(self):
        t = getattr(self, "tutorial", None)
        if t and t.win.winfo_exists():
            t.win.lift()
            return
        self.tutorial = dangam_tutorial.Tutorial(self.root, self.brain, self.pal, body=self)

    def greet(self):
        h = time.localtime().tm_hour
        _, _, key, text = next(g for g in core.char_lines(self.brain.char, "GREETS", core.GREETS) if g[0] <= h < g[1])
        self.pop(key, core.nick_fill(text).format(h=h))

    def pat(self, e=None):
        """더블클릭 = 쓰다듬기."""
        if self.click_job:
            self.root.after_cancel(self.click_job)
            self.click_job = None
        self.dbl = True
        if not self.busy:
            self.pop(*random.choice(core.char_lines(self.brain.char, "PATS", core.PATS)))

    def load_faces(self):
        if self.av3d.get():          # 3D일 땐 표정마다 같은 마스크 그림
            if not self.av_img:      # 3D 창이 마스크를 보내기 전까지 쓸 대충 사람 모양
                w, h = (round(v * self.av_scale) for v in (AV_SIZE_VT if self.vt.get() else AV_SIZE))
                self.av_img = tk.PhotoImage(width=w, height=h)
                self.av_img.put("#f0d8dc", to=(w // 2 - 12, 20, w // 2 + 12, h - 30))
            self.imgs = {k: self.av_img for k in FACES}
            return
        self.imgs = {k: self._face_img(core.face_file(self.brain.char, k)) for k in FACES}

    @staticmethod
    def _face_img(path):
        """BG(#ff00ff)가 투명색이라 반투명 가장자리가 분홍으로 번진다 -> 읽을 때 알파를 0/255로 자름.
        새 캐릭터 그림이 어떻게 만들어졌든 여기서 한 번에 막는다."""
        try:
            import base64, io
            from PIL import Image
            im = Image.open(path).convert("RGBA")
            r, g, b, a = im.split()
            im = Image.merge("RGBA", (r, g, b, a.point(lambda v: 255 if v >= 128 else 0)))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        except Exception:
            return tk.PhotoImage(file=path)

    def face(self, key):
        key = key if key in FACES else "normal"
        self.brain.face = key
        if not self.av_moving:
            self.cv.itemconfigure(self.char, image=self.imgs[key])
        self.av_send(face=key)

    # ── 3D 아바타 ──
    def av_send(self, **msg):
        if self.av_sock and self.av_proc and self.av_proc.poll() is None:
            try:
                self.av_sock.sendto(json.dumps(msg).encode(), ("127.0.0.1", AV_PORT))
            except OSError:
                pass

    def av_rect(self):
        if self.av3d.get() and hasattr(self, "char_xy") and hasattr(self, "wx"):   # 시작 직후엔 아직 위치가 없음
            x, y = self.char_xy
            self.av_send(rect=[self.wx + x, self.wy + y, self.cw, self.ch], show=not self.hidden)

    def av_resize(self):
        """그림 크기가 바뀌면 발 위치는 그대로 두고 다시 배치."""
        cx, feet = self.char_pos()
        self.load_faces()
        self.cw, self.ch = self.imgs["normal"].width(), self.imgs["normal"].height()
        self.face_y = self.av_face_y()
        self.cv.itemconfigure(self.char, image=self.imgs[self.brain.face if self.brain.face in FACES else "normal"])
        self.render()
        self.place_char(cx, feet)

    def av_start(self):
        import socket
        if not self.av_sock:
            self.av_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.av_sock.bind(("127.0.0.1", AV_MY_PORT))
            self.av_sock.setblocking(False)
        if not (self.av_proc and self.av_proc.poll() is None):
            env = dict(os.environ, AVATAR_FOLLOW="1", AVATAR_CHAR=self.brain.char, AVATAR_Q=f"&bs={self.av_bust.get()}")
            if self.vt.get():
                env["AVATAR_VT"] = "1"
            self.av_proc = subprocess.Popen([AV_EXE, AV_DIR], cwd=AV_DIR, env=env,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
            winsys.OWN_PIDS.add(self.av_proc.pid)
        self.av_resize()
        self.av_poll()

    AV_MODELS = []   # 3D 모델은 이 배포판에 들어 있지 않음

    def av_cur_model(self):
        try:
            st = json.load(open(os.path.join(AV_DIR, "state.json"), encoding="utf-8"))
        except Exception:
            st = {}
        return (st.get("models") or {}).get(self.brain.char) or "default"

    def fill_models(self):
        m = self.model_menu
        m.delete(0, "end")
        if not hasattr(self, "_model_icons"):
            self._model_icons = {}
        cur = self.av_cur_model()
        for k, n in self.AV_MODELS:
            if k not in self._model_icons:
                try:
                    self._model_icons[k] = tk.PhotoImage(file=os.path.join(AV_DIR, "thumbs", k + "_icon.png"))
                except Exception:
                    self._model_icons[k] = None
            kw = {"image": self._model_icons[k], "compound": "left"} if self._model_icons[k] else {}
            m.add_command(label=("✓ " if k == cur else "   ") + n, command=lambda k=k: self.av_model_set(k), **kw)

    def av_model_set(self, k):
        path = os.path.join(AV_DIR, "state.json")
        try:
            st = json.load(open(path, encoding="utf-8"))
        except Exception:
            st = {}
        st["model"] = k
        st.setdefault("models", {})[self.brain.char] = k
        json.dump(st, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        self.av_send(quit=True)   # 3D 창이 꺼지면 av_poll이 새 모델로 다시 켬

    def av_bust_set(self):
        self.brain.set_body_state(av_bust=self.av_bust.get())
        self.av_send(bust=self.av_bust.get())

    def av_stop(self):
        self.av_send(quit=True)
        self.av_proc = None
        self.av_resize()

    def av_face_y(self):
        return round((AV_FACE_Y_VT if self.vt.get() else AV_FACE_Y) * self.av_scale) if self.av3d.get() else FACE_Y

    def vt_toggle(self):
        """상반신 모드 켜고 끄기: 3D 창을 새 모드로 다시 띄우고(av_poll이 꺼진 걸 보고 다시 켬) 창 크기를 바꾼다."""
        self.brain.set_body_state(vt=self.vt.get())
        self.walk = None
        if self.av3d.get():
            self.av_send(quit=True)
            self.av_img = None
            self.av_resize()

    def av_scale_by(self, d):
        """3D 몸 크기 바꾸기: 3D 창을 새 크기로 다시 띄움 (vt_toggle과 같은 방식)."""
        s = min(2.0, max(0.75, self.av_scale + d))
        if s == self.av_scale:
            return
        self.av_scale = s
        self.brain.set_body_state(av_scale=s)
        self.walk = None
        if self.av3d.get():
            self.av_send(quit=True)
            self.av_img = None
            self.av_resize()

    def av_toggle(self):
        self.brain.set_body_state(av3d=self.av3d.get())
        self.av_start() if self.av3d.get() else self.av_stop()

    def av_poll(self, n=0):
        """3D 창이 보낸 것 받기 (창 핸들, 마스크), 2초마다 위치 다시 알려 주기(살아 있다는 신호도 겸함)."""
        if not self.av3d.get():
            return
        while True:
            try:
                msg = json.loads(self.av_sock.recv(65536))
            except (BlockingIOError, OSError, ValueError):
                break
            if msg.get("hwnd"):      # 3D 창의 주인을 위젯으로: 늘 위젯 위에 그려짐
                top = int(self.root.wm_frame(), 16)
                ctypes.windll.user32.SetWindowLongPtrW(ctypes.c_void_p(msg["hwnd"]), -8, ctypes.c_void_p(top))
                self.av_rect()
            if msg.get("mask"):
                try:
                    self.av_img.configure(file=msg["mask"])
                except tk.TclError:
                    pass
        if self.av_proc and self.av_proc.poll() is not None:   # 3D 창이 죽었으면 다시 켬
            self.av_proc = None
            self.av_start()
            return
        if bool(self.dragging) != getattr(self, "av_held", False):   # 잡아 들면 3D 몸이 허우적거리도록 알림
            self.av_held = bool(self.dragging)
            self.av_send(held=self.av_held)
        if n % 20 == 0:
            self.av_rect()
        self.root.after(100, self.av_poll, n + 1)

    def schedule_talk(self):
        self.root.after(random.randint(core.TALK_MIN * 60000, core.TALK_MAX * 60000), self.talk)

    def talk(self):
        """가끔 먼저 말 걸기. 대답 중, 숨김, 입력 중, 방금까지 얘기하던 중, 자리 비움이면 건너뜀."""
        self.schedule_talk()
        if self.touring or self.busy or self.hidden or self.entry.get("1.0", "end-1c").strip():
            return
        if time.time() - self.brain.last_chat < core.TALK_QUIET * 60:   # 말풍선이 열려 있어도 조용하면 말 걸기
            return
        if winsys.idle_seconds() > core.TALK_IDLE * 60:
            return
        if core.TALK_AI:
            self.brain.talk_ai()
            return
        h = time.localtime().tm_hour
        pool = [l for l in core.char_lines(self.brain.char, "LINES", core.LINES) if l[0] <= h < l[1] and l != self.brain.last_line]
        self.brain.last_line = line = random.choice(pool)
        self.pop(line[2], line[3])

    def pop(self, key, text, sticky=False, note=True, voiced=True):
        """먼저 말 건 말풍선. 포커스는 안 뺏고, sticky가 아니면 대답 없을 때 TALK_CLOSE초 뒤 닫힘."""
        if self.hidden:
            return
        # ponytail: 정해진 대사는 단감 말투 그대로, 이름만 바꿈. 캐릭터별 대사 필요하면 characters/<id>/lines.json
        text = text.replace("단감", self.brain.name)
        if note:
            self.brain.note_talk(text)
        self.face(key)
        self.open = True
        self.show(text, typed=True)
        if voiced:
            self.speak_aloud(text, key)
        self.jump_at = time.time()
        msg = self.message
        if not sticky:
            self.root.after(core.TALK_CLOSE * 1000, lambda: self.message is msg and not self.busy
                            and not self.entry.get("1.0", "end-1c").strip() and self.toggle(False))

    def test_voice(self):
        voice.speak("이 정도 크기면 어때?", None, self.brain.char)

    def toggle_voice(self):
        on = not voice.enabled()
        voice.set_enabled(on)
        self.render()
        if on:   # 서버 띄우고 모델 올린 뒤 상태 알려 줌
            self.pop("coding", "목소리 준비 중이야. 잠깐만 기다려 줘.", note=False, voiced=False)
            voice.warmup(self.brain.char, lambda ok: self.root.after(0, lambda: self.voice_ready(ok)))

    def voice_ready(self, ok):
        if ok:
            self.pop("happy", "준비 끝. 이제 소리 잘 나!", note=False)
        else:
            self.pop("sad", "목소리 서버가 안 켜졌어. 그래픽카드가 바쁜지 한 번 봐 줘.", note=False, voiced=False)

    def speak_aloud(self, text, face=None):
        """목소리가 있는 캐릭터만 읽어 줌 (이 배포판엔 없음) (숨김/전체 화면 게임 중엔 조용히)."""
        if self.brain.char in voice.VOICED and voice.enabled() and not self.hidden and not winsys.fullscreen() and not os.environ.get("DANGAM_NOVOICE"):
            voice.speak(text, face, self.brain.char)

    # ── 두뇌가 보낸 말 ──
    def on_event(self, kind, *args):
        if kind == "reply":
            face, text, web = args
            self.entry.configure(state="normal")
            self.face(face)
            self.open = True
            self.show(text, typed=True)   # 숨어 있으면 안 나오고, Ctrl+Alt+Q로 부르면 이 답장이 떠 있음. 마크다운은 show가 모양으로 바꿈
            self.speak_aloud(self.message, face)
            self.jump_at = time.time()
            if not web and not self.hidden:
                self.entry.focus_force()
        elif kind == "act":
            self.do_act(args[0])
        elif kind == "pop":
            face, text, sticky = args
            self.entry.configure(state="normal")
            if sticky:
                self.alert(face, text)
            else:
                self.pop(face, text, note=False)
        elif kind == "busy":
            self.face("coding")
            self.typing()
        elif kind == "status":
            self.face(args[0])
        elif kind == "char":   # 캐릭터 바뀜: 그림 다시 읽고 새 방 인사
            self.load_faces()
            if self.av3d.get():
                self.av_send(quit=True)   # 3D 창이 꺼지면 av_poll이 새 캐릭터 모델로 다시 켬
            self.face("happy")
            self.open = True
            self.show(f"{self.brain.name} 등장~ 새 방에서 이어서 얘기하자.", typed=True)
        elif kind == "theme":
            self.theme_var.set(self.brain.theme)
            self.apply_theme()
        elif kind == "backend":
            self.backend_var.set(self.brain.backend_mode)
            self.render()

    # ── 테마 ──
    def apply_theme(self):
        self.pal = P = PALETTES[self.brain.effective_theme()]
        self.text.configure(bg=P["fill"], fg=P["ink"])
        self.entry.configure(bg=P["entry"], fg=P["ink"], insertbackground=P["ink"])
        self.text.tag_config("who_me", foreground=P["me_who"])
        self.text.tag_config("me", foreground=P["me"])
        self.text.tag_config("who_dangam", foreground=P["accent"])
        self.text.tag_config("sys", foreground=P["sys"])
        self.text.tag_config("m_q", foreground=P["muted"])
        self.text.tag_config("m_hr", foreground=P["line"])
        for name in self.mdtags:
            if "c" in name[2:]:
                self.text.tag_config(name, foreground=P["accent"])
        if hasattr(self, "char_xy"):
            self.render()

    # ── 그리기 ──
    def render(self):
        """말풍선 열림/닫힘과 글 길이에 맞춰 다시 그림. 캐릭터의 화면 위치는 그대로 둠."""
        cv, cw, ch = self.cv, self.cw, self.ch
        old = getattr(self, "char_xy", None)
        P = self.pal
        cv.delete("deco")
        if not self.open:
            cv.itemconfigure(self.twin, state="hidden")
            cv.itemconfigure(self.ewin, state="hidden")
            self.char_xy = (0, BOB + JUMP)
            W, H = cw, ch + BOB + JUMP
        else:
            # 글 높이 재기: 같은 폭의 canvas 글자로 재고, Text 위젯은 그 높이로 (넘치면 스크롤)
            if self.hist:
                th = MAXH
            else:
                indent = any(t in ("m_q", "m_li") for _, _, t in self.spans)       # 인용/목록은 들여쓴 만큼 좁아서 줄이 더 늘어남
                wide = any(t in self.mdtags and ("b" in t[2:] or "h" in t[2:]) for _, _, t in self.spans)   # 굵은 글자는 폭이 넓음
                probe = cv.create_text(-2000, 0, text=self.message, font=FONT, width=BW - 32 - (14 if indent else 0), anchor="nw")
                x1, y1, x2, y2 = cv.bbox(probe)
                cv.delete(probe)
                th = min(y2 - y1 + 4 + (self.line_h if wide or indent else 0), MAXH)
            bh = th + 44
            ah = 26 if self.attach else 0          # 첨부 줄 높이
            oy = max(0, self.face_y + 20 + BOB + JUMP - bh)          # 말풍선이 짧으면 아래로 내려서 얼굴 높이에 맞춤
            top, bot = oy + 2, oy + bh
            W = BW + cw - 20
            cy = bot - 18 - self.face_y                 # 꼬리 끝이 얼굴 높이에 오도록 캐릭터 위치
            ih = self.in_lines * self.line_h
            H = max(cy + ch, bot + ah + ih + 28)
            self.char_xy = (W - cw, cy)

            rounded(cv, 2, top, BW, bot, 18, fill=P["fill"], outline=P["line"], width=2, tags="deco")
            cv.create_polygon(BW - 2, bot - 36, BW + 16, bot - 18, BW - 2, bot - 22,
                              fill=P["fill"], outline=P["line"], width=2, tags="deco")
            cv.create_rectangle(BW - 4, bot - 34, BW, bot - 24, fill=P["fill"], outline="", tags="deco")
            cv.create_text(16, top + 14, text="대화 기록" if self.hist else self.brain.name, fill=P["accent"],
                           font=(FONT[0], 9, "bold"), anchor="w", tags="deco")
            current = "GPT" if self.brain.current_backend() == "codex" else "Claude"
            mode = "자동·" + current if self.brain.backend_mode == "auto" else current
            cv.create_text(125, top + 14, text=mode + " ▾", fill=P["muted"],
                           font=(FONT[0], 8), anchor="e", tags=("deco", "backendbtn"))
            btn = cv.create_text(BW - 14, top + 14, text="자세히", fill=P["muted"],
                                 font=(FONT[0], 8), anchor="e", tags=("deco", "detailbtn"))
            hb = cv.create_text(cv.bbox(btn)[0] - 10, top + 14, text="닫기" if self.hist else "기록", fill=P["muted"],
                                font=(FONT[0], 8), anchor="e", tags=("deco", "histbtn"))
            if self.brain.char in voice.VOICED:   # 목소리 켜기/끄기 (켰을 때만 읽음)
                on = voice.enabled()
                cv.create_text(cv.bbox(hb)[0] - 10, top + 14, text="♪ 소리 켬" if on else "♪ 소리 끔",
                               fill=P["accent"] if on else P["muted"], font=(FONT[0], 8), anchor="e", tags=("deco", "voicebtn"))

            self.fill_text()
            cv.coords(self.twin, 16, top + 26)
            cv.itemconfigure(self.twin, width=BW - 32, height=th, state="normal")

            if self.attach:
                names = ", ".join(os.path.basename(f).split("_", 3)[-1] if os.path.dirname(f) == ATTACH_DIR
                                  else os.path.basename(f) for f in self.attach)
                label = f"첨부 {len(self.attach)}개 · {names}"
                label = label if len(label) <= 28 else label[:27] + "…"
                # 투명 배경에 바로 쓰면 글자 테두리가 번져서, 작은 말풍선을 깔고 씀
                rounded(cv, 2, bot + 8, BW, bot + 30, 11, fill=P["fill"], outline=P["line"], width=1, tags="deco")
                cv.create_text(14, bot + 19, text=label, fill=P["accent"], font=(FONT[0], 8), anchor="w", tags="deco")
                cv.create_text(BW - 28, bot + 19, text="✕", fill=P["muted"], font=(FONT[0], 9, "bold"),
                               anchor="e", tags=("deco", "clearatt"))   # 오른쪽 20px는 단감 머리카락이 덮어서 안쪽에
            rounded(cv, 2, bot + ah + 8, BW, bot + ah + ih + 26, 16, fill=P["entry"], outline=P["line"], width=2, tags="deco")
            cv.coords(self.ewin, 16, bot + ah + 17)
            cv.itemconfigure(self.ewin, width=BW - 30, height=ih, state="normal")
            cv.tag_raise(self.char)                # 머리카락이 말풍선 테두리 위로

        cv.configure(width=W, height=H)
        r = self.root
        if old and r.winfo_ismapped():   # 캐릭터가 화면에서 제자리에 있도록 창을 옮김
            self.move(self.wx + old[0] - self.char_xy[0], self.wy + old[1] - self.char_xy[1], W, H)
        else:
            r.geometry(f"{W}x{H}")
        self.av_rect()

    def move(self, wx, wy, W=None, H=None):
        self.wx, self.wy = round(wx), round(wy)
        size = f"{W}x{H}" if W else ""
        self.root.geometry(f"{size}+{self.wx}+{self.wy}")
        self.av_rect()
        # 말풍선이 늘어나서 창만 커질 땐 캐릭터의 화면 위치가 그대로라 3D 창도 안 움직임 (생각 중 점 찍을 때마다 깜빡이던 원인)
        cxy = getattr(self, "char_xy", (0, 0))
        cpos = (self.wx + cxy[0], self.wy + cxy[1])
        moved, self.av_cpos = cpos != getattr(self, "av_cpos", None), cpos
        if self.av3d.get() and self.av_img and (moved or self.av_moving):   # 움직이는 동안 3D 창이 한 박자 늦게 따라와서 마스크가 삐져나옴
            if not self.av_moving:            # → 그동안은 몸통 가운데 가는 막대만 남겨 둠
                core = getattr(self, "av_core", None)
                if not core or core.width() != self.av_img.width() or core.height() != self.av_img.height():
                    w, h = self.av_img.width(), self.av_img.height()
                    core = self.av_core = tk.PhotoImage(width=w, height=h)
                    core.put("#f0d8dc", to=(w // 2 - 8, h // 4, w // 2 + 8, h * 9 // 20))   # 치마 안쪽까지만: 더 길면 다리를 벌렸을 때 가운데로 삐져나옴
                self.cv.itemconfigure(self.char, image=core)
            else:
                self.root.after_cancel(self.av_moving)
            self.av_moving = self.root.after(250, self.av_still)

    def av_still(self):
        self.av_moving = None
        if self.av3d.get():
            self.cv.itemconfigure(self.char, image=self.imgs.get(self.brain.face, self.av_img))

    def sink(self):
        """상반신 모드는 창 아랫면이 평평하게 잘려 있어서 파묻히면 작업표시줄을 덮음 → 딱 붙임."""
        return 0 if self.av3d.get() and self.vt.get() else SINK

    def char_pos(self):
        """캐릭터의 (가운데 x, 발 y) 화면 좌표."""
        return self.wx + self.char_xy[0] + self.cw / 2, self.wy + self.char_xy[1] + self.ch - self.sink()

    def place_char(self, cx, feet):
        self.move(cx - self.char_xy[0] - self.cw / 2, feet + self.sink() - self.char_xy[1] - self.ch)

    # ── 던지기/중력/창 위에 앉기 ──
    def gravity_changed(self):
        self.falling = self.gravity.get()
        self.perch = None
        self.save_pos()

    def physics(self, dt):
        if self.dragging or self.hidden or not self.gravity.get():
            return
        cx, feet = self.char_pos()
        wa = winsys.floor_area(cx, feet - 10)
        if not self.falling:
            if self.perch == "floor":
                if abs(feet - wa[3]) > 2:                   # 작업표시줄 위치가 바뀜
                    self.falling = True
                return
            r = self.perch and winsys.window_rect(self.perch)
            if not r or r[1] < wa[1] + self.ch * 0.6 or r[1] > wa[3] or feet > wa[3] + 2 or not (r[0] <= cx <= r[2]):
                self.perch, self.falling = None, True       # 창이 닫히거나 최소화되거나 작업표시줄 밑으로 내려가면 떨어짐
                return
            if r != self.perch_rect:                        # 창을 옮기면 따라감
                self.place_char(cx + r[0] - self.perch_rect[0], r[1])
                self.perch_rect = r
            return

        self.vy = min(self.vy + GRAVITY * dt, 4000)
        nx, nf = cx + self.vx * dt, feet + self.vy * dt
        half = self.cw / 2 - 25
        if nx - half < wa[0]:
            nx, self.vx = wa[0] + half, abs(self.vx) * BOUNCE
        if nx + half > wa[2]:
            nx, self.vx = wa[2] - half, -abs(self.vx) * BOUNCE
        if nf - self.ch < wa[1]:
            nf, self.vy = wa[1] + self.ch, abs(self.vy) * BOUNCE

        land, where, rect = None, None, None
        if nf > wa[3]:                                       # 던지다 작업표시줄 밑으로 파고들면 위로 끌어올림
            nf = wa[3]
            if self.vy <= 0:
                self.vy = 0.0
        if self.vy > 0:
            if nf >= wa[3]:
                land, where = wa[3], "floor"
            wins = winsys.top_windows(os.getpid())
            for i, (h, r) in enumerate(wins):
                top = r[1]
                if (r[0] + 15 <= nx <= r[2] - 15 and feet - 1 <= top <= nf and top >= wa[1] + self.ch * 0.6
                        and (land is None or top < land)
                        and not any(q[0] <= nx <= q[2] and q[1] <= top + 2 <= q[3] for _, q in wins[:i])):  # 다른 창에 가려진 곳은 안 앉음
                    land, where, rect = top, h, r
        if land is not None:
            nf = land
            if self.vy > 700:                                # 세게 떨어지면 통 튀어 오름
                self.vy, self.vx = -self.vy * BOUNCE, self.vx * 0.6
            else:
                self.falling, self.vx, self.vy = False, 0.0, 0.0
                self.perch, self.perch_rect = where, rect
                self.save_pos()
        self.place_char(nx, nf)

    # ── 장난치기 ──
    def schedule_play(self):
        self.root.after(random.randint(*PLAY_SEC.get(self.play.get(), (40, 120))) * 1000, self.play_tick)

    def play_tick(self):
        """가끔 혼자 장난. 말풍선 열림/대답 중/숨김/들고 있음/떨어지는 중/자리 비움/전체 화면(게임)이면 쉼."""
        self.schedule_play()
        try:
            wild = self.play.get() == "wild"
            typing = self.entry.get("1.0", "end-1c").strip()
            if (self.play.get() == "off" or not self.gravity.get() or self.busy or self.hidden or self.mouse_over()
                    or self.root.state() == "withdrawn"               # 숨바꼭질 중
                    or (self.open and (not wild or typing))          # 난리 모드는 말풍선 열려 있어도 (입력 중만 빼고)
                    or self.dragging or self.falling or self.walk or winsys.idle_seconds() > 60 or winsys.fullscreen()):
                return
            cx, feet = self.char_pos()
            mx, my = winsys.cursor()
            acts = ["walk", "walk", "chase", "jump"]
            if wild and math.hypot(mx - cx, my - (feet - self.ch / 2)) < 500:
                acts += ["nudge"] * 3
            fg = winsys.foreground(os.getpid())
            shakeable = [h for h in (self.perch if self.perch != "floor" else None, fg) if h and winsys.movable(h)]
            if wild:
                acts += ["grab", "grab", "hide", "pinball"] + ["shake"] * 3 * bool(shakeable)
                if fg and winsys.movable(fg) and self.perch != fg:
                    acts += ["climb"] * 2
            act = random.choice(acts)
            if act == "walk":
                self.walk = (cx + random.choice((-1, 1)) * random.randint(80, 1200 if wild else 400), time.time() + 8)
            elif act == "chase":
                self.walk = ("cursor", time.time() + 5)
            elif act == "jump":
                self.perch, self.falling = None, True
                self.vx, self.vy = random.choice((-1, 1)) * random.randint(150, 900 if wild else 450), -random.randint(1300, 2600 if wild else 1900)
                self.play_say("jump")
            elif act == "nudge":
                self.play_say("nudge")
                d = math.hypot(mx - cx, my - feet + self.ch / 2) or 1
                ux, uy = (mx - cx) / d, (my - feet + self.ch / 2) / d
                for i in range(1, 13):                   # 12번에 나눠서 스르륵 밀어냄
                    self.root.after(i * 20, lambda i=i: winsys.set_cursor(mx + ux * i * 12, my + uy * i * 12))
            elif act == "shake":
                self.play_say("shake")
                h = shakeable[0]
                r = winsys.window_rect(h)
                for i, dx in enumerate((20, -20, 16, -16, 12, -12, 6, -6, 0)):   # 마지막엔 원래 자리로
                    self.root.after(i * 50, lambda dx=dx: winsys.move_window(h, r[0] + dx, r[1]))
            elif act == "grab":                          # 커서를 단감 머리 위로 끌고 옴
                self.play_say("grab")
                hx, hy = cx, feet - self.ch * 0.8
                for i in range(1, 16):
                    f = i / 15
                    self.root.after(i * 20, lambda f=f: winsys.set_cursor(mx + (hx - mx) * f, my + (hy - my) * f))
            elif act == "climb":                         # 보고 있는 창 위로 정확히 점프
                r = winsys.window_rect(fg)
                tx, top = random.uniform(r[0] + 40, r[2] - 40), r[1]
                h = max(feet - top, 0) + 80
                vy = -math.sqrt(2 * GRAVITY * h)
                t = (-vy + math.sqrt(max(vy * vy - 2 * GRAVITY * (feet - top), 0))) / GRAVITY
                self.perch, self.falling = None, True
                self.vx, self.vy = max(-3000, min(3000, (tx - cx) / t)), max(vy, -4000)
                self.play_say("climb")
            elif act == "pinball":                       # 벽에 튕기면서 날아다님
                self.perch, self.falling = None, True
                self.vx, self.vy = random.choice((-1, 1)) * 3000, -2200
                self.play_say("pinball")
            elif act == "hide":                          # 사라졌다가 다른 데서 뚝 떨어짐
                self.play_say("hide")
                self.root.after(2500, self.hide_and_seek)
        except Exception:
            traceback.print_exc()

    def hide_and_seek(self):
        if self.hidden or self.dragging:
            return
        self.root.withdraw()
        self.av_send(show=False)
        def back():
            wa = winsys.work_area(*self.char_pos())
            self.place_char(random.uniform(wa[0] + self.cw, wa[2] - self.cw / 2), wa[1] + self.ch + 10)
            self.perch, self.falling, self.vx, self.vy = None, True, 0.0, 0.0
            if not self.hidden:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
                self.av_rect()
                self.play_say("found")
        self.root.after(random.randint(4000, 9000), back)

    def do_act(self, act):
        """AI가 답변 태그([행동 | ...])로 시킨 움직임. 중력이 꺼져 있거나 떨어지는 중이면 무시."""
        if self.hidden or self.dragging or self.falling or not self.gravity.get():
            return
        cx, feet = self.char_pos()
        if act in ("왼쪽걷기", "오른쪽걷기", "커서로") and self.vt.get() and self.av3d.get():
            return
        if act in ("왼쪽걷기", "오른쪽걷기"):
            base = self.walk[0] if self.walk and self.walk[0] != "cursor" and time.time() < self.walk[1] else cx   # 연달아 시킨 걷기는 이어서 더 감
            self.walk = (base + (-1 if act[0] == "왼" else 1) * 320, time.time() + 8 + (4 if base != cx else 0))
        elif act == "커서로":
            self.walk = ("cursor", time.time() + 6)
        elif act == "점프":
            self.perch, self.falling = None, True
            self.vx, self.vy = 0.0, -1700
            return
        self.walk_cmd_until = self.walk[1]      # 말풍선이 열려 있어도 이번 걷기는 계속

    def play_say(self, act):
        """장난칠 때 한마디, 3초 뒤 닫음. 대화 중(말풍선 열림)이면 대화 글은 안 덮고 표정만."""
        if self.open:
            return self.face(core.char_lines(self.brain.char, "PLAY_LINES", PLAY_LINES)[act][0][0])
        self.pop(*random.choice(core.char_lines(self.brain.char, "PLAY_LINES", PLAY_LINES)[act]), note=False)
        msg = self.message
        self.root.after(3000, lambda: self.message is msg and not self.busy
                        and not self.entry.get("1.0", "end-1c").strip() and self.toggle(False))

    def stroll(self, dt):
        """걷기: 지금 앉은 곳(바닥/창) 안에서만 목표 x까지 통통 걸어감."""
        if not self.walk or self.vt.get() and self.av3d.get():   # 상반신 모드는 걷지 않음
            self.walk = None
            return False
        target, until = self.walk
        if (self.dragging or self.falling or time.time() > until or self.mouse_over()
                or (self.open and self.play.get() != "wild" and time.time() > self.walk_cmd_until)):
            self.walk = None
            return False
        cx, feet = self.char_pos()
        tx = winsys.cursor()[0] if target == "cursor" else target
        wa = winsys.work_area(cx, feet - 10)
        if self.perch == "floor":
            wt = winsys.work_area(tx, feet - 10)         # 목적지가 있는 모니터 기준으로 잘라서 옆 디스플레이로도 넘어감
            lo, hi = (min(wa[0], wt[0]) + self.cw / 2 - 25, max(wa[2], wt[2]) - self.cw / 2 + 25)
        else:
            lo, hi = (self.perch_rect[0] + 15, self.perch_rect[2] - 15)
        lo += self.char_xy[0]                            # 말풍선 열려 있으면 왼쪽 말풍선도 화면 안에
        tx = max(lo, min(hi, tx))
        if abs(tx - cx) < 3:
            if target != "cursor":
                self.walk = None
            return False
        self.walk_sign = 1 if tx > cx else -1
        self.place_char(cx + math.copysign(min(WALK * (3 if self.play.get() == "wild" else 1) * dt, abs(tx - cx)), tx - cx), feet)
        if time.time() - self.jump_at > JUMP_SEC:        # 걸을 땐 통통
            self.jump_at = time.time()
        return True

    def bob(self):
        """매 프레임. 오류가 나도 멈추지 않게 (멈추면 단감이 굳고 대답도 못 받음) error.log에 남기고 계속."""
        fast = False
        try:
            fast = self.frame()
        except Exception:
            traceback.print_exc()
            self.falling = self.dragging = False
        self.root.after(16 if fast else 40, self.bob)

    def frame(self):
        """둥실둥실 + 폴짝 + 중력 + 두뇌/단축키/드롭에서 온 일 처리. 빨리 다시 불러야 하면 True."""
        x, y = self.char_xy
        now = time.time()
        dt, self.last_frame = min(now - self.last_frame, 0.05), now
        self.physics(dt)
        walking = self.stroll(dt)
        sign = self.walk_sign if walking else 0
        if sign != self.av_walk:                # 3D 몸이 걷는 동작을 하도록 알림
            self.av_walk = sign
            self.av_send(walk=sign, spd=3 if self.play.get() == "wild" else 1)
        dy = BOB * (math.cos(now * 2 * math.pi / BOB_SEC) - 1) / 2   # 0 ~ -BOB
        t = now - self.jump_at
        if t < JUMP_SEC:                                             # 폴짝
            dy -= JUMP * math.sin(math.pi * t / JUMP_SEC)
        self.cv.coords(self.char, x, y + (0 if self.falling or self.dragging or self.av3d.get() else dy))
        while not self.brain.events.empty():
            self.on_event(*self.brain.events.get())
        while self.drops:
            kind, *args = self.drops.pop(0)
            if kind == "drop":
                self.add_attach(args[0])
            elif kind == "hotkey":
                self.hotkey_pressed()
            elif kind == "hotkey_fail":
                self.pop("sad", "Ctrl+Alt+Q 단축키를 다른 프로그램이 쓰고 있어서 못 잡았어...")
        return self.falling or self.dragging or walking or t < JUMP_SEC

    def fill_text(self):
        """말풍선 글: 기록 보기면 전체 대화, 아니면 지금 말 (한 글자씩 보여 준 만큼)."""
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not self.hist:
            self.put_md(self.message, self.spans, upto=self.shown)
        elif not self.brain.log:
            t.insert("1.0", "아직 나눈 얘기가 없어.", "sys")
        for who, msg, *rest in self.brain.log if self.hist else []:
            if who == "sys":
                t.insert("end", f"── {msg} ──\n\n", "sys")
            else:
                files = rest[2] if len(rest) > 2 else []
                t.insert("end", ("나" if who == "me" else "단감") + "\n", "who_" + who)
                if who == "me":
                    t.insert("end", msg, who)
                else:
                    self.put_md(*md_parse(msg), base=who)
                t.insert("end", (f" [첨부 {len(files)}]" if files else "") + "\n\n", who)
        t.configure(state="disabled")
        t.see("end")

    def put_md(self, text, spans, base=None, upto=None):
        """plain 글을 모양(spans) 경계마다 끊어서 넣음 (인덱스 계산 없이 태그를 직접 붙임: 이모지가 있어도 안 어긋남)."""
        n = len(text) if upto is None else min(upto, len(text))
        cuts = sorted({0, n} | {min(max(p, 0), n) for s, e, _ in spans for p in (s, e)})
        for a, b in zip(cuts, cuts[1:]):
            tags = ([base] if base else []) + [tag for s, e, tag in spans if s <= a and b <= e]
            self.text.insert("end", text[a:b], tuple(tags))

    def toggle_hist(self):
        self.hist = not self.hist
        self.shown = len(self.message)   # 기록 닫으면 마지막 말은 다 보이게
        self.render()

    def cycle_backend(self):
        self.brain.set_backend("claude" if self.brain.current_backend() == "codex" else "codex")

    def button_click(self, e):
        """말풍선 작은 글자 버튼들. 글자 위 딱 맞게 눌러야 했던 걸 주변 6px까지 넓힘."""
        for tag, fn in (("histbtn", self.toggle_hist), ("detailbtn", self.open_detail),
                        ("backendbtn", self.cycle_backend), ("clearatt", self.clear_attach),
                        ("voicebtn", self.toggle_voice)):
            b = self.cv.bbox(tag)
            if b and b[0] - 6 <= e.x <= b[2] + 6 and b[1] - 6 <= e.y <= b[3] + 6:
                return fn()

    def mouse_over(self):
        mx, my = winsys.cursor()
        return self.wx <= mx <= self.wx + self.root.winfo_width() and self.wy <= my <= self.wy + self.root.winfo_height()

    def open_detail(self, tab="chat", tour=False):
        """대화 창을 따로 열기 (Edge 앱 모드: 주소창/탭 없는 창). 토큰은 주소 뒤(#)에 붙여서 서버 기록에도 안 남음."""
        url = self.brain.url(tab)
        size = "560,820"
        if tour:   # 사용법: 왼쪽 패널이 보이는 넓은 일반 창으로
            url, size = url.replace("#", "&tour=1#", 1), "1180,860"
        elif self.kakao.get() and tab == "chat":
            app = None   # 배포판: 다른 위젯에서 설치된 카톡 모드 앱을 재사용하지 않음 (주소가 달라 엉뚱한 캐릭터가 뜸)
            if app and os.path.exists(EDGE):   # 설치한 카톡 모드 앱이 있으면 그걸로 (제목 표시줄까지 카톡 색)
                return subprocess.Popen([EDGE, f"--app-id={app}"])
            url, size = url.replace("#", "&kakao=1#", 1), "400,680"
        if os.path.exists(EDGE):
            subprocess.Popen([EDGE, f"--app={url}", f"--window-size={size}"])
        else:
            webbrowser.open(url)

    def reveal(self, n):
        """글자를 n개까지 보여 줌. 말풍선 크기는 전체 글 기준이라 흔들리지 않음."""
        self.shown = min(n, len(self.message))
        if not self.hist:
            self.fill_text()

    def type_next(self, msg):
        if self.message is not msg or self.shown >= len(msg):   # 다른 말로 바뀌었거나 다 나옴
            return
        self.reveal(self.shown + 1)
        self.root.after(TYPE_MS, self.type_next, msg)

    def toggle(self, open_=None):
        self.open = (not self.open) if open_ is None else open_
        self.render()
        if self.open:
            self.entry.focus_force()
        elif not self.busy:
            self.face("normal")

    # ── 마우스: 클릭 = 말풍선, 드래그 = 옮기기/던지기 ──
    def press(self, e):
        self.start = (e.x_root, e.y_root, self.wx, self.wy)
        self.moved = False
        self.samples = [(time.time(), e.x_root, e.y_root)]

    def drag(self, e):
        sx, sy, wx, wy = self.start
        if abs(e.x_root - sx) + abs(e.y_root - sy) > 4:
            self.moved = True
            self.dragging, self.falling, self.perch = True, False, None
        self.samples = (self.samples + [(time.time(), e.x_root, e.y_root)])[-8:]
        self.move(wx + e.x_root - sx, wy + e.y_root - sy)

    def release(self, e):
        if self.dbl:                 # 더블클릭의 두 번째 떼기는 무시
            self.dbl = False
        elif not self.moved:         # 더블클릭인지 잠깐 기다렸다가 열고 닫기
            self.click_job = self.root.after(250, self.click)
        else:                        # 놓으면 떨어짐, 휙 던졌으면 날아감
            self.dragging = False
            recent = [s for s in self.samples if s[0] > time.time() - 0.1] or self.samples[-1:]
            t0, x0, y0 = recent[0]
            dt = max(time.time() - t0, 0.016)
            self.vx = max(-3000, min(3000, (e.x_root - x0) / dt))
            self.vy = max(-3000, min(3000, (e.y_root - y0) / dt))
            if self.gravity.get():
                self.falling = True
                if math.hypot(self.vx, self.vy) > 1500:
                    self.brain.thrown()
            else:
                self.vx = self.vy = 0.0
                self.save_pos()

    def click(self):
        self.click_job = None
        self.toggle()

    def show(self, text, typed=False):
        self.hist = False
        self.message, self.spans = md_parse(text.strip())
        self.shown = 0 if typed else len(self.message)
        self.render()
        if typed:
            self.av_send(talk=len(self.message))
        if typed:
            self.type_next(self.message)

    def new_chat(self):
        self.brain.new_chat()
        self.open = True
        self.show("새 대화 시작~ 아까 얘기는 잊어버렸어.", typed=True)

    def fill_chars(self):
        self.char_menu.delete(0, "end")
        self.char_var.set(self.brain.char)
        for cid, name in core.char_list():
            self.char_menu.add_radiobutton(label=name, value=cid, variable=self.char_var,
                                           command=lambda: self.brain.set_char(self.char_var.get()))

    def fill_rooms(self, m):
        m.delete(0, "end")
        now = self.brain.sessions.get(sys.platform)
        for r in self.brain.room_list():
            m.add_command(label=("● " if r["id"] == now else "") + f'{r["t"][5:]}  {r["title"]}',
                          command=lambda r=r: self.open_room(r))
        if m.index("end") is None:
            m.add_command(label="(아직 없어)", state="disabled")

    def rename_room(self):
        sid = self.brain.sessions.get(sys.platform)
        if not sid:
            return self.show("아직 말 한마디도 안 한 방인데 이름부터 지으려고?")
        old = next((r["title"] for r in self.brain.room_list() if r["id"] == sid), "")
        title = simpledialog.askstring("대화방 이름", "이 대화방 이름:", initialvalue=old, parent=self.root)
        if title and title.strip():
            self.brain.rename_room(sid, title)
            self.show(f"\"{title.strip()[:40]}\"(으)로 이름 붙였어~", typed=True)

    def open_room(self, r):
        if self.busy:
            return self.show("답 쓰는 중이라 못 옮겨~ 끝나고 다시 눌러 줘.")
        self.brain.open_room(r["id"])
        self.open = True
        self.show(f"{r['t'][5:]} 대화로 돌아왔어~ \"{r['title']}\" 하던 거 이어서 하자.", typed=True)

    def typing(self, n=0):
        if self.busy:
            dots = "·" * (n % 3 + 1)
            self.show(f"{self.brain.status} {dots}" if self.brain.status else dots)
            self.root.after(400, self.typing, n + 1)

    def fit_input(self):
        """입력한 글이 길어지면 입력창을 아래로 늘림 (최대 IN_MAX 줄, 넘으면 스크롤)."""
        n = self.entry.count("1.0", "end-1c", "displaylines")
        n = (n[0] if isinstance(n, tuple) else n or 0) + 1
        n = max(1, min(n, IN_MAX))
        if n != self.in_lines:
            self.in_lines = n
            self.render()
            self.entry.see("insert")

    def send(self, _=None):
        msg = self.entry.get("1.0", "end-1c").strip()
        if msg or self.attach:   # 답 쓰는 중이어도 보내면 끼어들기
            self.entry.delete("1.0", "end")
            files, self.attach = self.attach, []
            self.in_lines = 1
            self.brain.send(msg, files)
            self.render()
        return "break"


if __name__ == "__main__":
    if sys.stderr is None:   # pythonw라 콘솔이 없음 → 오류는 error.log에 남김 (갑자기 꺼지면 여기 봐)
        sys.stderr = open(os.path.join(HERE, "error.log"), "a", encoding="utf-8", buffering=1)
        sys.stderr.write(f"\n--- 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    # 이미 켜져 있으면 또 켜지 않음 (시작 프로그램 + "위젯 켜기" 버튼이 겹쳐도 하나만)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex = _k32.CreateMutexW(None, False, "Local\\DotCompanionWidget")
    if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
        sys.exit()
    # 위젯이 꺼져 있는 동안 dangam_keeper가 두뇌만 켜 두는데, 위젯이 켜지면 두뇌가 스스로 꺼짐. 포트가 비길 기다렸다 이어받음
    import socket
    for _ in range(40):
        _s = socket.socket()
        _s.settimeout(0.3)
        try:
            _s.connect(("127.0.0.1", core.DETAIL_PORT))
        except OSError:
            break
        finally:
            _s.close()
        time.sleep(0.25)
    try:
        register_protocol()   # 자세히 창 "위젯 켜기" 버튼 (dotcompanion://). 위젯 위치가 바뀌어도 늘 맞게 다시 적음
    except OSError:
        pass
    app = Dangam()
    try:
        app.root.mainloop()
    finally:
        app.av_send(quit=True)
        cx, feet = app.char_pos()
        app.brain.body_state.update(pos=[round(cx), round(feet)], gravity=app.gravity.get(), play=app.play.get())
        app.brain.save_state()
