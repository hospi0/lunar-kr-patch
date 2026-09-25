# -*- coding: utf-8 -*-
r"""본문 16×16 글꼴(KANJI.FNT) 한글 + 대사 블록 되쓰기
  KANJI.FNT = [u16 코드 목록 끝][20 20][SJIS 코드 1,570개 오름차순][16×16 1bpp 32 B씩 — ★맨 앞 1칸(전각 공백) + 코드 순서 = 순번+1]
  → 한글 음절에 «한자 코드»를 빌려(대사에 드물게 쓰인 것부터) 그 칸 글리프를 한글로 덮는다.
     ♥(曖 9E42) 등 그림 칸은 제외. 배정은 work/kr/charmap.tsv 를 이어받는다(세이브스테이트 보호).
  글리프: 갈무리14(13×14) 를 가로로 1px 굵혀 16×16 칸 1‥14행에(원본 획 2px 에 맞춤).
  대사: 구역 머리 (N, T) 주소 표로 부른다(tools/scr.py) → 블록을 새로 짜고 표만 고친다.
       블록 뒤 꼬리(«N00m144.msg» 이름 등)는 그대로 뒤에 붙이고, 구역 크기(파일 머리)·다음 구역까지의 자리를 검사.
"""
import collections, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, scr

GALMURI14 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.bdf'
KEEP = {'曖'}                    # 그림 칸(♥) — 도너로 쓰지 않는다
CHARMAP = os.path.join(ROOT, 'work', 'kr', 'charmap.tsv')


def font_codes(fnt):
    end = struct.unpack_from('>H', fnt, 0)[0]
    return [bytes(fnt[i:i + 2]) for i in range(4, end, 2)], end


def donors(fnt, freq):
    codes, _ = font_codes(fnt)
    c = [b for b in codes if b[0] >= 0x88 and b.decode('cp932', 'replace') not in KEEP]
    return sorted(c, key=lambda b: (freq[b.decode('cp932', 'replace')], b))


def assign(sylls, fnt, freq):
    prev = {}
    if os.path.exists(CHARMAP):
        for ln in open(CHARMAP, encoding='utf-8'):
            r = ln.rstrip('\n').split('\t')
            if len(r) >= 2:
                prev[r[0]] = bytes.fromhex(r[1])
    cand = donors(fnt, freq)
    cs = set(cand)
    m = {s: prev[s] for s in sylls if s in prev and prev[s] in cs}
    used = set(m.values())
    free = iter(b for b in cand if b not in used)
    for s in sylls:
        if s not in m:
            m[s] = next(free)
    os.makedirs(os.path.dirname(CHARMAP), exist_ok=True)
    with open(CHARMAP, 'w', encoding='utf-8') as f:
        for s, b in m.items():
            f.write('%s\t%s\t%s\n' % (s, b.hex(), b.decode('cp932', 'replace')))
    return m


def glyph16(F, ch):
    pts, _ = F.draw(ch)
    g = [0] * 16
    for x, y in pts:
        yy = y - 3                          # 갈무리14 y 4‥17 → 1‥14
        for xx in (x, x + 1):               # 가로 1px 굵게(갈무리14 는 x 0‥14 까지 쓴다)
            assert 0 <= yy < 16 and 0 <= xx < 16, (ch, x, y)
            g[yy] |= 0x8000 >> xx
    return b''.join(struct.pack('>H', v) for v in g)


def put_font(fnt, m):
    codes, end = font_codes(fnt)
    F = bdf.Font(GALMURI14)
    idx = {b: i for i, b in enumerate(codes)}
    for s, b in m.items():
        k = idx[b] + 1          # ★글리프 표 맨 앞에 목록에 없는 칸이 하나 더 있다(전각 공백 자리) → 목록 순번 +1 (실기 2026-09-26 «뀨?»)
        fnt[end + 32 * k:end + 32 * k + 32] = glyph16(F, s)


def encode(ko, m):
    """KO 표기 → 바이트(\n, {xx}, 한글=도너 2B, ASCII 1B, 그 밖 cp932)"""
    out = bytearray()
    i = 0
    while i < len(ko):
        if ko.startswith('\\n', i):
            out.append(0x0A); i += 2; continue
        mm = re.match(r'\{([0-9a-f]{2})\}', ko[i:])
        if mm:
            out.append(int(mm.group(1), 16)); i += 4; continue
        ch = ko[i]
        if ch == '♥':
            ch = '曖'                        # ♥ = 원문 曖(9E42) 자리에 그린 하트
        if ch in m:
            out += m[ch]
        elif ord(ch) < 0x80:
            out.append(ord(ch))
        else:
            out += ch.encode('cp932')
        i += 1
    return bytes(out)


def rewrite_scripts(file, tr, m, err):
    """tr = {'S00:0:0': KO} → 해당 구역 메시지 블록을 새로 짠다. file(p) = bytearray"""
    by = collections.defaultdict(dict)
    for k, v in tr.items():
        f, si, i = k.split(':')
        by[('/%s.FLD' % f, int(si))][int(i)] = v
    n_ok = 0
    for (p, si), msgs in by.items():
        d = file(p)
        secs = scr.sections(bytes(d))
        o, s = secs[si]
        t = scr.find_table(bytes(d), o, s)
        if not t:
            err.append('%s 구역 %d 주소 표 없음' % (p, si)); continue
        n, tb, e = t
        virtual = (n == 1)
        cnt = len(e) - 1
        old = [bytes(d[o + e[i]:o + e[i + 1]]) for i in range(cnt)]      # 끝 NUL 포함
        new = []
        for i in range(cnt):
            if i in msgs:
                new.append(encode(msgs[i], m) + b'\x00'); n_ok += 1
            else:
                new.append(old[i])
        tail_start = e[-1]
        nxt = min([so for so, ss in secs if so > o] + [len(d)])
        if virtual:
            tail = b''                                   # 대사 하나뿐 — 끝 NUL 뒤는 건드리지 않는다
            tail_end = e[-1]
        else:
            tail = bytes(d[o + tail_start:o + s])        # «xxx.msg» 이름 등 구역 끝까지
            tail_end = s
        blk = b''.join(new)
        new_end = e[0] + len(blk)
        total = new_end + len(tail)
        if not virtual and o + total > nxt:
            err.append('%s 구역 %d 넘침 %d > %d' % (p, si, total, nxt - o)); continue
        if virtual and new_end > tail_end:
            err.append('%s 구역 %d(대사 1개) 원문보다 길다 %d > %d' % (p, si, new_end - e[0], tail_end - e[0])); continue
        pos = e[0]
        for i in range(cnt):
            struct.pack_into('>I', d, o + tb + 4 * i, pos)
            pos += len(new[i])
        if not virtual:
            struct.pack_into('>I', d, o + tb + 4 * cnt, pos)          # 끝 항목 = 꼬리 시작
            d[o + e[0]:o + total] = blk + tail
            if total < s:
                d[o + total:o + s] = b'\xff' * (s - total)
            # 파일 머리의 구역 크기(같은 오프셋을 가리키는 항목 모두)
            for k in range(0, 0x800, 8):
                so, ss = struct.unpack_from('>II', d, k)
                if so == 0xFFFFFFFF:
                    break
                if so == o:
                    struct.pack_into('>I', d, k + 4, total)
        else:
            d[o + e[0]:o + tail_end] = blk + bytes(tail_end - new_end)
        # 되읽기: 표로 다시 풀어 모든 대사가 기대대로인지
        s2 = struct.unpack_from('>I', d, [k for k in range(0, 0x800, 8) if struct.unpack_from('>I', d, k)[0] == o][0] + 4)[0]
        t2 = scr.find_table(bytes(d), o, s2 if not virtual else s)
        got = [bytes(d[o + t2[2][i]:o + t2[2][i + 1]]) for i in range(len(t2[2]) - 1)] if t2 else None
        if got != new:
            err.append('%s 구역 %d 되읽기 불일치' % (p, si))
    return n_ok
