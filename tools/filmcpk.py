# -*- coding: utf-8 -*-
r"""Sega FILM(.cpk, 1.09) 읽기·쓰기 + cinepak 프레임 새턴식 변환
  머리: 'FILM' u32 머리길이 '1.09' u32 0 | 'FDSC' 32 B | 'STAB' u32 길이, u32 기준(30), u32 개수, 항목 16 B × 개수
  항목: u32 위치(머리 뒤 기준) u32 길이 u32 정보1(소리 = FFFFFFFF, 영상 = 시각 | 0x80000000 이면 키 프레임 아님) u32 정보2(길이)
  새턴 cinepak: 10 B 프레임 머리 뒤에 «00 00» 2 B 가 더 있고, 머리의 크기 칸 = 조각 길이 − 8.
               띠 머리 좌표는 띠마다 (0, 0, 띠 높이, 320) — 절대 y 가 아니다. 띠 번호: 키 프레임 첫 띠 0x1000, 나머지 0x1100.
"""
import struct


def read(d):
    assert d[:4] == b'FILM' and d[8:12] == b'1.09'
    hl = struct.unpack_from('>I', d, 4)[0]
    o, fdsc, stab = 16, None, None
    while o < hl:
        tag, ln = d[o:o + 4], struct.unpack_from('>I', d, o + 4)[0]
        if tag == b'FDSC':
            fdsc = d[o:o + ln]
        elif tag == b'STAB':
            base, cnt = struct.unpack_from('>II', d, o + 8)
            stab = [list(struct.unpack_from('>IIII', d, o + 16 + 16 * i)) for i in range(cnt)]
        o += ln
    chunks = [d[hl + e[0]:hl + e[0] + e[1]] for e in stab]
    return {'hl': hl, 'head': d[:hl], 'base': base, 'stab': stab, 'chunks': chunks}


def write(film, chunks, infos):
    """film = read() 결과, chunks/infos = 항목 순서 그대로의 새 데이터·정보1 → bytes (머리 길이 같음)"""
    head = bytearray(film['head'])
    hl = film['hl']
    so = head.index(b'STAB')
    pos = 0
    for i, (c, inf) in enumerate(zip(chunks, infos)):
        e = film['stab'][i]
        struct.pack_into('>IIII', head, so + 16 + 16 * i, pos, len(c), inf, e[3])
        pos += len(c)
    return bytes(head) + b''.join(chunks)


def to_saturn(pkt, key):
    """표준 cinepak 프레임(ffmpeg) → 새턴식"""
    flags = pkt[0]
    w, h, ns = struct.unpack_from('>HHH', pkt, 4)
    out = bytearray(pkt[:10]) + b'\x00\x00'
    p = 10
    for s in range(ns):
        sid, ssz = struct.unpack_from('>HH', pkt, p)
        y0, x0, y1, x1 = struct.unpack_from('>HHHH', pkt, p + 4)
        # ★띠 안 조각마다 길이를 4의 배수로(뒤에 0 채움) — 원본은 전부 4의 배수. 홀수 길이면 뒤 조각(소리 포함)이
        #   홀수 주소에 놓여 새턴이 «지직·삐익» 소리 후 멈춘다(실기 2026-09-26).
        body = bytearray()
        q = p + 12
        while q < p + ssz:
            cid, csz = struct.unpack_from('>HH', pkt, q)
            c = bytearray(pkt[q:q + csz])
            c += bytes((-csz) % 4)
            struct.pack_into('>H', c, 2, len(c))
            body += c
            q += csz
        sid = 0x1000 if (key and s == 0) else 0x1100
        out += struct.pack('>HHHHHH', sid, 12 + len(body), 0, 0, y1 - y0, x1 - x0) + body
        p += ssz
    assert p == len(pkt), (p, len(pkt))
    assert len(out) % 4 == 0, len(out)
    sz = len(out) - 8
    out[1:4] = sz.to_bytes(3, 'big')
    return bytes(out)


def strips(frame):
    """새턴식 프레임 → [(띠 번호, 좌표, [(조각 번호, 길이)])] (검사용)"""
    ns = struct.unpack_from('>H', frame, 8)[0]
    p, res = 12, []
    for s in range(ns):
        sid, ssz = struct.unpack_from('>HH', frame, p)
        co = struct.unpack_from('>HHHH', frame, p + 4)
        q, ch = p + 12, []
        while q < p + ssz:
            cid, csz = struct.unpack_from('>HH', frame, q)
            ch.append((cid, csz)); q += csz
        res.append((sid, co, ch)); p += ssz
    return res


def avi_packets(d):
    """AVI(ffmpeg) 의 영상 조각(00dc) 을 순서대로"""
    out = []
    i = d.index(b'movi') + 4
    while i < len(d) - 8:
        tag, ln = d[i:i + 4], struct.unpack_from('<I', d, i + 4)[0]
        if tag == b'LIST':
            i += 12; continue
        if tag == b'idx1':
            break
        if tag[2:] in (b'dc', b'db'):
            out.append(d[i + 8:i + 8 + ln])
        i += 8 + ln + (ln & 1)
    return out
