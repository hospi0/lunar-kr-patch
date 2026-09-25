# -*- coding: utf-8 -*-
r"""글리프 미리보기 → my files/그래픽/글리프_미리보기.png
  위: 16×16 본문 PoC 대사(원문 줄 모양대로) · 아래: 8×8 인물 이름·마법 이름 몇 개
"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, kr16, build

F14 = bdf.Font(kr16.GALMURI14)
F7 = bdf.Font(build.GALMURI7)


def g16(ch):
    b = kr16.glyph16(F14, ch)
    return np.array([[(int.from_bytes(b[y * 2:y * 2 + 2], 'big') >> (15 - x)) & 1 for x in range(16)] for y in range(16)], np.uint8)


def g8(ch):
    pts, _ = F7.draw(ch)
    a = np.zeros((8, 8), np.uint8)
    for x, y in pts:
        a[y - 1, x] = 1
    return a


def line(chars, fn, cw):
    return np.hstack([fn(c) if '가' <= c <= '힣' else np.zeros((cw, cw), np.uint8) for c in chars]) if chars else np.zeros((cw, cw), np.uint8)


if __name__ == '__main__':
    ko = build.load_scr()['S00:0:0']
    rows = [l.replace('{0d}', '').replace('{08}', '').replace('曖', '♥') for l in ko.split('\\n')]
    blocks = [line(r, g16, 16) for r in rows]
    names = ['엘리', '레나', '세니아', '블레이드', '안식', '각성', '라이트닝블레이드', '세븐헤드드래곤']
    small = [np.kron(line(n, g8, 8), np.ones((2, 2), np.uint8)) for n in names]
    W = max(b.shape[1] for b in blocks + small)
    pad = lambda a: np.hstack([a, np.zeros((a.shape[0], W - a.shape[1]), np.uint8)])
    img = np.vstack([pad(b) for b in blocks] + [np.zeros((8, W), np.uint8)] + [np.vstack([pad(s), np.zeros((4, W), np.uint8)]) for s in small])
    im = Image.fromarray((img * 255).astype(np.uint8)).resize((W * 3, img.shape[0] * 3), Image.NEAREST)
    dst = os.path.join(ROOT, 'my files', '그래픽', '글리프_미리보기.png')
    im.save(dst); print(dst)
