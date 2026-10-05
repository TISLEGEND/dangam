"""새 캐릭터 만들기: 자작 캐릭터(그림 올리기)는 여기서 바로 만들고, 유명 캐릭터/설명만 있는 캐릭터는 요청서를 써 두고 AI가 이어서 만듦.

사용:
  python newchar.py sheet <id>    characters/<id>_sheet_src.png (3x3 시트, 초록 #00FF00 배경) → characters/<id>/faces 만들기
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHAR_DIR = os.path.join(HERE, "characters")
FACES = ["normal", "happy", "smug", "surprised", "sad", "sleepy", "curious", "coding", "angry"]   # 3x3 시트 순서이기도 함
FACE_LABEL = {"normal": "평상시", "happy": "기분 좋음", "smug": "우쭐함", "surprised": "놀람", "sad": "슬픔",
              "sleepy": "졸림", "curious": "궁금함", "coding": "작업 중", "angry": "삐짐·화남"}


def make_id(name):
    """영문 소문자/숫자 폴더 이름. 한글 이름이면 해시로. 이미 있으면 숫자 붙임"""
    base = re.sub(r"[^a-z0-9]+", "", name.lower())[:16] or "c" + hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
    if base in ("dangam", "new", "_new"):
        base += "x"
    cid, n = base, 1
    while os.path.exists(os.path.join(CHAR_DIR, cid)) or os.path.exists(os.path.join(CHAR_DIR, "_new", cid)):
        n += 1
        cid = f"{base}{n}"
    return cid


def persona_text(name, desc="", tone="", source=""):
    head = f'너는 "{name}"이다.'
    if source:
        head += f" {source}에 나오는 캐릭터/인물이다."
    parts = [head]
    if desc:
        parts.append(f"설정: {desc}")
    parts.append("지금은 {닉네임}의 PC 바탕화면 위젯에 사는 작은 몸으로 와 있고, 자신이 LLM으로 돌아가는 걸 숨기지 않지만 굳이 꺼내지도 않는다.")
    parts.append(f"말투: {tone}" if tone else "말투: 설정에 어울리는 자연스러운 말투로, 짧게 한두 문장씩 채팅하듯 말한다.")
    parts.append("호칭: 자기와 상대를 부르는 말은 설정에 맞게 정하되, 상대 이름을 너무 자주 부르지 않는다.")
    parts.append("규칙: 원작이나 설정 중 확실히 모르는 건 지어내지 말고 얼버무리거나 모른다고 한다. 상대가 힘들어 보이면 장난을 접고 진지하게 들어 준다.")
    return "\n\n".join(parts) + "\n"


def default_lines():
    """캐릭터 말투를 모르는 상태에서 쓰는 무난한 정해진 대사 (AI가 만들 때는 이 파일을 캐릭터에 맞게 다시 씀)"""
    return {
        "GREETS": [[0, 6, "sleepy", "늦은 시간이네. 아직 안 잤어?"], [6, 12, "happy", "좋은 아침이야."],
                   [12, 18, "curious", "왔어? 오늘은 뭐 하고 있었어?"], [18, 24, "happy", "저녁이네. 오늘도 수고했어."]],
        "LINES": [[6, 11, "curious", "아침은 먹었어?"], [11, 14, "curious", "점심 때네. 뭐 먹을 거야?"],
                  [14, 18, "normal", "오후도 천천히 가 보자."], [18, 24, "normal", "오늘은 어땠어?"], [0, 6, "sleepy", "슬슬 쉬어야 하지 않을까?"]],
        "PATS": [["happy", "헤헤, 간지러워."], ["surprised", "어, 갑자기?"], ["smug", "계속해도 돼."]],
        "WELCOMES": [["happy", "{d} 만이네. 기다렸어."], ["curious", "어서 와. {d} 동안 무슨 일 있었어?"]],
        "THROWN": [["surprised", "으앗, 던져졌다?!"], ["angry", "이건 좀 너무하잖아."]],
    }


def _save(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_basics(cid, name, tagline, persona, hidden=False):
    """name/tagline/persona/lines. hidden이면 그림이 생길 때까지 목록에 안 뜨게 persona.md.wait로 둠"""
    d = os.path.join(CHAR_DIR, cid)
    _save(os.path.join(d, "name.txt"), name)
    _save(os.path.join(d, "tagline.txt"), tagline)
    _save(os.path.join(d, "persona.md" + (".wait" if hidden else "")), persona)
    if not os.path.isfile(os.path.join(d, "lines.json")):
        _save(os.path.join(d, "lines.json"), json.dumps(default_lines(), ensure_ascii=False, indent=1))


def _square(img, size):
    from PIL import Image
    w, h = img.size
    s = max(w, h)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sq.paste(img, ((s - w) // 2, (s - h) // 2))
    sq = sq.resize((size, size), Image.LANCZOS)
    a = sq.getchannel("A").point(lambda v: 255 if v >= 128 else 0)   # 위젯은 #ff00ff를 투명색으로 써서 반투명 가장자리가 번진다
    sq.putalpha(a)
    return sq


def _cut_background(img):
    """투명 배경이 없는 그림이면 네 모서리 색과 비슷한 바깥 배경을 투명하게 (가장자리에서 번져 들어가는 방식)"""
    import numpy as np
    from PIL import Image
    a = np.array(img)
    if a[..., 3].min() < 250:   # 이미 투명한 곳이 있음
        return img
    h, w = a.shape[:2]
    corners = np.array([a[0, 0, :3], a[0, w - 1, :3], a[h - 1, 0, :3], a[h - 1, w - 1, :3]], dtype=np.int32)
    bg = np.median(corners, axis=0)
    if np.abs(corners - bg).max() > 24:   # 모서리 색이 제각각이면 배경이 아님
        return img
    near = (np.abs(a[..., :3].astype(np.int32) - bg).max(axis=2) <= 28).astype(np.uint8)
    import cv2
    n, lab = cv2.connectedComponents(near, connectivity=4)
    edge_labels = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    edge_labels.discard(0)
    out = a.copy()
    out[np.isin(lab, list(edge_labels)) & (near > 0)] = 0
    return Image.fromarray(out, "RGBA")


def faces_from_images(cid, files):
    """files: {표정: 이미지 경로}. 160/400px 정사각 PNG로 저장. normal이 없으면 첫 그림으로"""
    from PIL import Image
    files = {k: v for k, v in files.items() if k in FACES and v and os.path.isfile(v)}
    if not files:
        raise ValueError("그림이 하나도 없어")
    files.setdefault("normal", next(iter(files.values())))
    out = os.path.join(CHAR_DIR, cid, "faces")
    os.makedirs(os.path.join(out, "big"), exist_ok=True)
    for face, path in files.items():
        im = _cut_background(Image.open(path).convert("RGBA"))
        box = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        if box:
            im = im.crop(box)
        for size, dest in ((400, os.path.join(out, "big", face + ".png")), (160, os.path.join(out, face + ".png"))):
            _square(im, size).save(dest)
    return sorted(files)


def faces_from_sheet(cid):
    """characters/<cid>_sheet_src.png: 3x3 시트(초록 배경) → 표정 9개. 끝나면 숨겨 둔 persona.md.wait를 풀어 목록에 띄움"""
    import cv2
    import numpy as np
    from PIL import Image
    src = os.path.join(CHAR_DIR, cid + "_sheet_src.png")
    out = os.path.join(CHAR_DIR, cid, "faces")
    im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    green = g - np.maximum(r, b)
    alpha = np.clip(1.0 - (green - 30) / 90.0, 0, 1)
    alpha[green < 30] = 1.0
    hard = (alpha > 0.5).astype(np.uint8)
    hard[green > 12] = 0
    hard = cv2.erode(hard, np.ones((3, 3), np.uint8), iterations=1)
    edge = cv2.dilate(hard, np.ones((3, 3), np.uint8), iterations=3) - hard
    rgb = np.dstack([r, np.minimum(g, (r + b) / 2), b]).astype(np.uint8)
    inner = cv2.erode(hard, np.ones((3, 3), np.uint8), iterations=3)
    w = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 3) + 1e-4
    fill = (cv2.GaussianBlur((rgb * inner[..., None]).astype(np.float32), (0, 0), 3) / w[..., None]).astype(np.uint8)
    rgb = np.where((edge > 0)[..., None], fill, rgb)
    a_soft = cv2.GaussianBlur(hard.astype(np.float32), (0, 0), 0.8)
    sheet = Image.fromarray(np.dstack([rgb, np.clip(a_soft * 255, 0, 255).astype(np.uint8)]), "RGBA")
    W, H = sheet.size
    cw, ch = W / 3, H / 3
    os.makedirs(os.path.join(out, "big"), exist_ok=True)
    os.makedirs(os.path.join(out, "src"), exist_ok=True)
    for i, name in enumerate(FACES):
        cx, cy = i % 3, i // 3
        arr = np.array(sheet.crop((int(cx * cw), int(cy * ch), int((cx + 1) * cw), int((cy + 1) * ch))))
        mask = (arr[..., 3] > 40).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(mask, np.ones((5, 5), np.uint8)))
        areas = stats[:, cv2.CC_STAT_AREA]
        keep = [k for k in range(1, n) if areas[k] > 0.02 * areas[1:].max()
                and not (stats[k, cv2.CC_STAT_TOP] + stats[k, cv2.CC_STAT_HEIGHT] >= ch - 3 and stats[k, cv2.CC_STAT_HEIGHT] < 30)]
        arr[~np.isin(lab, keep)] = 0
        cell = Image.fromarray(arr, "RGBA")
        cell = cell.crop(cell.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox())
        sq = _square(cell, max(cell.size))
        sq.save(os.path.join(out, "src", name + ".png"))
        for size, dest in ((400, os.path.join(out, "big", name + ".png")), (160, os.path.join(out, name + ".png"))):
            _square(cell, size).save(dest)
        print(name, cell.size)
    wait = os.path.join(CHAR_DIR, cid, "persona.md.wait")
    if os.path.isfile(wait):
        os.replace(wait, os.path.join(CHAR_DIR, cid, "persona.md"))
        print("persona.md 복원: 캐릭터 목록에 나타남")


def create_own(name, desc, tone, files, tagline=""):
    """자작 캐릭터: 올린 그림으로 바로 만들기. 돌려주는 건 캐릭터 id"""
    cid = make_id(name)
    faces_from_images(cid, files)
    write_basics(cid, name, tagline or (desc.split("\n")[0][:30] if desc else "새로 온 캐릭터"), persona_text(name, desc, tone))
    return cid


def request_ai(kind, name, source="", desc="", tone=""):
    """유명 캐릭터/설명만 있는 캐릭터: 요청서를 남기고, 그림 시트가 나올 때까지 목록에 안 뜨게 숨겨 둠. (id, AI에게 보낼 말) 돌려줌"""
    cid = make_id(name)
    write_basics(cid, name, "새로 온 캐릭터", persona_text(name, desc, tone, source), hidden=True)
    req = {"id": cid, "kind": kind, "name": name, "source": source, "desc": desc, "tone": tone}
    _save(os.path.join(CHAR_DIR, "_new", cid, "request.json"), json.dumps(req, ensure_ascii=False, indent=1))
    what = f"{source}의 \"{name}\"" if kind == "known" else f"\"{name}\""
    msg = (f"새 캐릭터 만들기 부탁이야. {what} 캐릭터를 만들어 줘. 요청서는 characters/_new/{cid}/request.json, "
           f"만드는 순서는 NEWCHAR.md에 있으니까 그대로 따라 해 줘. 폴더 이름(id)은 {cid}야. 끝나면 어떻게 고르는지 알려 줘.")
    return cid, msg


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "sheet":
        faces_from_sheet(sys.argv[2])
    else:
        print(__doc__)
