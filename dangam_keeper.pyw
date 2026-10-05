"""위젯이 꺼져 있을 때 두뇌만 대신 켜 두는 지킴이 (윈도우). 폰 앱/자세히 창이 위젯 없이도 열리게 함.
위젯(dangam.pyw)이 켜져 있으면 가만히 있고, 없으면 dangam_core.py(두뇌만 켜기)를 띄움. 위젯이 켜지면 두뇌가 스스로 꺼짐."""
import ctypes, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenMutexW.restype = ctypes.c_void_p
k32.CloseHandle.argtypes = [ctypes.c_void_p]


def widget_running():
    h = k32.OpenMutexW(0x100000, False, "Local\\DotCompanionWidget")   # SYNCHRONIZE
    if h:
        k32.CloseHandle(h)
    return bool(h)


if __name__ == "__main__":
    if sys.stderr is None:
        sys.stderr = open(os.path.join(HERE, "error.log"), "a", encoding="utf-8", buffering=1)
    _m = k32.CreateMutexW(None, False, "Local\\DangamKeeper")
    if ctypes.get_last_error() == 183:   # 이미 지킴이가 있음
        sys.exit()
    brain = None
    while True:
        time.sleep(5)
        if widget_running():
            brain = None   # 위젯이 켜지면 두뇌는 스스로 꺼짐
            continue
        if brain is None or brain.poll() is not None:
            time.sleep(3)   # 위젯이 재시작 중일 수 있어서 한 번 더 확인
            if widget_running():
                continue
            brain = subprocess.Popen([PYW, os.path.join(HERE, "dangam_core.py")], cwd=HERE,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
