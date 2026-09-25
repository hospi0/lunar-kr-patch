# -*- coding: utf-8 -*-
r"""대사 스크립트(S00‥S12.FLD) 구조
  파일 머리 = 구역 표 (u32 BE 오프셋·크기 쌍, 0xFFFFFFFF 까지; 같은 구역을 두 번 가리키기도 하고 0,0 빈칸도 있다).
  구역(장면) 머리 안에 «(항목 수 N, 표 위치 T)» u32 쌍 → 구역+T 에 u32 BE 주소 N 개(구역 기준, 증가).
  주소 i 의 대사 = [e[i], e[i+1]) , 대사 끝은 NUL(대개 «08 00» = 대기+끝, 선택지 등은 NUL 만). 마지막 항목 = 블록 끝(뒤에 «xxx.msg» 이름).
  ⇒ 대사는 번호 → 주소 표로 부른다 → 길이를 바꾸면 표만 다시 쓰면 된다(구역 크기·다음 구역 틈 안에서).
  python tools/scr.py            # 전수 조사 + work/text/scr.tsv 추출
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iso9660 import Iso

TRACK1 = r'C:\claude\roms\ss\Mahou Gakuen Lunar! (Japan) (2M)\Mahou Gakuen Lunar! (Japan) (2M) (Track 01).bin'
FILES = ['/S%02d.FLD' % i for i in range(13)]


def sections(d):
    out, k = [], 0
    while k < 0x800:
        o, s = struct.unpack_from('>II', d, k)
        if o == 0xFFFFFFFF:
            break
        out.append((o, s)); k += 8
    return out


def find_table(d, base, size):
    """구역 머리에서 (N, T) 쌍을 찾는다 → (N, T, 주소 목록) 또는 None"""
    for k in range(0, min(0x400, size - 8), 2):
        n, t = struct.unpack_from('>II', d, base + k)
        if not (2 <= n <= 6000 and 0 < t and t + 4 * n <= size):
            continue
        e = [struct.unpack_from('>I', d, base + t + 4 * i)[0] for i in range(n)]
        if any(b <= a for a, b in zip(e, e[1:])) or e[-1] > size:
            continue
        # 첫 항목이 «N10 M118 Ivent Message» 같은 이름 문자열인 구역도 있다 → 앞 3 항목 중 하나라도 SJIS 로 시작하면
        heads = b''.join(d[base + x:base + x + 8] for x in e[:3])
        if all(d[base + e[i + 1] - 1] == 0 for i in range(n - 1)) and re.search(rb'[\x81-\x9f\xe0-\xef][\x40-\xfc]', heads):
            return n, t, e
    # 대사가 하나뿐인 구역: (1, T) — 표에 끝 항목이 없다 → 끝은 NUL. ★e 의 끝 항목은 가상(표에 쓰지 말 것)
    for k in range(0, min(0x400, size - 8), 2):
        n, t = struct.unpack_from('>II', d, base + k)
        if n != 1 or not (0 < t and t + 4 <= size):
            continue
        e0 = struct.unpack_from('>I', d, base + t)[0]
        if not (0x200 <= e0 < size) or not re.match(rb'[\x0c\x0a]?[\x81-\x9f\xe0-\xef][\x40-\xfc]', d[base + e0:base + e0 + 4]):
            continue
        end = d.index(b'\x00', base + e0) - base + 1
        return 1, t, [e0, end]
    return None


def esc(b):
    """대사 바이트 → 표기(가나·한자는 그대로, 제어는 {xx}, 줄바꿈 \n, CR 은 {0d})"""
    out, i = [], 0
    while i < len(b):
        x = b[i]
        if (0x81 <= x <= 0x9F or 0xE0 <= x <= 0xEF) and i + 1 < len(b):
            out.append(b[i:i + 2].decode('cp932', 'backslashreplace')); i += 2
        elif x == 0x0A:
            out.append('\\n'); i += 1
        elif 0x20 <= x < 0x7F and x != 0x7B and x != 0x7D:
            out.append(chr(x)); i += 1
        else:
            out.append('{%02x}' % x); i += 1
    return ''.join(out)


def scan(iso=None):
    iso = iso or Iso(TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    res = []
    for p in FILES:
        d = iso.read(ent[p][1], ent[p][2])
        seen = set()
        for si, (o, s) in enumerate(sections(d)):
            if o == 0 or o in seen:
                continue
            seen.add(o)
            t = find_table(d, o, s)
            res.append((p, si, o, s, t))
    return res


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    iso = Iso(TRACK1)
    ent = {f[0]: f for f in iso.walk()}
    rows = []
    miss = []
    for p, si, o, s, t in scan(iso):
        if not t:
            miss.append((p, si, hex(o), hex(s))); continue
        n, tb, e = t
        d = iso.read(ent[p][1], ent[p][2])
        for i in range(len(e) - 1):
            b = d[o + e[i]:o + e[i + 1] - 1]          # 끝 NUL 만 뺀다({08} 대기는 대사 안에 남김)
            rows.append(('%s:%d:%d' % (p[1:4], si, i), len(b), esc(b)))
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    out = os.path.join(ROOT, 'work', 'text', 'scr.tsv')
    ko = {}                                             # 다시 뽑아도 번역(KO)은 (번호, JP) 가 같으면 살린다
    if os.path.exists(out):
        for l in open(out, encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            if len(c) >= 4 and not c[0].startswith('#'):
                ko[(c[0], c[2])] = c[3]
    with open(out, 'w', encoding='utf-8') as f:
        f.write('#번호\t바이트\tJP\tKO\n')
        for r in rows:
            f.write('%s\t%d\t%s\t%s\n' % (r + (ko.get((r[0], r[2]), ''),)))
    print('대사 %d줄 · 표 없는 구역 %d' % (len(rows), len(miss)))
    for m in miss:
        print('  표 없음', *m)
