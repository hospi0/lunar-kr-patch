# -*- coding: utf-8 -*-
r"""UI 번역 조각(«번호<TAB>KO» 줄들) → work/text/ui.tsv 의 KO 열(6열)에 넣기
  python tools/uiapply.py 조각.tsv [...]
  KO 는 쓴 그대로 넣는다(전각·반각 변환 없음 — 예산이 바이트 단위라 직접 고른다). «=» 는 원문 그대로.
  같은 종류(W/H)·같은 JP(앞 {09} 빼고) 인 빈 칸은 이미 넣은 KO 로 채운다({09} 는 그 칸의 JP 를 따른다).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(os.path.dirname(HERE), 'work', 'text', 'ui.tsv')
lines = open(P, encoding='utf-8').read().split('\n')
rows = [l.split('\t') for l in lines]
idx = {r[0]: i for i, r in enumerate(rows) if r and r[0] and not r[0].startswith('#')}
new = {}
sys.stdout.reconfigure(encoding='utf-8')
for fn in sys.argv[1:]:
    for l in open(fn, encoding='utf-8'):
        l = l.rstrip('\n')
        if l.strip():
            k, ko = l.split('\t', 1); new[k] = ko
for k, ko in new.items():
    r = rows[idx[k]]
    while len(r) < 6: r.append('')
    r[5] = ko
# 같은 JP(앞 {09} 빼고) 에 이미 넣은 KO 가 있으면 빈 칸 채우기({09} 는 JP 쪽을 따른다)
strip = lambda s: s[4:] if s.startswith('{09}') else s
by = {}
for r in rows:
    if len(r) > 5 and r[5] and r[5] != '=' and not r[0].startswith('#'):
        by.setdefault((r[3], strip(r[4])), strip(r[5]))
auto = 0
for r in rows:
    if len(r) > 4 and r[0] and not r[0].startswith('#') and (len(r) < 6 or not r[5]):
        ko = by.get((r[3], strip(r[4])))
        if ko:
            while len(r) < 6: r.append('')
            r[5] = ('{09}' if r[4].startswith('{09}') else '') + ko; auto += 1
open(P, 'w', encoding='utf-8').write('\n'.join('\t'.join(r) for r in rows))
print('넣음', len(new), '자동', auto)
