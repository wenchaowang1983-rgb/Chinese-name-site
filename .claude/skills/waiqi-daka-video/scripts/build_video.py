"""外企也打卡 · 竖屏短视频生成器。用法: python3 build_video.py config.json
读取 config.json（见 examples/boulder.json），输出 1080x1920 成片 + 封面图。版式：视频窗口占竖屏 54%，字幕只出中文。"""
import os, sys, json, subprocess, re, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = f"{SKILL}/assets"
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
WORK = os.path.abspath(CFG["work_dir"]); os.makedirs(f"{WORK}/tts", exist_ok=True)
SRC = os.path.abspath(CFG["source_video"])
OUT = f"{WORK}/out"; os.makedirs(OUT, exist_ok=True)
FD = os.environ.get("WAIQI_FONTS") or (f"{SKILL}/fonts")
W, H = 1080, 1920
WIN_Y, WIN_H = 236, 1040          # 视频窗口：占竖屏 54%（≥一半）
FPS = 30
GREEN = (6, 73, 55)
CREAM = (246, 243, 236)
CROP_RAW = CFG.get("crop") or "null"   # 可选预裁剪：去掉原片烧录字幕/水印，如 crop=1280:590:0:0,delogo=x=18:y=16:w=260:h=46
def vf(focus=None):
    """把原片裁成窗口比例(1080x1040)再缩放；focus=水平取景中心(0左~1右)，默认 config.focus_x 或 0.5"""
    f = CFG.get("focus_x", 0.5) if focus is None else focus
    return f"{CROP_RAW},crop='min(iw,ih*{W}/{WIN_H})':ih:'(iw-ow)*{f}':0,scale={W}:{WIN_H}"

IVORY = (246, 243, 236)
INK = (15, 31, 26)
GOLD = (201, 169, 106)
_FC = {}
def serif(sz, w=900):
    k = ("s", sz, w)
    if k not in _FC:
        ft = ImageFont.truetype(f"{FD}/NotoSerifSC[wght].ttf", sz); ft.set_variation_by_axes([w]); _FC[k] = ft
    return _FC[k]
def nb(sz, w=700):
    k = ("n", sz, w)
    if k not in _FC:
        ft = ImageFont.truetype(f"{FD}/NotoSansSC[wght].ttf", sz); ft.set_variation_by_axes([w]); _FC[k] = ft
    return _FC[k]
def inter(sz, w=500):
    k = ("i", sz, w)
    if k not in _FC:
        ft = ImageFont.truetype(f"{FD}/Inter[opsz,wght].ttf", sz); ft.set_variation_by_axes([min(32, max(14, sz)), w]); _FC[k] = ft
    return _FC[k]
_LET = Image.open(f"{ASSETS}/lettering_mask.png").getchannel("A")
def lettering(width, color):
    h = int(width * _LET.height / _LET.width)
    m = _LET.resize((width, h), Image.LANCZOS)
    im = Image.new("RGBA", (width, h), tuple(color) + (255,)); im.putalpha(m); return im
def tracked(d, cx, y, text, font, fill, sp=8):
    ws = [d.textlength(c, font=font) for c in text]; total = sum(ws) + sp * (len(text) - 1); x = cx - total / 2
    for c, w in zip(text, ws):
        d.text((x, y), c, font=font, fill=fill); x += w + sp

def run(cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
def text_w(d, t, font): return d.textbbox((0, 0), t, font=font)[2]
def dur_of(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))

def wrap(d, t, font, maxw):
    zh = bool(re.search(r"[\u4e00-\u9fff]", t))
    toks = re.findall(r"[A-Za-z0-9'\-\*\.,!?…]+ ?|.", t) if zh else re.findall(r"\S+ ?", t)
    def greedy(mw):
        lines, cur = [], ""
        for tok in toks:
            if text_w(d, cur + tok, font) > mw and cur: lines.append(cur.rstrip()); cur = tok.lstrip()
            else: cur += tok
        if cur.strip(): lines.append(cur.rstrip())
        for i in range(1, len(lines)):
            while lines[i] and lines[i][0] in "，。！？、；：”）":
                lines[i - 1] += lines[i][0]; lines[i] = lines[i][1:]
        return [l for l in lines if l]
    lines = greedy(maxw); n = len(lines)
    if n == 2 and zh:
        best = None
        for k in range(1, len(toks)):
            a, b2 = "".join(toks[:k]).rstrip(), "".join(toks[k:]).strip()
            if not b2 or b2[0] in "，。！？、；：”）": continue
            wm = max(text_w(d, a, font), text_w(d, b2, font))
            if wm > maxw: continue
            score = wm - (260 if a[-1] in "，。！？、；：" else 0)
            if best is None or score < best[0]: best = (score, a, b2)
        if best: return [best[1], best[2]]
    if n >= 2:
        lo, hi = maxw * 0.5, maxw
        for _ in range(12):
            mid = (lo + hi) / 2
            if len(greedy(mid)) <= n: hi = mid
            else: lo = mid
        lines = greedy(hi)
    return lines

def ctext(d, y, t, font, fill, stroke=0, sfill="#000", cx=W // 2):
    d.text((cx - text_w(d, t, font) // 2, y), t, font=font, fill=fill, stroke_width=stroke, stroke_fill=sfill)

def logo_img(size, radius=None):
    lg = Image.open(f"{ASSETS}/logo.jpg").convert("RGB").resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius or size // 8, fill=255)
    return lg, m

# ---------------------------------------------------------------- content layout
def background(tag, footer):
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    lt = lettering(340, GREEN); im.paste(lt, ((W - lt.width) // 2, 40), lt)
    tracked(d, W // 2, 122, "打卡外企如喝茶", nb(22, 500), (110, 122, 116), sp=10)
    d.rectangle((0, 164, W, 176), fill="#e60012")
    if tag:
        tracked(d, W // 2, 188, tag, nb(30, 700), GREEN, sp=3)
    d.rectangle((0, WIN_Y - 6, W, WIN_Y + WIN_H + 6), fill=GREEN)
    if footer:
        tracked(d, W // 2, 1852, footer, nb(24, 400), (140, 146, 142), sp=3)
    return im

def sub_png(path, en, zh):
    """只出中文字幕（英文默认不显示；config 里 show_english=true 才显示）；说话人用小标签"""
    im = Image.new("RGBA", (W, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    y = 0
    mm = re.match(r"【(.+?)】(.*)", zh)
    if mm:
        label, zh = mm.group(1), mm.group(2)
        fl = nb(28, 700); tw = sum(d.textlength(c, font=fl) for c in label) + 5 * (len(label) - 1)
        d.rounded_rectangle((W // 2 - tw / 2 - 22, 0, W // 2 + tw / 2 + 22, 44), radius=22, fill=GREEN)
        tracked(d, W // 2, 3, label, fl, IVORY, sp=5); y = 64
    if en and CFG.get("show_english"):
        fe = inter(40, 500)
        for ln in wrap(d, en, fe, 960):
            ctext(d, y, ln, fe, (92, 106, 99)); y += 54
        y += 8
    fz = nb(62, 700); zh = zh.rstrip("。")
    for ln in wrap(d, zh, fz, 960):
        ctext(d, y, ln, fz, INK); y += 84
    im.save(path)

def headline_png(path, lines):
    im = Image.new("RGBA", (W, WIN_H), (0, 0, 0, 0))
    ph = 330
    g = Image.new("L", (1, ph)); g.putdata([int(225 * (i / ph) ** 1.4) for i in range(ph)])
    im.paste(Image.new("RGBA", (W, ph), GREEN + (255,)), (0, WIN_H - ph), g.resize((W, ph)))
    d = ImageDraw.Draw(im); fh = serif(72, 900); step = 92
    y = WIN_H - 36 - step * len(lines)
    for i, ln in enumerate(lines):
        ctext(d, y, ln, fh, IVORY if i == 0 or len(lines) == 1 else GOLD); y += step
    im.save(path)

def frame_png(t, path, focus=None):
    run(["ffmpeg", "-y", "-ss", str(t), "-i", SRC, "-frames:v", "1", "-vf", vf(focus), path])

def card_png(path, lines, sub=None):
    im = Image.new("RGB", (W, WIN_H), GREEN); d = ImageDraw.Draw(im)
    fh = serif(84, 900); y = (WIN_H - len(lines) * 116 - (64 if sub else 0)) // 2
    for i, (ln, col) in enumerate(lines):
        ctext(d, y, ln, fh, IVORY if i == 0 else GOLD); y += 116
    if sub:
        tracked(d, W // 2, y + 18, sub, nb(34, 400), (190, 208, 199), sp=5)
    im.save(path)

def render(name, dur, bg, window, overlays, audio_filter, audio_inputs):
    bgp = f"{OUT}/{name}_bg.png"; bg.save(bgp)
    inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", bgp]
    if window[0] == "video":
        inputs += ["-ss", f"{window[1]}", "-t", f"{dur}", "-i", SRC]
        wf = f"[1:v]{vf(window[2] if len(window) > 2 else None)},fps={FPS},setpts=PTS-STARTPTS[win]"
    else:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", window[1]]
        n = int(dur * FPS) + 2
        wf = (f"[1:v]scale={2 * W}:{2 * WIN_H},zoompan=z='min(1+0.10*on/{n},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d=1:s={W}x{WIN_H}:fps={FPS}[win]")
    k = 2
    for p in overlays:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", p[0]]
    for a in audio_inputs:
        inputs += a
    fc = [wf, f"[0:v][win]overlay=0:{WIN_Y}:shortest=1[v1]"]
    last = "v1"
    for i, (p, y, t0, t1) in enumerate(overlays):
        fc.append(f"[{last}][{k + i}:v]overlay=0:{y}:enable='between(t,{t0:.2f},{t1:.2f})'[v{i + 2}]")
        last = f"v{i + 2}"
    fc.append(audio_filter.format(n=k + len(overlays)))
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "[aout]",
         "-t", f"{dur}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", f"{OUT}/{name}.mp4"])
    return f"{OUT}/{name}.mp4"

# ---------------------------------------------------------------- cover + intro / outro animation
def ease_out_back(p):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
def ease_io(p): return 3 * p * p - 2 * p ** 3
def clamp(x): return max(0.0, min(1.0, x))

def zoom_img(im, z):
    if z == 1: return im
    w, h = int(W * z), int(H * z)
    r = im.resize((w, h), Image.BILINEAR)
    return r.crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))

def green_bg(glow=True):
    im = Image.new("RGB", (W, H), GREEN)
    if glow:
        gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((90, 520, 990, 1420), fill=70)
        gl = gl.filter(ImageFilter.GaussianBlur(200)); im.paste(Image.new("RGB", (W, H), (22, 104, 80)), (0, 0), gl)
    return im

def portrait_cover():
    """笔记侠式封面：高清人物竖屏铺满 + 底部大标题（人物名: 金句）+ 右下角小 logo。
    cover 字段：who（如 "Nike CEO"）、quote（金句，str 或 list）、frame_time、focus_x（人物水平中心，0-1）、
    focus_y（0-1，默认 0.5）、crop_bottom（裁掉原片底部比例，默认 0.17，去掉台标/字幕条）、zoom（默认 1.0，>1 更特写）、cover_source（可选，高清原片路径，默认用 source_video）、
    quote_size（默认 112）。"""
    cv = CFG["cover"]; src_path = os.path.abspath(cv.get("cover_source") or SRC)
    full = f"{OUT}/cov_hd.png"
    run(["ffmpeg", "-y", "-ss", str(cv["frame_time"]), "-i", src_path, "-frames:v", "1", full])
    fr = Image.open(full).convert("RGB")
    fr = fr.crop((0, 0, fr.width, int(fr.height * (1 - cv.get("crop_bottom", 0.17)))))   # 裁掉原片底部的电视台字幕条/台标
    z = cv.get("zoom", 1.0); ch = fr.height / z; cw = ch * W / H
    cx = cv.get("focus_x", 0.5) * fr.width; cy = cv.get("focus_y", 0.5) * fr.height
    x0 = min(max(cx - cw / 2, 0), fr.width - cw); y0 = min(max(cy - ch / 2, 0), fr.height - ch)
    im = fr.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    im = ImageEnhance.Contrast(im).enhance(1.06)
    # 底部压暗渐变，托住标题
    gh = 1000; g = Image.new("L", (1, gh)); g.putdata([int(235 * (i / gh) ** 1.6) for i in range(gh)])
    im.paste(Image.new("RGB", (W, gh), (4, 20, 15)), (0, H - gh), g.resize((W, gh)))
    d = ImageDraw.Draw(im)
    who = cv.get("who", ""); q = cv["quote"]; q = [q] if isinstance(q, str) else q
    fq = serif(cv.get("quote_size", 112), 900); fw = serif(cv.get("who_size", 84), 900)
    lines = []
    for part in q: lines += wrap(d, part, fq, 940)
    step = int(cv.get("quote_size", 112) * 1.28)
    bottom = H - 190; y = bottom - step * len(lines)
    if who:
        wy = y - 128
        d.rectangle((60, wy + 12, 76, wy + 12 + 84), fill="#e60012")
        d.text((100, wy), who + "：", font=fw, fill=GOLD, stroke_width=3, stroke_fill=(8, 26, 20))
    for ln in lines:
        d.text((60, y), ln, font=fq, fill=(255, 255, 255), stroke_width=5, stroke_fill=(8, 26, 20)); y += step
    lg, m = logo_img(124, radius=22); im.paste(lg, (W - 124 - 52, H - 124 - 56), m)
    return im

def cover_img():
    if "quote" in CFG["cover"]: return portrait_cover()
    cv = CFG["cover"]
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    for x, y, r, c in [(930, 90, 280, "#e6edea"), (90, 1650, 320, "#ebeee8")]:
        bl = Image.new("L", (W, H), 0); ImageDraw.Draw(bl).ellipse((x - r, y - r, x + r, y + r), fill=255)
        bl = bl.filter(ImageFilter.GaussianBlur(100)); im.paste(Image.new("RGB", (W, H), c), (0, 0), bl)
    d = ImageDraw.Draw(im)
    f = serif(cv.get("size", 152), 900); l1 = cv["line1"]; red = cv.get("red", "")
    w1 = sum(d.textlength(c, font=f) for c in l1); x = (W - w1) / 2
    for c in l1:
        d.text((x, 64), c, font=f, fill=("#d1101f" if c in red else INK)); x += d.textlength(c, font=f)
    ctext(d, 250, cv["line2"], f, GREEN)
    d.rectangle((0, 470, W, 498), fill="#e60012")
    full = f"{OUT}/cov_full.png"
    run(["ffmpeg", "-y", "-ss", str(cv["frame_time"]), "-i", SRC, "-frames:v", "1", "-vf", CROP_RAW, full])
    src = Image.open(full).convert("RGB"); box = cv.get("crop_box") or [0, 0, src.width, src.height]
    ph = src.crop(tuple(box)).resize((W, 840), Image.LANCZOS)
    im.paste(ph, (0, 498)); d.rectangle((0, 1338, W, 1344), fill=GREEN)
    lg, m = logo_img(96); im.paste(lg, (W // 2 - 48, 1420), m)
    lt = lettering(540, GREEN); im.paste(lt, ((W - lt.width) // 2, 1548), lt)
    tracked(d, W // 2, 1548 + lt.height + 34, "打卡外企如喝茶", nb(32, 500), (110, 122, 116), sp=16)
    return im

def brand_scene(t, t_in, show_thanks=False):
    im = green_bg(); d = ImageDraw.Draw(im)
    s = ease_out_back(clamp(t / 0.5)); size = max(8, int(300 * s))
    lg, m = logo_img(size, radius=size // 8); im.paste(lg, ((W - size) // 2, 640 - size // 2 + 120), m)
    lt = lettering(780, IVORY); p = clamp((t - 0.3) / 0.5); e = ease_io(p)
    if p > 0:
        vis = int(lt.width * e); lay = lt.copy(); mk = Image.new("L", lt.size, 0); ImageDraw.Draw(mk).rectangle((0, 0, vis, lt.height), fill=255)
        lay.putalpha(Image.fromarray((__import__("numpy").array(lt.getchannel("A")) * (__import__("numpy").array(mk) / 255.0)).astype("uint8")))
        im.paste(lay, ((W - lt.width) // 2, int(930 + (1 - e) * 24)), lay)
    pl = clamp((t - 0.8) / 0.3)
    if pl > 0:
        lw = int(260 * ease_io(pl)); d.rectangle((W // 2 - lw // 2, 930 + lt.height + 50, W // 2 + lw // 2, 930 + lt.height + 54), fill=GOLD)
    pf = clamp((t - 0.95) / 0.3)
    if pf > 0:
        txt = Image.new("RGBA", (W, 150), (0, 0, 0, 0)); td = ImageDraw.Draw(txt)
        tracked(td, W // 2, 0, "打卡外企如喝茶", nb(44, 500), IVORY + (255,), sp=16); tracked(td, W // 2, 82, "WORK  &  WONDER", inter(32, 500), GOLD + (255,), sp=10)
        txt.putalpha(txt.getchannel("A").point(lambda v: int(v * pf)))
        im.paste(txt, (0, 930 + lt.height + 84), txt)
    if show_thanks:
        pt = clamp((t - 0.7) / 0.3)
        if pt > 0:
            lay = Image.new("RGBA", (W, 140), (0, 0, 0, 0)); ctext(ImageDraw.Draw(lay), 0, CFG.get("outro", {}).get("thanks_label", "感谢收看"), serif(96, 900), IVORY + (255,))
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v * pt))); im.paste(lay, (0, 1500), lay)
    return im

def pipe_video(frames, path, audio, dur):
    p = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          *audio[0], "-filter_complex", audio[1], "-map", "0:v", "-map", "[aout]", "-t", f"{dur}",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", path],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for fr in frames: p.stdin.write(fr.tobytes())
    p.stdin.close(); err = p.stderr.read(); p.wait()
    if p.returncode: raise RuntimeError(err.decode()[-800:])

def make_intro(path, cover, hook=False):
    D = 2.4; skip = 0.6 if hook else 0; n = int((D - skip) * FPS); frames = []
    pre = Image.new("RGB", (W, H), CREAM) if hook else None
    for i in range(n):
        t = i / FPS + skip
        if t < 0.6: fr = zoom_img(cover, 1 + 0.015 * t / 0.6)
        else:
            sc = brand_scene(t - 0.6, 0)
            fr = Image.blend(pre if hook else zoom_img(cover, 1.015), sc, ease_io(clamp((t - 0.6) / 0.3))) if t < 0.9 else sc
            if t > 2.2: fr = Image.blend(fr, Image.new("RGB", (W, H), CREAM), clamp((t - 2.2) / 0.2))
        frames.append(fr)
    sting = ["-f", "lavfi", "-t", "0.6", "-i", "anoisesrc=d=0.6:c=pink:a=0.6",
             "-f", "lavfi", "-t", "0.8", "-i", "aevalsrc='0.9*sin(2*PI*70*t)*exp(-6*t)':s=44100:d=0.8",
             "-f", "lavfi", "-t", "1.2", "-i", "aevalsrc='0.30*(sin(2*PI*784*t)+0.45*sin(2*PI*1568*t))*exp(-3.5*t)':s=44100:d=1.2",
             "-f", "lavfi", "-t", "1.2", "-i", "aevalsrc='0.30*(sin(2*PI*1047*t)+0.45*sin(2*PI*2094*t))*exp(-3.5*t)':s=44100:d=1.2"]
    fc = ("[1:a]highpass=f=500,lowpass=f=6000,afade=t=in:d=0.35,afade=t=out:st=0.4:d=0.2,adelay=330|330[w];"
          "[2:a]adelay=700|700[h];[3:a]adelay=950|950[c1];[4:a]adelay=1130|1130[c2];"
          "[w][h][c1][c2]amix=inputs=4:normalize=0,aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:2.4,atrim=start={sk},asetpts=PTS-STARTPTS,afade=t=out:st={fs}:d=0.3[aout]".format(sk=skip, fs=2.1 - skip))
    pipe_video(frames, path, (sting, fc), D - skip)

def make_outro(path, narr_mp3):
    nd = dur_of(narr_mp3); D = round(nd + 0.5 + 0.3, 2); n = int(D * FPS); frames = []
    for i in range(n):
        t = i / FPS; fr = brand_scene(t, 0, show_thanks=True)
        fo = clamp((t - (D - 1.1)) / 1.1)
        if fo > 0: fr = Image.blend(fr, Image.new("RGB", (W, H), (0, 0, 0)), fo)
        frames.append(fr)
    aud = ["-f", "lavfi", "-t", "1.2", "-i", "aevalsrc='0.28*(sin(2*PI*1047*t)+0.45*sin(2*PI*2094*t))*exp(-3.5*t)':s=44100:d=1.2",
           "-i", narr_mp3]
    fc = (f"[2:a]volume=4dB,adelay=500|500[n];[1:a]anull[c];"
          f"[c][n]amix=inputs=2:normalize=0,aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:{D},afade=t=out:st={D - 1.2:.2f}:d=1.2[aout]")
    pipe_video(frames, path, (aud, fc), D)
    return D

# ---------------------------------------------------------------- 配置驱动的时间线
segments = []
SUB_Y = WIN_Y + WIN_H + 80
VOICE = CFG.get("voice", "zh-CN-YunxiNeural"); RATE = CFG.get("rate", "+15%")

def tts(key, text, rate=None):
    mp3 = f"{WORK}/tts/{key}.mp3"
    if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
        cmd = ["edge-tts", "--voice", VOICE, f"--rate={rate or RATE}", "--text", text, "--write-media", mp3]
        if os.environ.get("HTTPS_PROXY"): cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return mp3

def narr(name, items, tag, footer, gap=0.2, tail=0.3):
    """items: [{id,text,frame|card,headline}]  frame=原视频秒数(窗口里的静帧)；card=[行1,行2]绿底金句卡"""
    for i, it in enumerate(items):
        k = it["id"]; a = tts(k, it["text"])
        d = dur_of(a) + gap + (tail if i == len(items) - 1 else 0)
        png = f"{OUT}/{name}_{k}_win.png"
        if "frame" in it: frame_png(it["frame"], png, it.get("focus"))
        else: card_png(png, [(x, "#fff") for x in it["card"]], it.get("card_sub"))
        ovs = []
        if "frame" in it and it.get("headline"):
            hp = f"{OUT}/{name}_{k}_hl.png"; headline_png(hp, it["headline"]); ovs.append((hp, WIN_Y, 0, d))
        parts = [p for p in re.split(r"(?<=[，。？：；])", it["text"]) if p.strip()]
        chunks, cur = [], ""
        for p in parts:
            if len(cur) + len(p) > 18 and cur: chunks.append(cur); cur = p
            else: cur += p
        if cur: chunks.append(cur)
        ad = dur_of(a); tot = sum(len(c) for c in chunks); t = 0
        for j, c in enumerate(chunks):
            sp = f"{OUT}/{name}_{k}_s{j}.png"; sub_png(sp, None, c.rstrip("，。；："))
            t1 = t + ad * len(c) / tot
            ovs.append((sp, SUB_Y + 20, t, d if j == len(chunks) - 1 else t1)); t = t1
        af = f"[{{n}}:a]volume=4dB,apad,atrim=0:{d:.3f},aformat=sample_rates=44100:channel_layouts=stereo[aout]"
        segments.append(render(f"{name}_{k}", d, background(tag, footer), ("still", png), ovs, af, [["-i", a]]))

cover = cover_img(); cover.save(f"{OUT}/cover.png")
if "--cover-only" in sys.argv:
    _p = os.path.splitext(os.path.abspath(CFG.get("output", f"{WORK}/final.mp4")))[0] + "_cover.png"; cover.save(_p); print("cover:", _p); sys.exit(0)
HK = CFG.get("hook")
if HK:
    rg = HK["range"]; a, b = rg["start"], rg["end"]; d = b - a; ovs = []
    hp = f"{OUT}/hook_hl.png"; headline_png(hp, HK["headline"]); ovs.append((hp, WIN_Y, 0, d))
    for j, sb in enumerate(rg["subs"]):
        sp = f"{OUT}/hook_s{j}.png"; sub_png(sp, sb.get("en"), sb["zh"])
        nxt = rg["subs"][j + 1]["s"] - a if j + 1 < len(rg["subs"]) else d
        ovs.append((sp, SUB_Y, max(0, sb["s"] - a), min(d, sb["e"] - a + 0.15, nxt - 0.01)))
    af = f"[1:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.05,afade=t=out:st={d - 0.12:.3f}:d=0.12,aformat=sample_rates=44100:channel_layouts=stereo[aout]"
    segments.append(render("hook", d, background(HK.get("tag", "这句话，值得听完"), CFG["intro"].get("footer", "")), ("video", a, rg.get("focus")), ovs, af, []))
make_intro(f"{OUT}/intro_sting.mp4", cover, bool(HK)); segments.append(f"{OUT}/intro_sting.mp4")

I = CFG["intro"]
narr("intro", I["lines"], I.get("tag", "今日拷问"), I.get("footer", ""))

ci = 0
for grp in CFG["clips"]:
    for rg in grp["ranges"]:
        a, b = rg["start"], rg["end"]; d = b - a; ovs = []; subs = rg["subs"]
        for j, sb in enumerate(subs):
            sp = f"{OUT}/clip{ci}_s{j}.png"; sub_png(sp, sb.get("en"), sb["zh"])
            nxt = subs[j + 1]["s"] - a if j + 1 < len(subs) else d
            ovs.append((sp, SUB_Y, max(0, sb["s"] - a), min(d, sb["e"] - a + 0.15, nxt - 0.01)))
        af = f"[1:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.08,afade=t=out:st={d - 0.12:.3f}:d=0.12,aformat=sample_rates=44100:channel_layouts=stereo[aout]"
        segments.append(render(f"clip{ci}", d, background(grp["tag"], grp.get("footer", "原声片段 · 中文字幕")), ("video", a, rg.get("focus")), ovs, af, []))
        ci += 1

O = CFG["outro"]
narr("outro", O["lines"], O.get("tag", "答案"), O.get("footer", ""))
make_outro(f"{OUT}/outro_end.mp4", tts("thanks", O.get("thanks", "感谢收看，我们下期再见。"), rate="+8%"))
segments.append(f"{OUT}/outro_end.mp4")

with open(f"{OUT}/list.txt", "w") as fl:
    for p in segments: fl.write(f"file '{p}'\n")
final = os.path.abspath(CFG.get("output", f"{WORK}/final.mp4"))
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{OUT}/list.txt", "-c:v", "copy", "-af", "loudnorm=I=-15:TP=-1.5:LRA=11",
     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
import shutil; shutil.copy(f"{OUT}/cover.png", os.path.splitext(final)[0] + "_cover.png")
print("done:", final, f"{dur_of(final):.1f}s")
if dur_of(final) > 120: print("WARNING: 超过 2 分钟，请删减原声片段或旁白")
