"""Typography motion video engine (Pillow + ffmpeg). 120BPM beat grid, 3-colour palette.
  python engine.py list                      scenes / effects / presets
  python engine.py preset NAME spec.json     write a preset spec
  python engine.py preview spec.json         scene PNGs + contact_sheet.png (folder: <spec dir>/preview)
  python engine.py render spec.json          MP4 (no audio)
spec: {"text","ratio":"16:9|9:16|1:1","fps":30,"copyright","palette":{"cream","ink","accent"},
       "font":path,"effects":["shake","pulse"],"out":"x.mp4",
       "scenes":[{"type":"marquee","dur":2,"wipe":"hard|up|down|left|right"}, ...]}
"""
import json, math, os, random, subprocess, sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

WIN = os.environ.get("WINDIR", "C:/Windows") + "/Fonts/"
FONTS = [WIN + "impact.ttf", WIN + "ariblk.ttf", "/Library/Fonts/Impact.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
SCENE_INFO = {  # name: (min seconds, description)
    "marquee": (1, "작은 글자가 바둑판처럼 깔리고 줄마다 엇갈려 흐름"),
    "bounce": (1.5, "큰 글자가 한 글자씩 위아래로 튀며 자리 잡음 (첫 두 글자는 반대 회전)"),
    "tunnel": (1, "외곽선만 남은 글자가 터널처럼 안쪽으로 빨려 들어감"),
    "halftone": (1, "글자 안을 도트로 채우고 도트 크기가 파도침"),
    "glitch": (1.5, "가로 슬라이스가 어긋났다 맞춰지고 포인트색 잔상이 남음"),
    "emblem": (1.5, "글자가 원 둘레를 따라 돌고 안쪽 링은 반대로 회전"),
    "logo": (1.5, "정리된 로고 + 저작권 표기, 마지막 0.5초 정지"),
}
EFFECT_INFO = {"shake": "박자마다 화면이 살짝 흔들림", "pulse": "박자마다 살짝 줌 인 되는 펄스"}
PRESETS = {
    "lookbook": [("marquee", 2, "hard"), ("bounce", 2, "hard"), ("tunnel", 2.5, "hard"), ("halftone", 2.5, "up"),
                 ("glitch", 2.5, "hard"), ("emblem", 2, "right"), ("logo", 1.5, "up")],
    "short": [("marquee", 2, "hard"), ("bounce", 2, "hard"), ("emblem", 2, "right"), ("logo", 1.5, "up")],
}
PEAK = {"marquee": .6, "bounce": .75, "tunnel": .5, "halftone": .5, "glitch": .65, "emblem": .6, "logo": .97}


def cl(x): return min(1.0, max(0.0, x))
def io(x): x = cl(x); return 4 * x**3 if x < .5 else 1 - (-2 * x + 2)**3 / 2
def eo(x): return 1 - (1 - cl(x))**4
def bo(x): x = cl(x) - 1; return 1 + 2.70158 * x**3 + 1.70158 * x**2
def beat(t): b = int(t / 0.5); return b, t / 0.5 - b
def edge(m, k): return ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(k)))
def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Engine:
    def __init__(s, spec):
        s.spec = spec; s.text = spec.get("text", "BBANGDUCK").upper()
        s.W, s.H = SIZES[spec.get("ratio", "16:9")]; s.fps = spec.get("fps", 30)
        p = spec.get("palette", {})
        s.CREAM, s.INK, s.YEL = (rgb(p.get("cream", "#F4EFE6")), rgb(p.get("ink", "#141414")), rgb(p.get("accent", "#FFD23F")))
        s.copy = spec.get("copyright", "© " + s.text); s.k = min(s.W, s.H) / 1080
        s.fx = spec.get("effects", [])
        s.fpath = next(f for f in [spec.get("font")] + FONTS if f and os.path.exists(f))
        s.scenes = [(d["type"], float(d["dur"]), d.get("wipe", "hard")) for d in spec["scenes"]]
        s._word(); s._strip()

    def font(s, sz): return ImageFont.truetype(s.fpath, max(1, int(sz)))
    def solid(s, c): return Image.new("RGB", (s.W, s.H), c)

    def _word(s):
        W, H = s.W, s.H; f = s.font(300); pad = 8
        bbs = [f.getbbox(c, anchor="ls") for c in s.text + "B"]  # full glyph extent (descenders, Hangul)
        top, bot = min(b[1] for b in bbs), max(b[3] for b in bbs); ch = bot - top + pad * 2
        width = int(W * (0.78 if W > H else 0.8)); height = int(420 * s.k)
        sx = width / sum(f.getlength(c) for c in s.text); sy = height / ch
        s.tiles, s.xs, x = [], [], 0.0
        for c in s.text:
            a = f.getlength(c); t = Image.new("L", (math.ceil(a), ch), 0)
            ImageDraw.Draw(t).text((0, pad - top), c, font=f, fill=255, anchor="ls")
            s.tiles.append(t.resize((max(1, round(a * sx)), height), Image.LANCZOS)); s.xs.append(round(x * sx)); x += a
        s.base = Image.new("L", (width, height), 0)
        for t, x in zip(s.tiles, s.xs): s.base.paste(255, (x, 0), t)
        s.BW, s.BH = s.base.size; s.BX, s.BY = (W - s.BW) // 2, (H - s.BH) // 2

    def _strip(s):
        s.f1 = s.font(100 * s.k); s.RH = int(130 * s.k); s.NR = math.ceil(s.H / s.RH)
        s.PER = round(s.f1.getlength(s.text) + 46 * s.k)
        s.STRIP = Image.new("L", (s.W + 3 * s.PER, s.RH), 0); d = ImageDraw.Draw(s.STRIP)
        for k in range(s.W // s.PER + 4): d.text((k * s.PER, s.RH // 2), s.text, font=s.f1, fill=255, anchor="lm")

    # ---- scenes: fn(t_local, dur) -> RGB ----
    def sc_marquee(s, t, dur):
        img = s.solid(s.CREAM); b, u = beat(t)
        for r in range(s.NR):
            d = 1 if r % 2 else -1
            off = d * (b + io(u)) * s.PER * 0.22 * (1 + 0.25 * (r % 4)); x0 = int(-off) % s.PER
            y = (s.H - s.NR * s.RH) // 2 + r * s.RH
            if (r - 2 * b) % 13 == 0: img.paste(s.YEL, (0, y + 10, s.W, y + s.RH - 10))
            img.paste(s.INK, (0, y), s.STRIP.crop((x0, 0, x0 + s.W, s.RH)))
        return img

    def sc_bounce(s, t, dur):
        img = s.solid(s.CREAM); n = len(s.tiles); step = min(0.12, max(0.02, (dur - 0.9) / max(1, n - 1)))
        for i, tile in enumerate(s.tiles):
            u = (t - step * i) / 0.6
            if u <= 0: continue
            dy = (-1 if i % 2 else 1) * max(s.W, s.H) * 0.6 * (1 - bo(u))
            ang = (720 if i == 0 else -720 if i == 1 else 0) * (1 - eo(u))
            m = tile.rotate(ang, resample=Image.BICUBIC, expand=True) if ang else tile
            cx, cy = s.BX + s.xs[i] + tile.width / 2, s.H / 2 + dy
            img.paste(s.INK, (int(cx - m.width / 2), int(cy - m.height / 2)), m)
        bw = int(s.BW * io((t - step * n - 0.5) / 0.4))
        ImageDraw.Draw(img).rectangle((s.BX, s.BY + s.BH + 50 * s.k, s.BX + bw, s.BY + s.BH + 62 * s.k), fill=s.YEL)
        return img

    def sc_tunnel(s, t, dur):
        img = s.solid(s.CREAM); b, u = beat(t); p = b + io(u); R = 0.8
        for m in sorted(range(int(p) - 8, int(p) + 3), key=lambda m: -R**(p - m)):
            z = R**(p - m)
            if not 0.03 < z < 2.0: continue
            w, h = round(s.BW * z) + 12, round(s.BH * z) + 12
            sm = Image.new("L", (w, h), 0); sm.paste(s.base.resize((w - 12, h - 12), Image.LANCZOS), (6, 6))
            img.paste(s.YEL if m % 4 == 0 else s.INK, ((s.W - w) // 2, (s.H - h) // 2), edge(sm, 5))
        return img

    def sc_halftone(s, t, dur):
        img = s.solid(s.INK); b, u = beat(t); ph = 2 * math.pi * (b + io(u)) * 0.5
        sp = int(28 * s.k); BW, BH = s.BW, s.BH
        dots = Image.new("L", (BW * 2, BH * 2), 0); dd = ImageDraw.Draw(dots)
        for row, gy in enumerate(range(sp // 2, BH, sp)):
            for gx in range(sp // 2 + (row % 2) * sp // 2, BW, sp):
                v = 0.5 + 0.5 * math.sin(2 * math.pi * (gx + gy * 0.6) / (380 * s.k) - ph)
                r = sp * (0.06 + 0.74 * v) * 0.9
                dd.ellipse(((gx - r) * 2, (gy - r) * 2, (gx + r) * 2, (gy + r) * 2), fill=255)
        img.paste(s.YEL, (s.BX, s.BY), ImageChops.multiply(dots.resize((BW, BH), Image.LANCZOS), s.base))
        return img

    def sc_glitch(s, t, dur):
        b, u = beat(t); last = b >= int(dur / 0.5) - 1; img = s.solid(s.INK)
        rng = random.Random(b * 7 + 3); n = 6
        env = 0 if last else eo(u / 0.2) * (1 - io((u - 0.4) / 0.5)); ghost = 0 if last else max(0.0, 1 - u / 0.45)
        main, gh = Image.new("L", (s.W, s.H), 0), Image.new("L", (s.W, s.H), 0)
        for j in range(n):
            y0, y1 = s.BY + s.BH * j // n, s.BY + s.BH * (j + 1) // n
            band = s.base.crop((0, y0 - s.BY, s.BW, y1 - s.BY))
            sh = int(rng.choice((-1, 1)) * rng.randint(14, 46) * s.k * env)
            main.paste(band, (s.BX + sh, y0)); gh.paste(band, (s.BX + sh - int(22 * s.k * ghost), y0))
        img.paste(s.YEL, (0, 0), gh); img.paste(s.CREAM, (0, 0), main)
        return img

    def _ring(s, img, seq, radius, color, rot):
        t100 = sum(s.font(100).getlength(c) for c in seq); sz = int(100 * 2 * math.pi * radius / t100 * 0.97)
        f = s.font(sz); cap = -f.getbbox("B", anchor="ls")[1]
        advs = [f.getlength(c) for c in seq]; tot = sum(advs); cum = 0
        for c, a in zip(seq, advs):
            th = (cum + a / 2) / tot * 360 + rot; cum += a
            if c == " ": continue
            tile = Image.new("L", (sz * 2, sz * 2), 0)
            ImageDraw.Draw(tile).text((sz, sz + cap // 2), c, font=f, fill=255, anchor="ms")
            tile = tile.rotate(-th, resample=Image.BICUBIC)
            x = s.W / 2 + radius * math.sin(math.radians(th)); y = s.H / 2 - radius * math.cos(math.radians(th))
            img.paste(color, (int(x - sz), int(y - sz)), tile)

    def sc_emblem(s, t, dur):
        k = s.k; e = io(t / dur); em = s.solid(s.CREAM); d = ImageDraw.Draw(em); cx, cy = s.W // 2, s.H // 2
        def circ(r, **kw): d.ellipse((cx - r, cy - r, cx + r, cy + r), **kw)
        circ(500 * k, outline=s.INK, width=3); circ(290 * k, outline=s.INK, width=3); circ(40 * k, fill=s.YEL)
        s._ring(em, (s.text + " • ") * 3, 395 * k, s.INK, 150 * e); s._ring(em, (s.text + " • ") * 2, 175 * k, s.INK, -300 * e)
        z = bo(t / 0.5) * 0.85; w, h = max(2, round(s.W * z)), max(2, round(s.H * z))
        bg = s.solid(s.CREAM); bg.paste(em.resize((w, h), Image.LANCZOS), ((s.W - w) // 2, (s.H - h) // 2))
        return bg

    def sc_logo(s, t, dur):
        img = s.solid(s.CREAM); bh = s.BH + int(60 * s.k); by = (s.H - bh) // 2
        ImageDraw.Draw(img).rectangle((s.BX, by + bh - 40 * s.k, s.BX + int(s.BW * io((t - 0.3) / 0.5)), by + bh - 28 * s.k), fill=s.YEL)
        layer = Image.new("L", (s.W, s.H), 0); layer.paste(s.base, (s.BX, s.BY + int(bh * (1 - eo((t - 0.2) / 0.5)))))
        clip = Image.new("L", (s.W, s.H), 0); ImageDraw.Draw(clip).rectangle((0, by, s.W, by + bh), fill=255)
        img.paste(s.INK, (0, 0), ImageChops.multiply(layer, clip))
        f = s.font(46 * s.k); adv = [f.getlength(c) + 8 * s.k for c in s.copy]; x = (s.W - sum(adv)) / 2
        tl = Image.new("L", (s.W, s.H), 0); dt = ImageDraw.Draw(tl)
        for c, a in zip(s.copy, adv): dt.text((x, by + bh + 70 * s.k), c, font=f, fill=255, anchor="lm"); x += a
        dt.rectangle((int(s.W * io((t - 0.6) / 0.4)), 0, s.W, s.H), fill=0)
        img.paste(s.INK, (0, 0), tl)
        return img

    # ---- timeline ----
    def total(s): return sum(d for _, d, _ in s.scenes)

    def scene_at(s, t):
        a = 0.0
        for i, (ty, d, w) in enumerate(s.scenes):
            if t < a + d or i == len(s.scenes) - 1: return i, t - a
            a += d

    def frame(s, f):
        t = f / s.fps; i, tl = s.scene_at(t); ty, d, wipe = s.scenes[i]; img = getattr(s, "sc_" + ty)(tl, d)
        if wipe != "hard" and i > 0 and tl < 0.25:
            pt, pd, _ = s.scenes[i - 1]; u = io(tl / 0.25); prev = getattr(s, "sc_" + pt)(pd, pd); W, H = s.W, s.H
            if wipe == "up": y = int(H * (1 - u)); prev.paste(img.crop((0, y, W, H)), (0, y))
            elif wipe == "down": y = int(H * u); prev.paste(img.crop((0, 0, W, y)), (0, 0))
            elif wipe == "right": x = int(W * u); prev.paste(img.crop((0, 0, x, H)), (0, 0))
            else: x = int(W * (1 - u)); prev.paste(img.crop((x, 0, W, H)), (x, 0))
            img = prev
        return s.post(img, t)

    def post(s, img, t):
        b, u = beat(t); W, H = s.W, s.H
        if "pulse" in s.fx:
            z = 1 + 0.035 * (1 - eo(u)); w, h = int(W * z), int(H * z)
            img = img.resize((w, h), Image.BILINEAR).crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))
        if "shake" in s.fx and u < 0.2:
            r = random.Random(b); a = 10 * s.k * (1 - u / 0.2); dx, dy = r.uniform(-a, a), r.uniform(-a, a)
            img = img.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=img.getpixel((0, 0)))
        return img


def load(p): return Engine(json.load(open(p, encoding="utf-8")))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print("SCENES"); [print(f"  {k:9} (최소 {v[0]}초) {v[1]}") for k, v in SCENE_INFO.items()]
        print("EFFECTS"); [print(f"  {k:9} {v}") for k, v in EFFECT_INFO.items()]
        print("WIPES\n  hard up down left right"); print("PRESETS")
        for k, v in PRESETS.items(): print(f"  {k:9} {sum(x[1] for x in v)}초: " + " > ".join(x[0] for x in v))
    elif cmd == "preset":
        sc = [{"type": a, "dur": b, "wipe": c} for a, b, c in PRESETS[sys.argv[2]]]
        json.dump({"text": "BBANGDUCK", "ratio": "16:9", "fps": 30, "effects": [], "scenes": sc},
                  open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    else:
        sp = sys.argv[2]; e = load(sp); d = os.path.dirname(os.path.abspath(sp))
        bad = [t for t, dur, _ in e.scenes if dur < SCENE_INFO[t][0]]
        if bad: sys.exit(f"장면 길이가 최소값보다 짧음: {bad}")
        if cmd == "preview":
            od = os.path.join(d, "preview"); os.makedirs(od, exist_ok=True); tw = 480; th = int(tw * e.H / e.W)
            cols = 4; rows = math.ceil(len(e.scenes) / cols); sheet = Image.new("RGB", (cols * (tw + 10), rows * (th + 10)), (128, 128, 128))
            for k, (ty, dur, _) in enumerate(e.scenes):
                im = e.post(getattr(e, "sc_" + ty)(dur * PEAK[ty], dur), dur * PEAK[ty]); im.save(os.path.join(od, f"{k + 1}_{ty}.png"))
                sheet.paste(im.resize((tw, th), Image.LANCZOS), ((k % cols) * (tw + 10) + 5, (k // cols) * (th + 10) + 5))
            sheet.save(os.path.join(od, "contact_sheet.png")); print("preview:", od)
        elif cmd == "render":
            import imageio_ffmpeg
            out = os.path.join(d, e.spec.get("out", f"{e.text.lower()}_{e.spec.get('ratio', '16:9').replace(':', 'x')}.mp4"))
            p = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                  "-s", f"{e.W}x{e.H}", "-r", str(e.fps), "-i", "-", "-c:v", "libx264", "-crf", "15",
                                  "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
            for f in range(round(e.total() * e.fps)): p.stdin.write(e.frame(f).tobytes())
            p.stdin.close(); p.wait(); print("rendered:", out)
