# -*- coding: utf-8 -*-
r"""장 제목 카드 CHAPTER.FLD (2026-09-26 해독)
  구역 0 = 머리(+0x6C 부터 24 B 스프라이트 기술자 24개 = 12장 × «第X章» + 부제)
      기술자 = [u32 ?][u16 위치/8][u16 (폭/8)<<8 | 높이][s16×8 네 꼭짓점] — VDP1 스프라이트 명령과 같은 꼴
  구역 1 = [u32 압축 길이][LZSS] → 글씨 시트 51,296 B (4bpp, 조각마다 폭이 다르다)
  구역 2‥6 = 배경 그림(미해독)
  python tools/chapter.py      → work/chapter/NN.png (회색조 미리보기)
"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scr, lzss


def sprites(d):
    o, s = scr.sections(d)[0]
    t = d[o:o + s]
    out = []
    for k in range(0x6C, 0x2AC, 24):
        a, b, c = struct.unpack_from('>IHH', t, k)
        out.append((k, b * 8, (c >> 8) * 8, c & 0xFF))
    return out


def sheet(d):
    o, s = scr.sections(d)[1]
    return lzss.block(d, o)


if __name__ == '__main__':
    from PIL import Image
    d = open(os.path.join(ROOT, 'work', 'CHAPTER.FLD'), 'rb').read()
    sh = sheet(d)
    od = os.path.join(ROOT, 'work', 'chapter'); os.makedirs(od, exist_ok=True)
    for i, (k, off, w, h) in enumerate(sprites(d)):
        raw = np.frombuffer(sh[off:off + w * h // 2], np.uint8)
        px = np.stack([raw >> 4, raw & 15], 1).reshape(h, w)
        Image.fromarray((px * 17).astype(np.uint8)).save(os.path.join(od, '%02d.png' % i))
    print('시트 %d B · 조각 %d → work/chapter/' % (len(sh), len(sprites(d))))
