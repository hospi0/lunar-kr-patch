# -*- coding: utf-8 -*-
"""건그리폰 II 압축 코덱 = 고전 오쿠무라 LZSS.

`/2` 파일오프셋 `0x153C8`(적재 `0x06023BC8`)의 해제 루틴을 명령 단위로 읽어 확정:

    [BE32 해제크기][플래그·데이터…]

  · 링버퍼 N = 0x1000, 초기값 **0x20**(리터럴 풀 `20202020` / `00001000`)
  · 쓰기 포인터 시작 = N − 18 = 0xFEE   (`MOV #0xEF,R6; ADD R11,R6`, R11 = N−1)
  · 플래그 바이트, **LSB 부터**. 1 = 리터럴 1바이트, 0 = 매치 2바이트
  · 매치 = `b0` + `b1` → 오프셋 = ((b1>>4)<<8)|b0, 길이 = (b1&0x0F)+3
  · 링버퍼에도 같이 써 넣는다(표준 LZSS)
"""
import struct

N = 0x1000
INIT = 0x20
START = N - 18


def decompress(buf, off=0, size=None):
    if size is None:
        size = struct.unpack_from('>I', buf, off)[0]
        off += 4
    ring = bytearray([INIT]) * N
    r = START
    out = bytearray()
    p = off
    flags = 0
    nbits = 0
    while len(out) < size:
        if nbits == 0:
            if p >= len(buf):
                break
            flags = buf[p]
            p += 1
            nbits = 8
        bit = flags & 1
        flags >>= 1
        nbits -= 1
        if bit:
            if p >= len(buf):
                break
            c = buf[p]
            p += 1
            out.append(c)
            ring[r] = c
            r = (r + 1) & (N - 1)
        else:
            if p + 1 >= len(buf):
                break
            b0, b1 = buf[p], buf[p + 1]
            p += 2
            pos = ((b1 >> 4) << 8) | b0
            ln = (b1 & 0x0F) + 3
            for k in range(ln):
                c = ring[(pos + k) & (N - 1)]
                out.append(c)
                ring[r] = c
                r = (r + 1) & (N - 1)
                if len(out) >= size:
                    break
    return bytes(out), p


def compress(data):
    """되압축. 매치 탐색은 단순 최장일치(속도보다 정확성)."""
    ring = bytearray([INIT]) * N
    r = START
    out = bytearray(struct.pack('>I', len(data)))
    i = 0
    chunk = bytearray()
    flags = 0
    nbits = 0
    while i < len(data):
        best_len, best_pos = 0, 0
        maxlen = min(18, len(data) - i)
        if maxlen >= 3:
            for pos in range(N):
                # ★디코더를 그대로 흉내내야 한다 — 매치가 쓰기 포인터를 지나가면
                #   디코더는 «방금 쓴 바이트»를 읽는다(자기참조 런).
                #   그걸 무시하면 압축은 되는데 왕복이 어긋난다.
                tmp = {}
                k = 0
                while k < maxlen:
                    s = (pos + k) & (N - 1)
                    c = tmp.get(s, ring[s])
                    if c != data[i + k]:
                        break
                    tmp[(r + k) & (N - 1)] = data[i + k]
                    k += 1
                if k > best_len:
                    best_len, best_pos = k, pos
                    if k == maxlen:
                        break
        if best_len >= 3:
            chunk += bytes([best_pos & 0xFF,
                            ((best_pos >> 8) << 4) | (best_len - 3)])
            for k in range(best_len):
                ring[r] = data[i + k]
                r = (r + 1) & (N - 1)
            i += best_len
        else:
            flags |= 1 << nbits
            chunk.append(data[i])
            ring[r] = data[i]
            r = (r + 1) & (N - 1)
            i += 1
        nbits += 1
        if nbits == 8:
            out.append(flags)
            out += chunk
            flags, nbits, chunk = 0, 0, bytearray()
    if nbits:
        out.append(flags)
        out += chunk
    return bytes(out)
