# -*- coding: utf-8 -*-
r"""오프닝(MSLM.FLD 구역 22, Sega FILM 1.09 / cinepak 320×224 15fps) 가사 한글 덮기 — 1단계: 프레임 그리기
  work/op22/f0001.png… (ffmpeg 로 푼 원본 프레임) → work/op22/kr/f0001.png… (덮은 것만) + my files/그래픽/오프닝가사_확인.png
  줄마다: «가사가 다 보이는» 프레임들에서 흰 글자 심(밝고 안 움직이는 화소) 을 잡아 상자 범위를 정하고,
          창 안 프레임마다 글자 대비(심 − 둘레)로 나타남·사라짐 정도(알파)를 잰다.
  상자 = 검정 불투명(알파 > 0.04 인 프레임 전부, 앞뒤 1프레임 더), 한글 = 흰 글씨 + 검은 1px 테두리, 알파만큼 섞음.
  python tools/opening.py
"""
import glob, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'op22')
DST = os.path.join(SRC, 'kr')
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX = 14
Y0, Y1 = 184, 222                      # 가사 줄 찾는 띠

# (한글, 창 첫·끝 프레임, 다 보이는 첫·끝 프레임)   — 프레임 번호는 1부터
LINES = [
    ('달려 나가자 속도를 붙여', 1, 104, 21, 81),
    ('새로운 아침에 여행을 떠나자', 100, 215, 111, 201),
    ('끙끙 앓고 있었어 어젯밤', 300, 400, 321, 381),
    ('불안해서 납작해져 있었던 거야', 395, 500, 411, 471),
    ('별님 소원은 언젠가 이루어질까', 490, 590, 511, 571),
    ('반짝 빛나고는 대답 않을 셈', 578, 700, 591, 671),
    ('어떻게든 될지도 몰라', 708, 760, 721, 741),
    ('문을 여는 거야', 755, 808, 771, 791),
    ('멋진 판타지 여행을 시작하자', 805, 935, 811, 921),
    ('가자 하늘로 도움닫기 하고', 935, 1030, 941, 1011),
    ('구름 틈새를 향해서', 1025, 1130, 1041, 1111),
    ('달려 나가자 속도를 붙여', 1125, 1215, 1141, 1201),
    ('새로운 아침에 여행을 떠나자', 1215, 1310, 1241, 1301),
    ('어떻게든 될 거야', 1305, 1365, 1311, 1341),
]

# 마지막 줄 «なんとかなるはず»(1305‥1356) 은 흰 배경 위라 자동 측정이 안 된다 → 상자는 1331 프레임을 확대해 잰 자리,
# 알파는 띠 그림(10프레임 간격)에서 읽은 대로: 1305 부터 나타나 1311 에 다 보이고 1345 부터 사라져 1356 에 없음.
FIXED = {'어떻게든 될 거야': ((89, 195, 243, 220), [(1304, 0), (1311, 1), (1345, 1), (1356, 0)])}


def load(n):
    return np.asarray(Image.open(os.path.join(SRC, 'f%04d.png' % n)).convert('RGB'))


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def analyse(win0, win1, f0, f1):
    full = np.stack([load(n)[Y0:Y1].min(2) for n in range(f0, f1 + 1)]).astype(np.int16)
    med, sd = np.median(full, 0), full.std(0)
    core = (med > 185) & (sd < 18)
    core[:, :6] = core[:, -6:] = False
    # 작은 부스러기 빼기: 글자 줄 높이 안(행 합이 큰 곳)만
    rows = core.sum(1)
    keep = rows > max(3, rows.max() * 0.15)
    core &= keep[:, None]
    ring = dilate(core, 2) & ~dilate(core, 1)
    ref = med[core].mean() - med[ring].mean()
    alpha = {}
    for n in range(win0, win1 + 1):
        g = load(n)[Y0:Y1].min(2).astype(np.int16)
        a = (g[core].mean() - g[ring].mean()) / ref
        alpha[n] = float(np.clip(a, 0, 1))
    ys, xs = np.nonzero(dilate(core, 3))
    box = (xs.min() - 3, ys.min() + Y0 - 1, xs.max() + 4, ys.max() + Y0 + 2)
    return core, alpha, box


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(DST, exist_ok=True)
    for f in glob.glob(os.path.join(DST, 'f*.png')):   # ★옛 판 프레임이 남으면 그대로 인코딩된다(실기 2026-09-26 끝에 자막 튐)
        os.remove(f)
    F = ImageFont.truetype(FONT, PX)
    plan = {}                                   # 프레임 → [(상자, 글, 알파)]
    report = []
    for text, w0, w1, f0, f1 in LINES:
        if text in FIXED:                       # 배경이 흰 장면이라 글자 심을 못 잡는 줄 — 상자·알파를 손으로
            box, ramp = FIXED[text]
            alpha = {n: float(np.interp(n, [p for p, _ in ramp], [a for _, a in ramp])) for n in range(w0, w1 + 1)}
        else:
            core, alpha, box = analyse(w0, w1, f0, f1)
        on = [n for n, a in alpha.items() if a > 0.06]
        s, e = min(on) - 1, max(on) + 1
        tw = ImageDraw.Draw(Image.new('L', (1, 1))).textlength(text, font=F)
        cx = (box[0] + box[2]) / 2
        x0, x2 = min(box[0], int(cx - tw / 2) - 4), max(box[2], int(cx + tw / 2) + 4)
        box = (max(0, x0), box[1], min(319, x2), box[3])
        for n in range(s, e + 1):
            plan.setdefault(n, []).append((box, text, alpha.get(n, 0.0), cx))
        report.append((text, s, e, box, round(max(alpha.values()), 2)))
        print('%-18s 프레임 %4d‥%4d  상자 %s  최대 알파 %.2f' % (text, s, e, box, max(alpha.values())))
    # 겹침 검사
    for n, v in plan.items():
        if len(v) > 1:
            print('  ⚠ 프레임 %d 두 줄 겹침: %s' % (n, [t for _, t, _, _ in v]))
    for n, items in sorted(plan.items()):
        im = Image.fromarray(load(n)).convert('RGBA')
        # 두 줄이 겹치는 프레임: 상자는 둘 다(합친 넓이), 글은 더 진한 줄 하나만(실기 2026-09-26 마지막 장면 겹침)
        top = max(items, key=lambda t: t[2])
        ub = (min(b[0] for b, *_ in items), min(b[1] for b, *_ in items), max(b[2] for b, *_ in items), max(b[3] for b, *_ in items))
        ImageDraw.Draw(im).rectangle(ub, fill=(0, 0, 0, 255))
        for box, text, a, cx in [top]:
            if a > 0:
                lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
                ImageDraw.Draw(lay).text((cx, (box[1] + box[3]) / 2 + 0.5), text, font=F, anchor='mm',
                                         fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
                arr = np.asarray(lay).copy()
                arr[..., 3] = (arr[..., 3] * a).astype(np.uint8)
                im = Image.alpha_composite(im, Image.fromarray(arr))
        im.convert('RGB').save(os.path.join(DST, 'f%04d.png' % n))
    # 확인 그림: 줄마다 원본/덮은 것(다 보이는 가운데 프레임) + 알파 곡선 대신 시작·끝 프레임
    tiles = []
    for text, w0, w1, f0, f1 in LINES:
        m = (f0 + f1) // 2
        tiles.append(np.concatenate([load(m)[176:224], np.asarray(Image.open(os.path.join(DST, 'f%04d.png' % m)))[176:224]], 1))
    sheet = np.concatenate(tiles, 0)
    dst = os.path.join(ROOT, 'my files', '그래픽', '오프닝가사_확인.png')
    Image.fromarray(sheet).resize((sheet.shape[1] * 2, sheet.shape[0] * 2), Image.NEAREST).save(dst)
    print('덮은 프레임 %d장 · %s' % (len(plan), dst))
    return plan


if __name__ == '__main__':
    main()
