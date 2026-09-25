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


def dlg_fix(ko):
    """대사 KO 빌드 전 손질: 반각 !·? → 전각(규칙 문서 — 반각은 대사창에서 8×8 로 나올 수 있다). 반각 빈칸은 그대로(원문도 씀)."""
    return ko.replace('!', '！').replace('?', '？')


def load_scr():
    """대사 번역: work/text/scr.tsv 4열 KO + work/ko/*.tsv(번호 \t … \t KO) 덧씌움. 빈칸·«=»(원문 그대로)는 건너뜀."""
    import glob
    tr = {}
    for ln in open(os.path.join(ROOT, 'work', 'text', 'scr.tsv'), encoding='utf-8'):
        r = ln.rstrip('\n').split('\t')
        if len(r) >= 4 and not r[0].startswith('#') and r[3] and r[3] != '=':
            tr[r[0]] = dlg_fix(r[3])
    for fn in sorted(glob.glob(os.path.join(ROOT, 'work', 'ko', '*.tsv'))):
        for ln in open(fn, encoding='utf-8'):
            r = ln.rstrip('\n').split('\t')
            if len(r) >= 2 and re.match(r'S\d\d:\d+:\d+$', r[0]) and r[-1] and r[-1] not in (r[0], '='):
                tr[r[0]] = dlg_fix(r[-1])
    return tr


def ui_table():
    """실행 파일 문자열 번역 — (파일, 위치, 예산, 종류 W/H, JP, KO). ui.tsv(6열) + ui_extra.tsv(위치·예산·JP·KO, 종류 W).
       KO 가 비었거나 «=» 면 원문 그대로."""
    out = []
    for ln in open(os.path.join(ROOT, 'work', 'text', 'ui.tsv'), encoding='utf-8'):
        if ln.startswith('#'):
            continue
        r = ln.rstrip('\n').split('\t')
        p, off = r[1].split('@')
        ko = r[5] if len(r) > 5 else ''
        out.append((p, int(off), int(r[2]), r[3], r[4], ko))
    fn = os.path.join(ROOT, 'work', 'text', 'ui_extra.tsv')
    if os.path.exists(fn):
        for ln in open(fn, encoding='utf-8'):
            if ln.startswith('#') or not ln.strip():
                continue
            r = ln.rstrip('\n').split('\t')
            p, off = r[0].split('@')
            out.append((p, int(off), int(r[1]), 'W', r[2], r[3] if len(r) > 3 else ''))
    return [x for x in out if x[5] and x[5] != '=']


def jp_bytes(jp):
    """표기(JP) → 원본 바이트({xx} 제어, \n, cp932)"""
    out = bytearray()
    for tok in re.split(r'(\{[0-9a-f]{2}\}|\\n)', jp):
        if not tok:
            continue
        if tok == '\\n':
            out.append(0x0A)
        elif re.fullmatch(r'\{[0-9a-f]{2}\}', tok):
            out.append(int(tok[1:3], 16))
        else:
            out += tok.encode('cp932')
    return bytes(out)


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
    uit = ui_table()
    # --- 1) 8×8 한글 --------------------------------------------------------
    sylls = sorted(set(c for x in uit if x[3] == 'H' for c in x[5] if '가' <= c <= '힣'))
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
    for p, off, n, kind, jp, ko in uit:
        if kind != 'H':
            continue
        d = file(p)
        if bytes(d[off:off + n]) != jp_bytes(jp) or d[off + n] != 0:
            err.append('%s@%d 원문 불일치 %s' % (p, off, jp)); continue
        b = enc(ko)
        if len(b) > n:
            err.append('%s@%d 예산 %d < %d: %s' % (p, off, n, len(b), ko)); continue
        d[off:off + n] = b + bytes(n - len(b))
        nh += 1
    # --- 2.5) 본문 16×16 한글 + 대사 블록 --------------------------------------
    scr_tr = load_scr()
    freq = collections.Counter()
    for ln in open(os.path.join(ROOT, 'work', 'text', 'scr.tsv'), encoding='utf-8'):
        freq.update(ln.split('\t')[-1])
    wko = [x[5] for x in uit if x[3] == 'W']
    sy16 = sorted(set(c for v in list(scr_tr.values()) + wko for c in v if '가' <= c <= '힣'))
    kfnt = file('/KANJI.FNT')
    m16 = kr16.assign(sy16, bytes(kfnt), freq)
    kr16.put_font(kfnt, m16)
    n_scr = kr16.rewrite_scripts(file, scr_tr, m16, err)
    # 실행 파일 전각 UI — ui.tsv(W) + ui_extra.tsv 자리에 제자리(KO 의 {09} 등 제어 바이트는 KO 에 적힌 그대로)
    n_ui = 0
    for p, off, n, kind, jp, ko in uit:
        if kind != 'W':
            continue
        d = file(p)
        if bytes(d[off:off + n]) != jp_bytes(jp) or d[off + n] != 0:
            err.append('%s@%d UI 원문 불일치 %s' % (p, off, jp)); continue
        b = kr16.encode(ko, m16)
        if len(b) > n:
            err.append('%s@%d UI 예산 %d < %d: %s' % (p, off, n, len(b), ko)); continue
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
    # --- 2.9) 경험치 배율 (--exp 2|3|4|5, 조우 감소판과 함께 — 사용자 제안 2026-09-26) -----------
    #   /2(전투, 0x06018000) 0x06039902: r12 = 적 경험치 합 ÷ 받는 인원(0x0605AB44 = 범용 나눗셈) →
    #   원래 «0 이면 1»(tst r12 / bf / mov #1,r12) 자리를 곱셈으로. r12 는 표시(«%dの経験値を得た»)와
    #   실제 지급(0x0603609C, 파티원마다) 둘 다에 쓰인다. 9,999,999 상한 검사는 뒤에 그대로.
    #   ⛔치트 불가 — 같은 주소가 필드(/1)에선 실제 코드.
    if '--exp' in sys.argv:
        k = sys.argv[sys.argv.index('--exp') + 1]
        EXP = {'2': '3ccc00090009', '3': '61c33c1c3c1c', '4': '4c0800090009', '5': '61c34c083c1c'}
        d = file('/2')
        if bytes(d[137476:137482]) != bytes.fromhex('2cc88b00ec01'):
            err.append('/2@137476 경험치 코드 원문 불일치')
        else:
            d[137476:137482] = bytes.fromhex(EXP[k])
            print('경험치 ×%s' % k)
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
