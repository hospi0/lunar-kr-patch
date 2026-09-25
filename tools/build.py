# -*- coding: utf-8 -*-
r"""마법학원 루나! 한글 빌더 (1차: 8×8 반각 이름·장 제목 카드)
  1) ASCII.FNT(8×8, 글리프 번호 = 코드) — 한글 음절을 0x80‥0xFD 칸에 갈무리7 로 그린다(가나 칸 전부 덮음).
  2) 실행 파일 /1·/2 의 반각 가나 문자열(인물 이름·마법 목록 이름, work/text/ui.tsv 종류 H) → work/text/half_ko.tsv 번역을 제자리에(원문 바이트 안, 남으면 NUL).
  3) CHAPTER.FLD ← tools/chapter_kr.py (장 제목 글씨 시트 LZSS 되압축).
  ⇒ Track 01 사본에 파일 크기 그대로 덮어쓰고 바뀐 섹터만 EDC/ECC 재계산 → work/out/
  (대사·KANJI.FNT 는 본문 번역이 오면 붙인다)
  python tools/build.py [--write]   (기본 = 예행)
"""
import collections, hashlib, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
from cdrom_ecc import recalc_sector
import scr, bdf, chapter_kr, kr16

GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
HALF_CODES = list(range(0x80, 0xFE))          # 한글 8×8 칸(0xFE·0xFF 는 피함)
OUT = os.path.join(ROOT, 'work', 'out')


def load_half():
    tr = {}
    for ln in open(os.path.join(ROOT, 'work', 'text', 'half_ko.tsv'), encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        jp, ko = ln.rstrip('\n').split('\t')[:2]
        tr[jp] = ko
    return tr


def load_scr():
    """대사 번역: work/text/scr_ko_poc.tsv + work/ko/*.tsv (번호 \t KO …) — 뒤 파일이 이긴다"""
    import glob
    tr = {}
    files = [os.path.join(ROOT, 'work', 'text', 'scr_ko_poc.tsv')] + sorted(glob.glob(os.path.join(ROOT, 'work', 'ko', '*.tsv')))
    for fn in files:
        if not os.path.exists(fn):
            continue
        for ln in open(fn, encoding='utf-8'):
            if ln.startswith('#') or not ln.strip():
                continue
            r = ln.rstrip('\n').split('\t')
            if len(r) >= 2 and re.match(r'S\d\d:\d+:\d+$', r[0]) and r[-1] and r[-1] != r[0]:
                tr[r[0]] = r[-1]
    return tr


def half_rows():
    for ln in open(os.path.join(ROOT, 'work', 'text', 'ui.tsv'), encoding='utf-8'):
        if ln.startswith('#'):
            continue
        r = ln.rstrip('\n').split('\t')
        if r[3] == 'H':
            p, off = r[1].split('@')
            yield p, int(off), int(r[2]), r[4]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    iso = Iso(scr.TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    data = {}

    def file(p):
        if p not in data:
            data[p] = bytearray(iso.read(ent[p][1], ent[p][2]))
        return data[p]

    err = []
    # --- 1) 8×8 한글 --------------------------------------------------------
    tr = load_half()
    sylls = sorted(set(c for k in tr.values() for c in k if '가' <= c <= '힣'))
    assert len(sylls) <= len(HALF_CODES), ('8×8 칸 부족', len(sylls), len(HALF_CODES))
    code = dict(zip(sylls, HALF_CODES))
    F = bdf.Font(GALMURI7)
    fnt = file('/ASCII.FNT')
    for ch, c in code.items():
        pts, _ = F.draw(ch)
        g = bytearray(8)
        for x, y in pts:
            yy = y - 1                             # 갈무리7 y 2‥8 → 8×8 칸 1‥7 (0행은 원본처럼 비움)
            assert 0 <= yy < 8 and 0 <= x < 8, (ch, x, y)
            g[yy] |= 0x80 >> x
        fnt[c * 8:c * 8 + 8] = g

    def enc(s):
        return bytes(code[ch] if ch in code else ord(ch) for ch in s)

    # --- 2) 반각 이름 제자리 ------------------------------------------------
    nh = 0
    for p, off, n, jp in half_rows():
        if jp not in tr:
            continue                               # 코드 잡음(2자 등)은 번역표에 없다
        d = file(p)
        if bytes(d[off:off + n]).decode('cp932') != jp or d[off + n] != 0:
            err.append('%s@%d 원문 불일치 %s' % (p, off, jp)); continue
        b = enc(tr[jp])
        if len(b) > n:
            err.append('%s@%d 예산 %d < %d: %s' % (p, off, n, len(b), tr[jp])); continue
        d[off:off + n] = b + bytes(n - len(b))
        nh += 1
    # --- 2.5) 본문 16×16 한글 + 대사 블록 --------------------------------------
    scr_tr = load_scr()
    freq = collections.Counter()
    for ln in open(os.path.join(ROOT, 'work', 'text', 'scr.tsv'), encoding='utf-8'):
        freq.update(ln.split('\t')[-1])
    sy16 = sorted(set(c for v in scr_tr.values() for c in v if '가' <= c <= '힣'))
    kfnt = file('/KANJI.FNT')
    m16 = kr16.assign(sy16, bytes(kfnt), freq)
    kr16.put_font(kfnt, m16)
    n_scr = kr16.rewrite_scripts(file, scr_tr, m16, err)
    print('16×16 한글 %d자 · 대사 %d줄' % (len(sy16), n_scr))
    # --- 3) 장 제목 카드 ----------------------------------------------------
    chap, _, clen = chapter_kr.build()
    d = file('/CHAPTER.FLD')
    assert len(chap) == len(d)
    d[:] = chap

    for e in err:
        print('⛔', e)
    if err:
        raise SystemExit('오류 %d — 빌드 안 함' % len(err))
    print('8×8 한글 %d자 · 반각 이름 %d곳 · 장 제목 압축 %d B' % (len(sylls), nh, clen))
    if '--write' not in sys.argv:
        print('예행 끝(디스크 안 씀) — 쓰려면 --write')
        return
    # --- 디스크 --------------------------------------------------------------
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, os.path.basename(scr.TRACK1))
    shutil.copyfile(scr.TRACK1, out)
    with open(out, 'r+b') as fh:
        for p, d in data.items():
            lba = ent[p][1]
            orig = iso.read(lba, len(d))
            for s in range(0, len(d), DATA_LEN):
                if d[s:s + DATA_LEN] != orig[s:s + DATA_LEN]:
                    pos = (lba + s // DATA_LEN) * SECTOR
                    fh.seek(pos)
                    sec = bytearray(fh.read(SECTOR))
                    chunk = d[s:s + DATA_LEN]
                    sec[DATA_OFF:DATA_OFF + len(chunk)] = chunk
                    fh.seek(pos)
                    fh.write(recalc_sector(bytes(sec)))
    h = hashlib.md5(open(out, 'rb').read()).hexdigest().upper()
    print('완료', out, 'md5', h)


if __name__ == '__main__':
    main()
