"""단감 위젯이 쓰는 윈도우 기능 모음 (ctypes만 씀, 설치할 것 없음)."""
import ctypes, os, threading
from ctypes import wintypes as W

u32, k32, sh32 = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.windll.shell32
psapi, dwm = ctypes.windll.psapi, ctypes.windll.dwmapi

k32.OpenProcess.restype = ctypes.c_void_p
k32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, W.DWORD, ctypes.c_wchar_p, ctypes.POINTER(W.DWORD)]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
u32.GetForegroundWindow.restype = W.HWND
for _f in ("IsWindow", "IsWindowVisible", "IsIconic", "GetWindowTextLengthW"):   # 창 핸들이 커도 안 넘치게
    getattr(u32, _f).argtypes = [W.HWND]
u32.GetWindowTextW.argtypes = [W.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetWindowLongW.argtypes = [W.HWND, ctypes.c_int]
u32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
u32.PostMessageW.argtypes = [W.HWND, ctypes.c_uint, W.WPARAM, W.LPARAM]
dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]
u32.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
u32.SetWindowLongPtrW.restype = ctypes.c_void_p
u32.SetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int, ctypes.c_void_p]
u32.CallWindowProcW.restype = ctypes.c_ssize_t
u32.CallWindowProcW.argtypes = [ctypes.c_void_p, W.HWND, ctypes.c_uint, W.WPARAM, W.LPARAM]
sh32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
sh32.DragFinish.argtypes = [ctypes.c_void_p]
sh32.DragAcceptFiles.argtypes = [W.HWND, W.BOOL]

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, W.HWND, ctypes.c_uint, W.WPARAM, W.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


def exe_path(pid):
    """프로세스 실행 파일 전체 경로 (못 읽으면 "")."""
    h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf, n = ctypes.create_unicode_buffer(1024), W.DWORD(1024)
    ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k32.CloseHandle(h)
    return buf.value if ok else ""


def window_pid(hwnd):
    pid = W.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def idle_seconds():
    """마지막 키보드/마우스 입력 뒤로 몇 초 지났는지."""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO))
    u32.GetLastInputInfo(ctypes.byref(li))
    return ((k32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000


def active_window():
    """지금 맨 앞에 있는 창의 (제목, 프로그램 파일 이름)."""
    hwnd = u32.GetForegroundWindow()
    title = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(hwnd, title, 512)
    return title.value, os.path.basename(exe_path(window_pid(hwnd)))


def running_exes():
    """지금 실행 중인 프로그램 경로들 (소문자)."""
    pids = (W.DWORD * 8192)()
    got = W.DWORD()
    psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(got))
    return {p.lower() for p in map(exe_path, pids[:got.value // 4]) if p}


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]


u32.MonitorFromPoint.restype = ctypes.c_void_p
u32.MonitorFromPoint.argtypes = [W.POINT, W.DWORD]
u32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]


def work_area(x, y):
    """(x, y)가 있는 모니터에서 작업표시줄 뺀 영역 (left, top, right, bottom)."""
    mi = MONITORINFO(ctypes.sizeof(MONITORINFO))
    u32.GetMonitorInfoW(u32.MonitorFromPoint(W.POINT(int(x), int(y)), 2), ctypes.byref(mi))   # 가장 가까운 모니터
    r = mi.rcWork
    return r.left, r.top, r.right, r.bottom


def floor_area(x, y):
    """work_area와 같은데, 맨 앞 창이 전체 화면(게임)이면 작업표시줄이 없는 셈 치고 모니터 맨 아래까지."""
    wa = work_area(x, y)
    if not fullscreen():
        return wa
    mi = MONITORINFO(ctypes.sizeof(MONITORINFO))
    u32.GetMonitorInfoW(u32.MonitorFromPoint(W.POINT(int(x), int(y)), 2), ctypes.byref(mi))
    return wa[0], wa[1], wa[2], mi.rcMonitor.bottom


def _cloaked(hwnd):
    v = ctypes.c_int(0)
    dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(v), 4)   # DWMWA_CLOAKED (가상 데스크톱/숨은 앱 창)
    return v.value != 0


def window_rect(hwnd):
    """보이는 창이면 (left, top, right, bottom), 최소화/숨김/닫힘이면 None."""
    if not u32.IsWindow(hwnd) or not u32.IsWindowVisible(hwnd) or u32.IsIconic(hwnd) or _cloaked(hwnd):
        return None
    r = W.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def top_windows(skip_pid):
    """앉을 수 있는 창들, 맨 위 창부터 순서대로 [(hwnd, rect)]."""
    out = []

    @WNDENUMPROC
    def cb(h, _):
        ex = u32.GetWindowLongW(h, -20)                          # GWL_EXSTYLE
        if ex & 0xA0:                                            # 도구 창/클릭 통과 창 (NVIDIA 오버레이 같은 것)
            return True
        if u32.GetWindowTextLengthW(h) and window_pid(h) != skip_pid:
            r = window_rect(h)
            if r and r[2] - r[0] > 80 and r[3] - r[1] > 60:
                out.append((h, r))
        return True
    u32.EnumWindows(cb, 0)
    return out


def hotkey(mods, vk, on_press, on_fail):
    """전역 단축키. 누르면 on_press() (단축키 스레드에서 불림)."""
    def run():
        if not u32.RegisterHotKey(None, 1, mods | 0x4000, vk):   # MOD_NOREPEAT
            on_fail()
            return
        msg = W.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:                            # WM_HOTKEY
                on_press()
    threading.Thread(target=run, daemon=True).start()


def accept_files(hwnd, on_drop):
    """이 창에 파일을 끌어다 놓으면 on_drop([경로...]). 돌려주는 값은 꼭 붙잡아 둘 것 (GC되면 튕김)."""
    old = None

    @WNDPROC
    def proc(h, msg, wp, lp):
        if msg == 0x0233:                                        # WM_DROPFILES
            n = sh32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
            files = []
            for i in range(n):
                buf = ctypes.create_unicode_buffer(1024)
                sh32.DragQueryFileW(wp, i, buf, 1024)
                files.append(buf.value)
            sh32.DragFinish(wp)
            on_drop(files)
            return 0
        return u32.CallWindowProcW(old, h, msg, wp, lp)

    sh32.DragAcceptFiles(hwnd, True)
    old = u32.SetWindowLongPtrW(hwnd, -4, ctypes.cast(proc, ctypes.c_void_p))   # GWLP_WNDPROC
    return proc


def beep():
    u32.MessageBeep(0x40)   # MB_ICONASTERISK


class _PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor():
    p = _PT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def set_cursor(x, y):
    u32.SetCursorPos(int(x), int(y))


u32.IsZoomed.argtypes = [W.HWND]
u32.GetClassNameW.argtypes = [W.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]


def movable(hwnd):
    """장난으로 흔들어도 되는 창인지 (최대화 아님)."""
    return window_rect(hwnd) is not None and not u32.IsZoomed(hwnd)


def move_window(hwnd, x, y):
    u32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, 0x0001 | 0x0004 | 0x0010)   # NOSIZE | NOZORDER | NOACTIVATE


def keep_on_top(hwnd):
    """작업표시줄이 클릭으로 위로 올라와서 창을 덮었을 때 다시 맨 위로 (활성화는 안 함)."""
    u32.GetParent.argtypes, u32.GetParent.restype = [W.HWND], W.HWND
    top = u32.GetParent(hwnd) or hwnd
    u32.SetWindowPos(top, W.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # HWND_TOPMOST, NOSIZE | NOMOVE | NOACTIVATE


OWN_PIDS = {os.getpid()}      # 위젯 자신(3D 몸 창 포함). 이 창이 맨 앞이면 직전 판정을 그대로 씀
_last_fs = False


def fullscreen():
    """맨 앞 창이 모니터 전체를 덮고 있는지 (게임, 영상 전체 화면). 위젯을 클릭해 내가 맨 앞이 돼도 게임 판정은 유지."""
    global _last_fs
    hwnd = u32.GetForegroundWindow()
    if window_pid(hwnd) in OWN_PIDS:
        return _last_fs
    _last_fs = _fullscreen(hwnd)
    return _last_fs


def _fullscreen(hwnd):
    r = window_rect(hwnd)
    cls = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(hwnd, cls, 64)
    if not r or cls.value in ("Progman", "WorkerW"):             # 바탕화면
        return False
    mi = MONITORINFO(ctypes.sizeof(MONITORINFO))
    u32.GetMonitorInfoW(u32.MonitorFromPoint(W.POINT((r[0] + r[2]) // 2, (r[1] + r[3]) // 2), 2), ctypes.byref(mi))
    m = mi.rcMonitor
    return r[0] <= m.left and r[1] <= m.top and r[2] >= m.right and r[3] >= m.bottom


def foreground(skip_pid):
    """맨 앞 창 핸들 (바탕화면이나 skip_pid 프로세스 창이면 None)."""
    hwnd = u32.GetForegroundWindow()
    cls = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(hwnd, cls, 64)
    if not hwnd or cls.value in ("Progman", "WorkerW", "Shell_TrayWnd") or window_pid(hwnd) == skip_pid:
        return None
    return hwnd
