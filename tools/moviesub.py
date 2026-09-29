# -*- coding: utf-8 -*-
r"""동영상 00‥21 대사 자막 — 1단계: 프레임 그리기
  ★2026-09-29 새 대본(my files/movie script.txt — 영상마다 0초부터)으로 전부 새로 번역:
  work/text/movie_sub.tsv 열 = 영상 NN · 시작 · 끝 · 원문 · 번역(«\n» = 한 자막 안 줄바꿈) · 비고.
  행마다 한 자막: 표의 [시작, 끝], 읽을 시간(글자×0.15초+0.8초, 최소 1.2초)보다 짧으면 다음 자막 앞까지 늘림. 부호 뒤 공백 1칸 삭제.
  (옛 판 = 이어 붙인 전체 시각 + «\n» 조각 차례 표시 — work/moviesub_old_20260929.py)
  글씨: 나눔고딕 Bold 14px, 흰색 + 검은 1px 테두리, 화면 아래 가운데, 폭 넘치면 어절 단위 두 줄.
  → work/mvNN/kr/f####.png (그린 프레임만) + my files/그래픽/동영상자막_NN.png(확인용)
  python tools/moviesub.py 00 01
"""
import glob, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX = 14
FPS = 15
TSV = os.path.join(ROOT, 'work', 'text', 'movie_sub.tsv')
PUNCT_SP = re.compile(r'''([,.!?:;)\]}'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )''')    # 부호 뒤 공백 1칸 삭제(전프로젝트 규칙)


def durations():
    """영상 NN → 길이(초) = ffprobe 전체 길이(소리가 영상보다 긴 편이 있다 — 프레임 수만 쓰면 17번부터 1초 넘게 밀림).
    사용자 시간표도 이 길이로 이어 붙인 것(02 시작 2:49.07 · 03 3:42.07 · 10 8:36.9 와 맞음)."""
    import subprocess
    ff = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe'
    out = []
    for n in range(22):
        r = subprocess.run([ff, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                            os.path.join(ROOT, 'work', 'movie', '%02d.cpk' % n)], capture_output=True, text=True)
        out.append(float(r.stdout.strip()))
    return out


def secs(t):
    m, s = t.split(':')
    return int(m) * 60 + float(s)


def rows():
    """→ {영상 번호: [(시작 초, 끝 초, [줄…])]} — 2026-09-29 새 대본(영상마다 0초부터)"""
    res = {}
    for ln in open(TSV, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        lines = [PUNCT_SP.sub(r'\1', p.strip()) for p in c[4].split('\\n')]
        res.setdefault(int(c[0]), []).append((secs(c[1]), secs(c[2]), lines))
    return res


def events():
    """→ {영상: [(시작 프레임, 끝 프레임, [줄…])]} — 표의 [시작, 끝] 을 쓰되 읽을 시간(글자×0.15초+0.8초, 최소 1.2초)보다
    짧으면 늘린다(다음 자막 앞·영상 끝까지)"""
    dur = durations()
    ev = {}
    for n, rs in rows().items():
        for k, (s, e, lines) in enumerate(rs):
            nxt = rs[k + 1][0] if k + 1 < len(rs) else dur[n]
            need = max(sum(len(p) for p in lines) * 0.15 + 0.8, 1.2)
            end = min(max(e, s + need), nxt - 0.07, dur[n] - 0.05)
            f0, f1 = int(round(s * FPS)), int(round(end * FPS)) - 1
            assert f1 >= f0, (n, s, lines)
            ev.setdefault(n, []).append((f0 + 1, f1 + 1, lines))          # 프레임 번호 1부터
    return ev


def wrap(text, F, width):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    if d.textlength(text, font=F) <= width:
        return [text]
    words = text.split(' ')
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        w = max(d.textlength(a, font=F), d.textlength(b, font=F))
        if best is None or w < best[0]:
            best = (w, [a, b])
    assert best and best[0] <= width, ('두 줄로도 넘침', text)
    return best[1]


def render(n, evs):
    src = os.path.join(ROOT, 'work', 'mv%02d' % n)
    dst = os.path.join(src, 'kr')
    os.makedirs(dst, exist_ok=True)
    for f in glob.glob(os.path.join(dst, 'f*.png')):          # 옛 판 프레임 지우기(남으면 그대로 인코딩됨)
        os.remove(f)
    F = ImageFont.truetype(FONT, PX)
    nf = len(glob.glob(os.path.join(src, 'f*.png')))
    for f0, f1, text in evs:
        for f in range(max(1, f0), min(nf, f1) + 1):
            p = os.path.join(dst, 'f%04d.png' % f)
            im = Image.open(p if os.path.exists(p) else os.path.join(src, 'f%04d.png' % f)).convert('RGB')
            W, H = im.size
            lines = [x for t in text for x in wrap(t, F, W - 12)]
            d = ImageDraw.Draw(im)
            y = H - 12 - (len(lines) - 1) * 17
            for ln in lines:
                d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
                y += 17
            im.save(p)
    # 확인용: 자막마다 가운데 프레임
    tiles = []
    for f0, f1, text in evs:
        m = max(1, min(nf, (f0 + f1) // 2))
        tiles.append(np.asarray(Image.open(os.path.join(dst, 'f%04d.png' % m)).convert('RGB')))
    if tiles:
        cols = 3
        rows_ = (len(tiles) + cols - 1) // cols
        h, w, _ = tiles[0].shape
        sheet = np.zeros((rows_ * h, cols * w, 3), np.uint8)
        for i, t in enumerate(tiles):
            sheet[(i // cols) * h:(i // cols + 1) * h, (i % cols) * w:(i % cols + 1) * w] = t
        Image.fromarray(sheet).save(os.path.join(ROOT, 'my files', '그래픽', '동영상자막_%02d.png' % n))
    return len(glob.glob(os.path.join(dst, 'f*.png')))


def room(n):
    """MSLM.FLD 구역 n 의 자리(다음 구역 시작까지)"""
    h = open(os.path.join(ROOT, 'work', '_mslm_head.bin'), 'rb').read()
    offs = []
    for k in range(0, 0x800, 8):
        o, s = struct.unpack_from('>II', h, k)
        if o == 0xFFFFFFFF:
            break
        offs.append(o)
    return offs[n + 1] - offs[n]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    want = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(22))
    ev = events()
    for n in want:
        evs = ev.get(n, [])
        for f0, f1, t in evs:
            print('%02d  %6.2f‥%6.2f초  %s' % (n, (f0 - 1) / FPS, f1 / FPS, ' / '.join(t)))
        k = render(n, evs)
        print('%02d 그린 프레임 %d' % (n, k))
        if '--encode' in sys.argv:              # 2단계: 자막 든 키 구간만 다시 굽기 → work/kr/mvNN.cpk (build.py 가 MSLM.FLD 구역 NN 에)
            import opening_enc
            src = os.path.join(ROOT, 'work', 'movie', '%02d.cpk' % n)
            mv = os.path.join(ROOT, 'work', 'mv%02d' % n)
            opening_enc.reencode(src, mv, os.path.join(mv, 'kr'), os.path.join(ROOT, 'work', 'kr', 'mv%02d.cpk' % n), room(n),
                                 log=lambda s: None)
            print('%02d 다시 구움 → work/kr/mv%02d.cpk %d B' % (n, n, os.path.getsize(os.path.join(ROOT, 'work', 'kr', 'mv%02d.cpk' % n))))
