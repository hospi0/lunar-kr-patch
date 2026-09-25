# -*- coding: utf-8 -*-
r"""마법학원 루나! 한글 빌더 (1차: 8×8 반각 이름·장 제목 카드)
  1) ASCII.FNT(8×8, 글리프 번호 = 코드) — 한글 음절을 0x80‥0xFD 칸에 갈무리7 로 그린다(가나 칸 전부 덮음).
  2) 실행 파일 /1·/2 의 반각 가나 문자열(인물 이름·마법 목록 이름, work/text/ui.tsv 종류 H) → work/text/half_ko.tsv 번역을 제자리에(원문 바이트 안, 남으면 NUL).
  3) CHAPTER.FLD ← tools/chapter_kr.py (장 제목 글씨 시트 LZSS 되압축).
  ⇒ Track 01 사본에 파일 크기 그대로 덮어쓰고 바뀐 섹터만 EDC/ECC 재계산 → work/out/
  (대사·KANJI.FNT 는 본문 번역이 오면 붙인다)
  python tools/build.py [--write [--install]]   (기본 = 예행 · --install = F: 트랙 1 교체)
"""
import collections, hashlib, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
from cdrom_ecc import recalc_sector
import scr, bdf, chapter_kr, kr16

GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
ENCOUNTER_THIRD = False                          # 기본 = 원본 조우율. 배포 때 --enc tenth / --enc never 로 xdelta 3종(원본·1/10·없음) — 사용자 결정 2026-09-26
HALF_CODES = list(range(0x80, 0xFE))          # 한글 8×8 칸(0xFE·0xFF 는 피함)
OUT = os.path.join(ROOT, 'work', 'out')
INSTALL = r'F:\hospi\roms\ss roms\Mahou Gakuen Lunar! (Japan) (2M)\Mahou Gakuen Lunar! (Japan) (2M) (Track 01).bin'   # --install


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


def extra_ui():
    """work/text/ui_extra.tsv — ui.tsv 에서 빠졌던 것(앞 바이트가 NUL 아님, tools/exestr2.py)"""
    fn = os.path.join(ROOT, 'work', 'text', 'ui_extra.tsv')
    out = []
    if os.path.exists(fn):
        for ln in open(fn, encoding='utf-8'):
            if ln.startswith('#') or not ln.strip():
                continue
            r = ln.rstrip('\n').split('\t')
            p, off = r[0].split('@')
            out.append((p, int(off), int(r[1]), r[2]))
    return out


def load_ui():
    """실행 파일 전각 UI 번역: work/text/ui_ko_poc.tsv (JP \t KO) — 같은 JP 는 모든 자리"""
    tr = {}
    for fn in (os.path.join(ROOT, 'work', 'text', 'ui_ko_poc.tsv'),):
        if os.path.exists(fn):
            for ln in open(fn, encoding='utf-8'):
                if ln.startswith('#') or not ln.strip():
                    continue
                jp, ko = ln.rstrip('\n').split('\t')[:2]
                tr[jp] = ko
    return tr


def ui_rows():
    for ln in open(os.path.join(ROOT, 'work', 'text', 'ui.tsv'), encoding='utf-8'):
        if ln.startswith('#'):
            continue
        r = ln.rstrip('\n').split('\t')
        p, off = r[1].split('@')
        yield p, int(off), int(r[2]), r[3], r[4]


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
    ui_tr = load_ui()
    sy16 = sorted(set(c for v in list(scr_tr.values()) + list(ui_tr.values()) for c in v if '가' <= c <= '힣'))
    kfnt = file('/KANJI.FNT')
    m16 = kr16.assign(sy16, bytes(kfnt), freq)
    kr16.put_font(kfnt, m16)
    n_scr = kr16.rewrite_scripts(file, scr_tr, m16, err)
    # 실행 파일 전각 UI — ui.tsv 의 W 자리 + 목록 밖 자리(EXTRA_UI) 에 제자리
    n_ui = 0
    places = [(p, off, n, jp) for p, off, n, kind, jp in ui_rows() if kind == 'W'] + extra_ui()
    for p, off, n, jp in places:
        lead = re.match(r'(\{[0-9a-f]{2}\})*', jp).group()
        core = jp[len(lead):]
        if core not in ui_tr:
            continue
        d = file(p)
        head = bytes(int(x, 16) for x in re.findall(r'\{([0-9a-f]{2})\}', lead))
        if bytes(d[off:off + n]) != head + core.encode('cp932') or d[off + n] != 0:
            err.append('%s@%d UI 원문 불일치 %s' % (p, off, jp)); continue
        b = head + kr16.encode(ui_tr[core], m16)
        if len(b) > n:
            err.append('%s@%d UI 예산 %d < %d: %s' % (p, off, n, len(b), ui_tr[core])); continue
        d[off:off + n] = b + bytes(n - len(b))
        n_ui += 1
    print('16×16 한글 %d자 · 대사 %d줄 · UI %d곳' % (len(sy16), n_scr, n_ui))
    # --- 2.8) 조우율 1/3 (사용자 요청 2026-09-26) ----------------------------------
    #   /1 0x06018338‥: 카운터(0x06052844) = 난수(r4=6) + 5 → 걸음마다 −1, 0 이면 전투(0x0602909C). 평균 약 8걸음.
    #   난수 범위 6→18, 더하기 5→15 → 15‥33걸음(평균 약 24) = 약 1/3.
    #   실험: --enc always = 매 걸음 전투(카운터 = 난수(0)+0 = 0) · --enc never = 전투 없음(감소 −1 → 0, /1@69798 71FF→7100)
    enc = sys.argv[sys.argv.index('--enc') + 1] if '--enc' in sys.argv else ('tenth' if ENCOUNTER_THIRD else None)
    ENC = {'tenth': ((830, 'e406', 'e440'), (834, '7105', '7146')),     # 난수(0‥64)+70 ≈ 평균 102걸음(1/10 — 1/5 가 체감 1/3 이라 사용자 요청 2026-09-26)
           'always': ((830, 'e406', 'e400'), (834, '7105', '7100')),
           'never': ((69798, '71ff', '7100'),)}
    if enc:
        d = file('/1')
        for off, old, new in ENC[enc]:
            if bytes(d[off:off + 2]) != bytes.fromhex(old):
                err.append('/1@%d 조우 코드 원문 불일치' % off); continue
            d[off:off + 2] = bytes.fromhex(new)
        print('조우 패치:', enc)
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
    if '--install' in sys.argv:
        shutil.copyfile(out, INSTALL)
        print('설치', INSTALL)


if __name__ == '__main__':
    main()
