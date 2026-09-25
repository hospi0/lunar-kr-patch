# -*- coding: utf-8 -*-
r"""번역 조각 파일(«번호<TAB>KO» 줄들) → work/text/scr.tsv 의 KO 열에 넣기
  python tools/koapply.py 조각.tsv [...]
  숫자·영문은 전각으로 바꾼다. 번호가 없으면 오류. 같은 JP 가 다른 번호에도 있고 그쪽 KO 가 비었으면 같이 채운다(중복 대사).
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
P = os.path.join(ROOT, 'work', 'text', 'scr.tsv')



def wide(s):
    """숫자·영문 → 전각({0d} 같은 제어 표기와 \\n 은 그대로)"""
    return re.sub(r'\{[0-9a-f]{2}\}|\\n|[0-9A-Za-z]', lambda m: m.group() if len(m.group()) > 1 else chr(ord(m.group()) + 0xFEE0), s)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    lines = open(P, encoding='utf-8').read().split('\n')
    rows = [l.split('\t') for l in lines]
    idx = {r[0]: i for i, r in enumerate(rows) if r and r[0] and not r[0].startswith('#')}
    new = {}
    for fn in sys.argv[1:]:
        for l in open(fn, encoding='utf-8'):
            l = l.rstrip('\n')
            if not l.strip() or l.startswith('#'):
                continue
            k, ko = l.split('\t', 1)
            ko = wide(ko)
            if k not in idx:
                sys.exit('번호 없음: %s' % k)
            new[k] = ko
    byjp = {}
    for k, ko in new.items():
        rows[idx[k]][3] = ko
        byjp.setdefault(rows[idx[k]][2], ko)
    dup = 0
    for r in rows:
        if len(r) > 3 and not r[0].startswith('#') and not r[3] and r[2] in byjp:
            r[3] = byjp[r[2]]; dup += 1
    open(P, 'w', encoding='utf-8').write('\n'.join('\t'.join(r) for r in rows))
    print('넣음 %d · 중복 대사 자동 %d' % (len(new), dup))
