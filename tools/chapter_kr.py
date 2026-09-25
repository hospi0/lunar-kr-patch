# -*- coding: utf-8 -*-
r"""장 제목 카드 한글판 — CHAPTER.FLD 구역 0(기술자)·구역 1(LZSS 글씨 시트)을 다시 만든다.
  글씨: 나눔고딕 ExtraBold, 4bpp 명암 = 원본 조각에서 잰 밝기 순서 RAMP(1 테두리 … 7 흰 채움), 둘레 1px 테두리(1).
  조각 = 폭 8의 배수, 시트 안 32 B 정렬(원본과 같음), 기술자 = 위치/8 · (폭/8)<<8|높이 · 꼭짓점(TL,TR,BL,BR).
  python tools/chapter_kr.py   → work/kr/CHAPTER.FLD + my files/그래픽/장제목_비교.png
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scr, lzss, chapter

FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
RAMP = [1, 8, 4, 13, 6, 5, 2, 10, 9, 3, 11, 12, 7]      # 어두움 → 밝음 (원본 조각 이웃 통계로 잰 순서)
TITLES = [('제1장', '바다를 가는 학원'), ('제2장', '마녀 바루아'), ('제3장', '전격 대작전'), ('제4장', '필살! 합체 마법'),
          ('제5장', '유령의 섬'), ('제6장', '인어의 보석'), ('제7장', '전격 대작전 2'), ('제8장', '수수께끼의 신입생'),
          ('제9장', '열리지 않는 문'), ('제10장', '별을 보는 힘'), ('제11장', '이엔과 청룡'), ('제12장', '안녕 마법학원')]
PX_HEAD, PX_SUB = 31, 28   # 글꼴 크기 — 원본 조각 높이(第X章 33‥35, 부제 29‥31)에 맞춤


def render(text, px):
    f = ImageFont.truetype(FONT, px)
    x0, y0, x1, y1 = f.getbbox(text)
    w, h = x1 - x0 + 4, y1 - y0 + 4
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((2 - x0, 2 - y0), text, font=f, fill=255)
    c = np.asarray(im, np.float32) / 255
    fill = c > 0.15
    ring = np.zeros_like(fill)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= np.roll(np.roll(fill, dy, 0), dx, 1)
    out = np.zeros(c.shape, np.uint8)
    out[ring & ~fill] = 1
    lv = np.clip((c - 0.15) / 0.85, 0, 1)
    out[fill] = np.array(RAMP, np.uint8)[np.round(lv[fill] * (len(RAMP) - 1)).astype(int)]
    ys, xs = np.nonzero(out)
    out = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = out.shape
    W = (w + 7) // 8 * 8
    pad = np.zeros((h, W), np.uint8); pad[:, (W - w) // 2:(W - w) // 2 + w] = out
    return pad


def build():
    src = open(os.path.join(ROOT, 'work', 'CHAPTER.FLD'), 'rb').read()
    d = bytearray(src)
    secs = scr.sections(src)
    o0, s0 = secs[0]
    sheet = bytearray()
    imgs = []
    for k, (a, b) in enumerate(TITLES):
        for text, size in ((a, PX_HEAD), (b, PX_SUB)):
            px = render(text, size)
            imgs.append(px)
    descs = chapter.sprites(src)
    assert len(descs) == len(imgs) == 24
    for (k, _, _, _), px in zip(descs, imgs):
        h, w = px.shape
        off = len(sheet)
        sheet += (px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).tobytes()
        sheet += bytes((-len(sheet)) % 32)
        c = ((w // 8) << 8) | h
        struct.pack_into('>HH', d, o0 + k + 4, off // 8, c)
        x0, x1, y0, y1 = -(w // 2), w // 2 - 1, -(h // 2), h - h // 2 - 1
        struct.pack_into('>8h', d, o0 + k + 8, x0, y0, x1, y0, x0, y1, x1, y1)
    orig_sheet = chapter.sheet(src)
    assert len(sheet) <= len(orig_sheet), ('시트가 원본보다 큼', len(sheet), len(orig_sheet))
    sheet += bytes(len(orig_sheet) - len(sheet))
    comp = lzss.compress(bytes(sheet))
    assert lzss.decompress(comp) == bytes(sheet), '왕복 불일치'
    o1, s1 = secs[1]
    room = secs[2][0] - o1
    blk = struct.pack('>I', len(comp)) + comp
    assert len(blk) <= room, ('구역 1 자리 초과', len(blk), room)
    d[o1:o1 + room] = blk + b'\xff' * (room - len(blk))
    # 파일 머리의 구역 1 크기
    struct.pack_into('>I', d, 8 + 4, len(blk))
    return bytes(d), imgs, len(comp)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    out, imgs, n = build()
    os.makedirs(os.path.join(ROOT, 'work', 'kr'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'kr', 'CHAPTER.FLD'), 'wb').write(out)
    # 비교 그림(회색조: 번호 → 밝기 순위)
    lvl = np.zeros(16, np.uint8)
    for i, v in enumerate(RAMP):
        lvl[v] = 40 + i * 17
    src = open(os.path.join(ROOT, 'work', 'CHAPTER.FLD'), 'rb').read()
    sh = chapter.sheet(src)
    rows = []
    for (k, off, w, h), px in zip(chapter.sprites(src), imgs):
        raw = np.frombuffer(sh[off:off + w * h // 2], np.uint8)
        o = np.stack([raw >> 4, raw & 15], 1).reshape(h, w)
        rows.append((Image.fromarray(lvl[o]), Image.fromarray(lvl[px])))
    W = max(a.width for a, _ in rows) + max(b.width for _, b in rows) + 30
    H = sum(max(a.height, b.height) + 4 for a, b in rows)
    c = Image.new('L', (W, H), 90); y = 0
    for a, b in rows:
        c.paste(a, (0, y)); c.paste(b, (max(x.width for x, _ in rows) + 20, y)); y += max(a.height, b.height) + 4
    dst = os.path.join(ROOT, 'my files', '그래픽', '장제목_비교.png')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    c.resize((c.width * 2, c.height * 2), Image.NEAREST).save(dst)
    print('work/kr/CHAPTER.FLD · 압축 %d B · %s' % (n, dst))
