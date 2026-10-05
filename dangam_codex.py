"""Codex CLI adapter for Dangam. Claude remains the primary backend."""

import glob
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time


def codex_path():
    found = shutil.which("codex")
    if found:
        return found
    if sys.platform == "win32":
        paths = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                       "OpenAI", "Codex", "bin", "*", "codex.exe"))
        if paths:
            return max(paths, key=os.path.getmtime)
    return None


def read_usage(timeout=20):
    """Read this ChatGPT account's Codex quota through the local Codex app-server."""
    exe = codex_path()
    if not exe:
        return None
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    p = subprocess.Popen([exe, "app-server", "--stdio"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         encoding="utf-8", errors="replace", bufsize=1, **kwargs)
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in p.stdout], daemon=True).start()
    def request(request_id, method, params):
        p.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        p.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = json.loads(lines.get(timeout=max(0.1, deadline - time.monotonic())))
            if response.get("id") == request_id:
                return response.get("result") if not response.get("error") else None
        return None
    try:
        if request(1, "initialize", {"clientInfo": {"name": "dot-companion", "version": "1.0"}}) is None:
            return None
        p.stdin.write('{"method":"initialized"}\n')
        p.stdin.flush()
        result = request(2, "account/rateLimits/read", {"excludeResetCreditDetails": True})
        if not isinstance(result, dict):
            return None
        limits = result.get("rateLimitsByLimitId") or {}
        bucket = limits.get("codex") or result.get("rateLimits") or {}
        snapshot = {"checked": time.strftime("%Y-%m-%d %H:%M"),
                    "available": result.get("ordinaryUsageAllowed")}
        for source, target in (("primary", "five_hour"), ("secondary", "seven_day")):
            window = bucket.get(source)
            if isinstance(window, dict) and isinstance(window.get("usedPercent"), (int, float)):
                snapshot[target] = {"utilization": max(0, min(1, window["usedPercent"] / 100)),
                                    "resetsAt": window.get("resetsAt"),
                                    "windowDurationMins": window.get("windowDurationMins")}
        return snapshot if "five_hour" in snapshot or "seven_day" in snapshot else None
    except (OSError, ValueError, queue.Empty, BrokenPipeError):
        return None
    finally:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()


def run(prompt, *, session=None, images=(), read_only=False, model="", on_process=None, on_status=None):
    """Return (reply, session_id, error) from a noninteractive Codex turn."""
    exe = codex_path()
    if not exe:
        return "", None, "Codex CLI를 찾지 못했어."
    cmd = [exe, "exec", "--json", "--skip-git-repo-check"]
    if model:
        cmd += ["-m", model]
    if read_only:
        cmd += ["-s", "read-only", "--ephemeral"]
    else:
        # Dangam's main Claude conversation already uses bypassPermissions.
        cmd += ["--dangerously-bypass-approvals-and-sandbox"]
    if not session:
        cmd += ["-C", os.path.expanduser("~")]
    for path in images:
        if os.path.isfile(path):
            cmd += ["-i", path]
    cmd += ["resume", session, "-"] if session else ["-"]
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {"start_new_session": True}
    p = subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         encoding="utf-8", errors="replace", bufsize=1, **kwargs)
    if on_process:
        on_process(p)
    errors = []
    def drain_errors():
        for line in p.stderr:
            if "ERROR" in line or "Error:" in line:
                errors.append(line.strip()[:300])
    stderr_thread = threading.Thread(target=drain_errors, daemon=True)
    stderr_thread.start()
    timed_out = threading.Event()
    def stop_slow_turn():
        if p.poll() is not None:
            return
        timed_out.set()
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           capture_output=True, **kwargs)
        else:
            p.kill()
    timer = threading.Timer(600, stop_slow_turn)
    timer.start()
    reply, thread_id, failure = "", session, ""
    try:
        p.stdin.write(prompt)
        p.stdin.close()
        for line in p.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            kind = event.get("type")
            if kind == "thread.started":
                thread_id = event.get("thread_id") or thread_id
            elif kind == "item.completed":
                item = event.get("item") or {}
                if item.get("type") == "agent_message":
                    reply = item.get("text") or reply
            elif kind == "item.started" and on_status:
                item = event.get("item") or {}
                label = {"command_execution": "컴퓨터에서 작업 중", "web_search": "웹 검색 중",
                         "mcp_tool_call": "도구 사용 중"}.get(item.get("type"))
                if label:
                    on_status(label)
            elif kind in ("turn.failed", "error"):
                failure = str(event.get("error") or event.get("message") or kind)[:500]
    finally:
        timer.cancel()
        p.wait()
        stderr_thread.join(timeout=1)
    if timed_out.is_set():
        failure = "GPT 응답이 10분 넘게 걸려 중단했어."
    if p.returncode or not reply:
        failure = failure or (errors[-1] if errors else f"Codex 종료 코드 {p.returncode}")
    return reply, thread_id, failure
