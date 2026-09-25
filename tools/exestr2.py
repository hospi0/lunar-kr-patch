# -*- coding: utf-8 -*-
r"""실행 파일 UI 추출 보강 — 앞 바이트가 NUL 이 아닌 문자열(코드 사이에 박힌 것, 예: /1@103204 取得アイテム)까지.
  NUL 로 끝나는 모든 자리에서 거꾸로 올라가며 «온전한 SJIS + 모든 글자가 KANJI.FNT 에 있음 + 가나·한자 2자 이상»인
  가장 긴 문자열을 잡는다(앞 제어 바이트 09 등은 포함하지 않음 — 빌더가 원본 바이트로 대조).
  python tools/exestr2.py    → 기존 work/text/ui.tsv 에 없는 것만 보고 + work/text/ui_extra.tsv
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso
import scr, exestr

JPC = re.compile(r'[ぁ-んァ-ヶ一-龯]')


def ok_char(c):
    return c in exestr.FONT or c in ' 　' or ('0' <= c <= '9') or ('A' <= c <= 'Z') or ('a' <= c <= 'z') or c in '!?.,:%/-+()'


def strings(d):
    out = []
    for m in re.finditer(rb'\x00', d):
        j = m.start()
        i = j                                    # 글자 단위로 거꾸로: 2바이트 글꼴 글자 → 2칸, ASCII → 1칸, 아니면 멈춤
        while i > 0 and j - i < 200:
            two = d[i - 2:i] if i >= 2 else b''
            c2 = None
            if len(two) == 2 and (0x81 <= two[0] <= 0x9F or 0xE0 <= two[0] <= 0xEF):
                try:
                    c2 = two.decode('cp932')
                except UnicodeDecodeError:
                    c2 = None
            if c2 and ok_char(c2):
                i -= 2
            elif 0x20 <= d[i - 1] < 0x7F and ok_char(chr(d[i - 1])):
                i -= 1
            else:
                break
        s = d[i:j].decode('cp932', 'replace')
        s = s.lstrip(' ')
        i = j - len(s.encode('cp932', 'replace'))
        if len(JPC.findall(s)) >= 2:
            out.append((i, j - i, s))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    iso = Iso(scr.TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    spans = {}                                   # ui.tsv 가 이미 덮는 바이트 범위
    for ln in open(os.path.join(ROOT, 'work', 'text', 'ui.tsv'), encoding='utf-8'):
        if not ln.startswith('#'):
            r = ln.split('\t'); p, o = r[1].split('@')
            spans.setdefault(p, []).append((int(o), int(o) + int(r[2])))
    new = []
    for p in exestr.EXES:
        d = iso.read(ent[p][1], ent[p][2])
        for off, n, s in strings(d):
            if any(a < off + n and off < b for a, b in spans.get(p, [])):
                continue                          # 기존 항목과 겹침(같은 문자열의 다른 자르기)
            if re.search(r'[a-z]', s.replace('%s', '')):
                continue                          # «詳hも» 같은 코드 잡음
            new.append((p, off, n, s))
    with open(os.path.join(ROOT, 'work', 'text', 'ui_extra.tsv'), 'w', encoding='utf-8') as f:
        f.write('#위치\t예산\tJP\tKO — ui.tsv 에서 빠졌던 것(앞 바이트가 NUL 아님)\n')
        for p, off, n, s in new:
            f.write('%s@%d\t%d\t%s\t\n' % (p, off, n, s))
    print('새로 찾은 문자열 %d' % len(new))
    for x in new[:80]:
        print(' ', x[0], x[1], x[2], x[3])
