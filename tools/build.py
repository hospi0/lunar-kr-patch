# -*- coding: utf-8 -*-
r"""마법학원 루나! 한글 빌더 (1차: 8×8 반각 이름·장 제목 카드)
  1) ASCII.FNT(8×8, 글리프 번호 = 코드) — 한글 음절을 0x80‥0xFD 칸에 갈무리7 로 그린다(가나 칸 전부 덮음).
  2) 실행 파일 /1·/2 의 반각 가나 문자열(인물 이름·마법 목록 이름, work/text/ui.tsv 종류 H) → work/text/half_ko.tsv 번역을 제자리에(원문 바이트 안, 남으면 NUL).
  3) CHAPTER.FLD ← tools/chapter_kr.py (장 제목 글씨 시트 LZSS 되압축).
  ⇒ Track 01 사본에 파일 크기 그대로 덮어쓰고 바뀐 섹터만 EDC/ECC 재계산 → work/out/
  (대사·KANJI.FNT 는 본문 번역이 오면 붙인다)
  python tools/build.py [--write [--install]]   (기본 = 예행 · --install = F: 트랙 1 교체)
"""
import struct, collections, glob, hashlib, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
from cdrom_ecc import recalc_sector
import scr, bdf, chapter_kr, kr16, ramlabel, options

GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
DEFAULT_ENC, DEFAULT_EXP = '10', '3'              # 인수 없이 빌드하면 조우 1/10 · 경험치 ×3 (사용자 결정 2026-09-26). 배포 기본은 make_dist 가 --enc 1 --exp 1
HALF_CODES = list(range(0x80, 0xFE))          # 한글 8×8 칸(0xFE·0xFF 는 피함)
OUT = os.path.join(ROOT, 'work', 'out')
INSTALL = r'F:\hospi\roms\ss roms\Mahou Gakuen Lunar! (Japan) (2M)\Mahou Gakuen Lunar! (Japan) (2M) (Track 01).bin'   # --install


def dlg_fix(ko):
    """대사 KO 빌드 전 손질: 반각(1바이트) 글자 → 전각. ★대사창은 모든 글자를 2바이트로 읽는다 —
    반각 빈칸 하나에 그 뒤 바이트 짝이 어긋나 글자가 빈칸으로 나오고 줄바꿈이 먹힌다(실기 2026-09-26 «뭐야 ··· 작년보다 ··· 줄었잖/아»).
    제어 표기({xx}·\\n)는 그대로."""
    out = []
    for tok in re.split(r'(\{[0-9a-f]{2}\}|\\n)', ko):
        if tok.startswith('{') or tok == '\\n':
            out.append(tok); continue
        out.append(''.join('　' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in tok))
    return ''.join(out)


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
    kr16.put_punct(kfnt)                           # 일본식 … 、 。 글리프 → 한국식
    # 대사 글자 검사: 한글이 아닌 2바이트 글자는 KANJI.FNT 에 있어야 하고, 1바이트(ASCII)는 없어야 한다
    fcodes = set(kr16.font_codes(bytes(kfnt))[0]) | {b'\x9e\x42', b'\x81\x40'}     # 曖(♥) · 전각 빈칸(글리프 표 맨 앞 칸)
    jpline = {}
    for ln in open(os.path.join(ROOT, 'work', 'text', 'scr.tsv'), encoding='utf-8'):
        r = ln.rstrip('\n').split('\t')
        if len(r) >= 3:
            jpline[r[0]] = set(dlg_fix(r[2]))
    bad = collections.Counter()
    for k, v in scr_tr.items():
        for ch in re.sub(r'\{[0-9a-f]{2}\}|\\n', '', v):
            if ch in m16 or ch == '♥' or ch in jpline.get(k, ()):      # 원문 그 줄에도 있는 글자 = 원문과 같은 동작
                continue
            if ord(ch) < 0x80:
                bad['반각 %r' % ch] += 1
            else:
                try:
                    if ch.encode('cp932') not in fcodes:
                        bad['글꼴에 없음 %r' % ch] += 1
                except UnicodeEncodeError:
                    bad['SJIS 에 없음 %r' % ch] += 1
    for kk, n in bad.items():
        err.append('대사 %s ×%d' % (kk, n))
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
    # --- 2.8) 조우 간격 (사용자 요청 2026-09-26) --------------------------------------------------
    #   /1 0x06018338‥: 카운터(0x06052844) = 난수(r4=6) + 5 → 걸음마다 −1, 0 이면 전투(0x0602909C). 평균 약 8걸음.
    #   --enc N(0 전투 없음 · 1 원본 · 2‥20 평균 8N걸음, tools/options.py) · tenth(예전 1/10 = 난수 64 + 70) · always(실험: 매 걸음)
    enc = sys.argv[sys.argv.index('--enc') + 1] if '--enc' in sys.argv else DEFAULT_ENC
    OLD = {'tenth': [('/1', 830, 'e406', 'e440'), ('/1', 834, '7105', '7146')],
           'always': [('/1', 830, 'e406', 'e400'), ('/1', 834, '7105', '7100')], 'never': options.enc_patch(0)}
    pats = []
    if enc:
        pats += OLD[enc] if enc in OLD else options.enc_patch(int(enc))
        print('조우 패치:', enc)
    # --- 2.9) 경험치 배율 --exp N(1‥10) — tools/options.py -------------------------------------------
    #   /2(전투, 0x06018000) 0x06039902: r12 = 적 경험치 합 ÷ 받는 인원 → «0 이면 1» 자리를 곱셈으로.
    #   r12 는 표시(«%dの経験値を得た»)와 실제 지급(0x0603609C) 둘 다에 쓰인다. 9,999,999 상한 검사는 뒤에 그대로.
    #   ⛔치트 불가 — 같은 주소가 필드(/1)에선 실제 코드.
    k = int(sys.argv[sys.argv.index('--exp') + 1] if '--exp' in sys.argv else DEFAULT_EXP)
    pats += options.exp_patch(k)
    print('경험치 ×%d' % k)
    for fp, off, old, new in pats:
        d = file(fp)
        n = len(old) // 2
        if bytes(d[off:off + n]) != bytes.fromhex(old):
            err.append('%s@%d 코드 원문 불일치' % (fp, off)); continue
        d[off:off + n] = bytes.fromhex(new)
    # --- 2.95) 전투 «%dの経験値を得た» 옮기기 ------------------------------------------------------
    #   전투 창 상자 폭 = 문자열 바이트 수 → 반각 빈칸도 16px 로 그려 상자보다 글자가 길어진다 → 빈칸은 전각.
    #   «의　경험치　획득»(16 B) 이 원래 자리(15 B)에 안 들어가 바로 앞 «THISISDUMMYSPACE»(16 B, 표 5번 = 안 쓰는 빈 칸)
    #   자리에 쓰고(ui_extra), 메시지 표 13번(/2@294344) 포인터를 그리로 돌린다.
    d = file('/2')
    if struct.unpack_from('>I', d, 294344)[0] != 0x060325D4:
        err.append('/2@294344 경험치 문구 포인터 원문 불일치')
    else:
        struct.pack_into('>I', d, 294344, 0x06032540)
    # --- 3) 장 제목 카드 ----------------------------------------------------
    chap, _, clen = chapter_kr.build()
    d = file('/CHAPTER.FLD')
    assert len(chap) == len(d)
    d[:] = chap
    # --- 4) 저장 화면 «本体RAM»·«カートリッジRAM» 그림 (MISC.FLD·EFCT.FLD 두 벌) ------
    for fp, si in ramlabel.SHEETS:
        ramlabel.apply(file(fp), si)

    # --- 5) 동영상(MSLM.FLD) — 오프닝 가사 구역 22 = work/kr/op22.cpk (tools/opening.py → opening_enc.py),
    #        대사 자막 구역 NN = work/kr/mvNN.cpk (tools/moviesub.py NN --encode). 크기는 다음 구역 전까지.
    movs = []
    op = os.path.join(ROOT, 'work', 'kr', 'op22.cpk')
    if not os.path.exists(op):
        err.append('work/kr/op22.cpk 없음 — tools/opening.py, tools/opening_enc.py 먼저')
    else:
        movs.append((22, op))
    for mp in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', 'mv[0-9][0-9].cpk'))):
        movs.append((int(os.path.basename(mp)[2:4]), mp))
    if movs:
        d = file('/MSLM.FLD')
        secs = scr.sections(bytes(d[:0x800]))
        for si, mp in movs:
            cpk = open(mp, 'rb').read()
            o, s = secs[si]
            room = secs[si + 1][0] - o
            if bytes(d[o:o + 4]) != b'FILM' or len(cpk) > room:
                err.append('MSLM.FLD 구역 %d 자리 불일치/초과 %d > %d' % (si, len(cpk), room)); continue
            d[o:o + room] = cpk + bytes([0xFF]) * (room - len(cpk))
            struct.pack_into('>I', d, si * 8 + 4, len(cpk))
        print('동영상 %d편 교체: %s' % (len(movs), ' '.join('%02d' % si for si, _ in movs)))
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
