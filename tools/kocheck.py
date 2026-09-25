# -*- coding: utf-8 -*-
r"""번역(KO) 검사 — work/text/scr.tsv · ui.tsv
  대사(scr):
   · 제어 순서: {08}(대기)·{0c}(새 쪽)의 순서·개수가 JP 와 같아야 한다({0d} 연출 쉼은 자유)
   · 한 줄 ≤ 16칸(원문에 더 긴 줄이 있으면 그 길이까지. 전각 기준, 한글·부호·빈칸 모두 1칸), 쪽({0c} 사이) 줄 수 ≤ JP 의 같은 쪽 줄 수(최소 3)
   · 글자: 한글 음절 + JP 에 쓰인 부호만. ♥ = KANJI.FNT 9E42(曖) 자리 그림
  UI:
   · W(전각) = 예산 바이트 ≥ 2×글자 수, H(반각 8×8) = 예산 ≥ 글자 수(1바이트 칸)
  python tools/kocheck.py [S03 ...]      # 접두사로 거르기, 끝에 진행률·한글 음절 수
"""
import os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
TXT = os.path.join(ROOT, 'work', 'text')
WIDTH = 16
PUNCT = set('　 ！？…‥、。・「」『』（）～ー―－―：；“”’ ♪♥●○×☆★／※＋＝％＆＊０１２３４５６７８９!?.,-~') | set(chr(c) for c in range(0xFF21, 0xFF3B)) | set(chr(c) for c in range(0xFF41, 0xFF5B))   # 전각 Ａ‥Ｚ ａ‥ｚ


def load(name):
    rows = []
    for l in open(os.path.join(TXT, name), encoding='utf-8'):
        c = l.rstrip('\n').split('\t')
        if c[0].startswith('#'):
            continue
        rows.append(c)
    return rows


def ctl(s):
    return re.findall(r'\{0[8c]\}', s)


def pages(s):
    """{0c} 로 쪽을 나누고 각 쪽의 줄(제어 표기 뺀 글)"""
    return [[re.sub(r'\{..\}', '', x) for x in pg.split('\\n')] for pg in s.split('{0c}')]


def check_scr(pref):
    bad, done, tot = [], 0, 0
    for r in load('scr.tsv'):
        if pref and not r[0].startswith(tuple(pref)):
            continue
        tot += 1
        jp, ko = r[2], (r[3] if len(r) > 3 else '')
        if not ko:
            continue
        done += 1
        if ko == '=':                               # 원문 그대로 둠(개발용 이름 등)
            continue
        if ctl(jp) != ctl(ko):
            bad.append((r[0], '제어 %s ≠ %s' % (''.join(ctl(jp)), ''.join(ctl(ko)))))
        pj, pk = pages(jp), pages(ko)
        wmax = max([WIDTH] + [len(x) for pg in pj for x in pg])   # 원문부터 16칸을 넘는 줄(줄바꿈 빠뜨림)은 그 길이까지
        for i, pg in enumerate(pk):
            for ln in pg:
                if len(ln) > wmax:
                    bad.append((r[0], '%d칸: %s' % (len(ln), ln)))
            lim = max(3, len(pj[i]) if i < len(pj) else 3)
            if len([x for x in pg if x]) > lim:
                bad.append((r[0], '쪽%d 줄 %d > %d' % (i, len(pg), lim)))
        for ch in re.sub(r'\{..\}|\\n', '', ko):
            if not ('가' <= ch <= '힣' or ch in PUNCT):
                bad.append((r[0], '글자 %r' % ch))
    return bad, done, tot


def check_ui():
    bad, done, tot = [], 0, 0
    for r in load('ui.tsv'):
        tot += 1
        ko = r[5] if len(r) > 5 else ''
        if not ko:
            continue
        done += 1
        body = re.sub(r'\{..\}', '', ko)
        n = len(re.findall(r'\{..\}', ko)) + (2 if r[3] == 'W' else 1) * len(body)
        if n > int(r[2]):
            bad.append((r[0], '%s 예산 %s < %d: %s' % (r[1], r[2], n, ko)))
    return bad, done, tot


def syllables():
    s = set()
    for r in load('scr.tsv'):
        if len(r) > 3:
            s |= set(ch for ch in r[3] if '가' <= ch <= '힣')
    for r in load('ui.tsv'):
        if len(r) > 5 and r[3] == 'W':
            s |= set(ch for ch in r[5] if '가' <= ch <= '힣')
    return s


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    pref = sys.argv[1:]
    b1, d1, t1 = check_scr(pref)
    b2, d2, t2 = check_ui() if not pref else ([], 0, 0)
    for k, m in b1 + b2:
        print(k, m)
    print('대사 %d/%d · UI %d/%d · 오류 %d · 한글 음절 %d' % (d1, t1, d2, t2, len(b1 + b2), len(syllables())))
