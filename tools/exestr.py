# -*- coding: utf-8 -*-
r"""실행 파일(/0‥/4) UI 문자열 추출 → work/text/ui.tsv
  인정 기준: 앞 바이트 NUL(또는 파일 시작), 뒤 NUL 인 문자열 중
   (a) 전각 SJIS 로 온전히 풀리고 가나·한자·전각 영숫자가 2자 이상
   (b) 1바이트 가나(반각 가타카나 0xA1‥0xDF, 탁점 포함) 2자 이상 + ASCII 만 섞인 것 — 8×8 글꼴(ASCII.FNT)
  열: 번호 · 파일@오프셋 · 예산(원문 바이트) · 종류(W=전각 16×16 / H=반각 8×8) · JP · KO
  python tools/exestr.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso
import scr

EXES = ['/0', '/1', '/2', '/3', '/4']
JPW = re.compile(r'[ぁ-んァ-ヶー一-龯０-９Ａ-Ｚａ-ｚ]')
_f = open(os.path.join(ROOT, 'work', 'KANJI.FNT'), 'rb').read()
FONT = set(_f[i:i + 2].decode('cp932', 'replace') for i in range(4, int.from_bytes(_f[:2], 'big'), 2))
HALF_EXES = ('/1', '/2')      # 1바이트 가나 문자열이 실제로 있는 곳(나머지는 2자 코드 잡음)


def wide(b):
    try:
        s = b.decode('cp932')
    except UnicodeDecodeError:
        return None
    if len(JPW.findall(s)) < 2:
        return None
    if any(ord(c) >= 0x80 and c not in FONT for c in s):      # 게임 글꼴에 없는 글자 = 화면에 못 나옴 = 코드 잡음
        return None
    # 반각 가나가 섞인 전각 문자열은 코드 잡음일 가능성이 높다
    if re.search(r'[\uff61-\uff9f]', s) or re.search(r'[\x00-\x08\x0b-\x1f\x7f]', s):
        return None
    return s


def half(b):
    if not re.fullmatch(rb'[\xa1-\xdf]+', b):                 # 순수 반각 가나만(«Aﾍﾍe» 같은 코드 잡음 제외)
        return None
    if len(re.findall(rb'[\xa6-\xdd]', b)) < 2:
        return None
    return b.decode('cp932')


def extract():
    iso = Iso(scr.TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    rows = []
    for p in EXES:
        d = iso.read(ent[p][1], ent[p][2])
        for m in re.finditer(rb'(?<=\x00)[^\x00]{2,400}(?=\x00)', d):
            b, o = m.group(), m.start()
            s = wide(b)
            kind = 'W'
            if s is None:
                lead = len(b) - len(b.lstrip(bytes(range(1, 0x20))))      # 앞 제어 바이트(09 등)는 문자열 밖
                b, o = b[lead:], o + lead
                s = half(b) if p in HALF_EXES else None; kind = 'H'
            if s is None:
                continue
            s = re.sub(r'[\x00-\x1f]', lambda c: '\\n' if c.group() == '\n' else '{%02x}' % ord(c.group()), s)
            rows.append((p, o, len(b), kind, s))
    return rows


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rows = extract()
    out = os.path.join(ROOT, 'work', 'text', 'ui.tsv')
    ko = {}                                             # 다시 뽑아도 번역(KO)은 (위치, JP) 가 같으면 살린다
    if os.path.exists(out):
        for l in open(out, encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            if len(c) >= 6 and not c[0].startswith('#'):
                ko[(c[1], c[4])] = c[5]
    with open(out, 'w', encoding='utf-8') as f:
        f.write('#번호\t위치\t예산\t종류\tJP\tKO\n')
        for k, (p, o, n, kind, s) in enumerate(rows):
            w = '%s@%d' % (p, o)
            f.write('%d\t%s\t%d\t%s\t%s\t%s\n' % (k, w, n, kind, s, ko.get((w, s), '')))
    import collections
    c = collections.Counter((r[0], r[3]) for r in rows)
    print('UI 문자열 %d' % len(rows), dict(c))
