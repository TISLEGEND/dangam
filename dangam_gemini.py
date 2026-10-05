"""Gemini adapter for Dangam: plain REST call with an AI Studio API key (no CLI needed, chat only)."""

import json
import os
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def run(prompt, *, model="", key=""):
    """Return (reply, error) from one Gemini turn."""
    key = key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return "", "Gemini API 키가 없어. 자세히 창 > 대화 엔진에서 키를 넣어 줘. (aistudio.google.com/apikey 에서 무료로 받아)"
    req = urllib.request.Request(
        API.format(model or "gemini-3.8-flash"),
        data=json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
    except urllib.error.HTTPError as ex:
        try:
            msg = json.load(ex).get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        return "", f"HTTP {ex.code} {msg}"[:300]
    except (urllib.error.URLError, OSError, ValueError) as ex:
        return "", str(ex)[:300]
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        return "", str((data.get("promptFeedback") or {}).get("blockReason") or "응답이 비었어")
    return text, ""
