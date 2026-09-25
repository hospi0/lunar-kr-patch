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


def block(buf, off=0):
    """[u32 BE 길이][데이터] 블록 풀기"""
    n = int.from_bytes(buf[off:off + 4], 'big')
    return decompress(buf[off + 4:off + 4 + n], n)
