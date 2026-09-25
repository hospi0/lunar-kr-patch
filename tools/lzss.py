# -*- coding: utf-8 -*-
r"""마법학원 루나 LZSS — /1 0x060353C0(파일 0x1D3C0) 역어셈블로 확정(2026-09-26).
  오쿠무라 LZSS: 링 4096 · 쓰기 시작 0xFEE · **초기값 0x00**(건그리폰 II 는 0x20) · 플래그 바이트 LSB 부터, 1 = 리터럴 1B, 0 = 매치 2B
  매치: 오프셋 = b0 | ((b1 & 0xF0) << 4), 길이 = (b1 & 0x0F) + 3.
  블록 = [u32 BE 압축 길이][압축 데이터] — 로더가 r4 = 길이, r5 = 블록+4 로 부른다.
"""


def decompress(src, n=None):
    """src = 압축 데이터(길이 머리 뒤), n = 압축 길이(없으면 전부)"""
    n = len(src) if n is None else n
    ring = bytearray(4096)
    r = 0xFEE
    out = bytearray()
    i = 0
    while i < n:
        f = src[i]; i += 1
        for k in range(8):
            if i >= n:
                break
            if (f >> k) & 1:
                c = src[i]; i += 1
                out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
            else:
                b0, b1 = src[i], src[i + 1]; i += 2
                off = b0 | ((b1 & 0xF0) << 4)
                for j in range((b1 & 0x0F) + 3):
                    c = ring[(off + j) & 0xFFF]
                    out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
    return bytes(out)


def compress(data):
    """되압축(링 초기값 0x00). ★디코더처럼 «방금 쓴 바이트»를 다시 읽는 자기참조 런까지 흉내낸다(건그리폰 II 교훈)."""
    ring = bytearray(4096)
    r = 0xFEE
    out = bytearray()
    i = 0
    # 빠른 후보 찾기: 3바이트 머리 → 링 위치 목록
    heads = {}
    while i < len(data):
        flags, chunk = 0, bytearray()
        for bit in range(8):
            if i >= len(data):
                break
            best_len, best_pos = 0, 0
            maxlen = min(18, len(data) - i)
            if maxlen >= 3:
                cands = heads.get(bytes(data[i:i + 3]), [])
                # 초기 링(0x00)도 후보: 0 줄은 링 어디서나 맞는다
                if data[i:i + 3] == b'\x00\x00\x00':
                    cands = cands + [(r + 1) & 0xFFF]
                for pos in reversed(cands[-64:]):
                    tmp = {}
                    k = 0
                    while k < maxlen:
                        s = (pos + k) & 0xFFF
                        cc = tmp.get(s, ring[s])
                        if cc != data[i + k]:
                            break
                        tmp[(r + k) & 0xFFF] = data[i + k]
                        k += 1
                    # 링에서 4096 이상 멀어진 위치는 이미 덮였을 수 있다 — 위에서 실제 링 값으로 비교하므로 안전
                    if k > best_len:
                        best_len, best_pos = k, pos
                        if k == maxlen:
                            break
            if best_len >= 3:
                chunk += bytes([best_pos & 0xFF, ((best_pos >> 4) & 0xF0) | (best_len - 3)])
                n = best_len
            else:
                flags |= 1 << bit
                chunk.append(data[i])
                n = 1
            for k in range(n):
                if i + k + 3 <= len(data):
                    pass
                ring[r] = data[i + k]
                if i + k >= 2:
                    heads.setdefault(bytes(data[i + k - 2:i + k + 1]), []).append((r - 2) & 0xFFF)
                r = (r + 1) & 0xFFF
            i += n
        out.append(flags)
        out += chunk
    return bytes(out)


def block(buf, off=0):
    """[u32 BE 길이][데이터] 블록 풀기"""
    n = int.from_bytes(buf[off:off + 4], 'big')
    return decompress(buf[off + 4:off + 4 + n], n)
