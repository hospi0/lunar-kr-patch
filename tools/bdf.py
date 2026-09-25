# -*- coding: utf-8 -*-
r"""BDF 비트맵 글꼴 읽기 (갈무리)

  from bdf import Font
  f = Font(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.bdf')
  f.draw('안녕') → ([(x, y)…], 폭)
"""
import os


class Font:
    def __init__(self, path):
        self.g = {}
        self.asc = 0
        cur, bm = None, False
        for ln in open(path, encoding='utf-8'):
            ln = ln.strip()
            if ln.startswith('FONT_ASCENT'):
                self.asc = int(ln.split()[1])
            elif ln.startswith('ENCODING'):
                cur = {'enc': int(ln.split()[1]), 'rows': [], 'dw': 0}
            elif ln.startswith('DWIDTH') and cur is not None:
                cur['dw'] = int(ln.split()[1])
            elif ln.startswith('BBX') and cur is not None:
                w, h, xo, yo = [int(v) for v in ln.split()[1:5]]
                cur['bbx'] = (w, h, xo, yo)
            elif ln == 'BITMAP':
                bm = True
            elif ln == 'ENDCHAR':
                if cur is not None and 'bbx' in cur:
                    self.g[cur['enc']] = cur
                cur, bm = None, False
            elif bm and cur is not None:
                cur['rows'].append(ln)

    def draw(self, text, x=0, y=0):
        """→ ([(x, y)…] 잉크, 전체 폭) — y 는 «윗선» 기준"""
        pts = []
        for ch in text:
            c = self.g.get(ord(ch))
            if c is None:
                x += 7
                continue
            w, h, xo, yo = c['bbx']
            top = y + self.asc - (h + yo)
            for r, hx in enumerate(c['rows']):
                v = int(hx, 16)
                n = len(hx) * 4
                for i in range(w):
                    if (v >> (n - 1 - i)) & 1:
                        pts.append((x + xo + i, top + r))
            x += c['dw']
        return pts, x
