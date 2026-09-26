# -*- coding: utf-8 -*-
r"""저장 화면 «本体RAM»·«カートリッジRAM» 그림 글자 → «본체RAM»·«카트리지RAM»
  같은 UI 시트가 두 벌: MISC.FLD 구역 1, EFCT.FLD 구역 4 — [u32 길이][LZSS(장 제목과 같은 형식)] → VDP1 0x8000 에 풀림.
  시트 +0x000 = 80×16 «カートリッジRAM», +0x280 = 48×16 «本体RAM» (4bpp, 잉크 = 색 1, 바탕 0).
  (2026-09-26 저장 화면 스테이트의 VDP1 명령표 → srca 0x8000/0x8280 → 디스크 전체 LZSS 구역 풀어 찾음)
  가나·한자만 갈무리11 콘덴스드 한글로 바꾸고 원본 «RAM» 은 살려 붙인 뒤 가운데 정렬(본체 자리가 20px 뿐이라 콘덴스드).
  python tools/ramlabel.py   → my files/그래픽/RAM라벨_비교.png
"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, lzss, scr

GALMURI11 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Condensed.bdf'
SHEETS = [('/MISC.FLD', 1), ('/EFCT.FLD', 4)]
LABELS = [(0x000, 80, '카트리지', 54), (0x280, 48, '본체', 21)]   # (시트 위치, 폭, 한글, 원본 «RAM» 시작 열)
INK = 1


def render(text, w, orig, ram_x, h=16):
    """한글(갈무리11 콘덴스드, 3‥13행) + 2px + 원본 «RAM» 조각(ram_x 부터) → 가운데 정렬"""
    F = bdf.Font(GALMURI11)
    pts, _ = F.draw(text)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    kw = max(xs) - min(xs) + 1
    ram = orig[:, ram_x:]
    rc = np.nonzero(ram.any(0))[0]
    ram = ram[:, rc.min():rc.max() + 1]
    gw = kw + 2 + ram.shape[1]
    assert gw <= w, (text, gw, w)
    x0 = (w - gw) // 2
    px = np.zeros((h, w), np.uint8)
    for x, y in pts:
        px[y - min(ys) + 3, x - min(xs) + x0] = INK
    px[:, x0 + kw + 2:x0 + gw] = ram
    return px


def patch_sheet(sheet):
    s = bytearray(sheet)
    for off, w, text, ram_x in LABELS:
        raw = np.frombuffer(sheet[off:off + w * 8], np.uint8)
        orig = np.stack([raw >> 4, raw & 15], 1).reshape(16, w)
        px = render(text, w, orig, ram_x)
        s[off:off + w * 16 // 2] = (px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).tobytes()
    return bytes(s)


def apply(d, si):
    """d = FLD bytearray, si = 구역 번호 → 제자리 되압축(다음 구역 전까지), 파일 머리 크기 갱신"""
    secs = scr.sections(bytes(d))
    o, s = secs[si]
    n = struct.unpack_from('>I', d, o)[0]
    sheet = lzss.decompress(bytes(d[o + 4:o + 4 + n]))
    new = patch_sheet(sheet)
    comp = lzss.compress(new)
    assert lzss.decompress(comp) == new, '왕복 불일치'
    blk = struct.pack('>I', len(comp)) + comp
    room = min(so for so, _ in secs if so > o) - o
    assert len(blk) <= room, ('구역 자리 초과', len(blk), room)
    d[o:o + room] = blk + b'\xff' * (room - len(blk))
    for k in range(0, 0x800, 8):
        so, _ = struct.unpack_from('>II', d, k)
        if so == 0xFFFFFFFF:
            break
        if so == o:
            struct.pack_into('>I', d, k + 4, len(blk))
    return sheet, new


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    from PIL import Image
    from iso9660 import Iso
    iso = Iso(scr.TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    p, si = SHEETS[0]
    d = bytearray(iso.read(ent[p][1], ent[p][2]))
    old, new = apply(d, si)
    rows = []
    for off, w, *_ in LABELS:
        for sh in (old, new):
            raw = np.frombuffer(sh[off:off + w * 8], np.uint8)
            rows.append(np.stack([raw >> 4, raw & 15], 1).reshape(16, w))
    W = 80
    c = np.full((len(rows) * 18, W + 4), 60, np.uint8)
    for i, r in enumerate(rows):
        c[i * 18 + 1:i * 18 + 17, 2:2 + r.shape[1]] = np.where(r > 0, 255, 0)
    dst = os.path.join(ROOT, 'my files', '그래픽', 'RAM라벨_비교.png')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray(c).resize((c.shape[1] * 4, c.shape[0] * 4), Image.NEAREST).save(dst)
    print(dst)
