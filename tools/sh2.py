# SH-2 간이 역어셈블러 — python tools/sh2.py <시작> <끝>  (환경변수 SH2_FILE·SH2_BASE)
import os, struct, sys
d = open(os.environ.get('SH2_FILE', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'exe_1')), 'rb').read()
B = int(os.environ.get('SH2_BASE', '0x06018000'), 16)


def lit(pc, disp, size):
    if size == 4:
        a = (pc & ~3) + 4 + disp * 4
        return struct.unpack_from('>I', d, a)[0]
    a = pc + 4 + disp * 2
    return struct.unpack_from('>h', d, a)[0]


def dis(o):
    w = struct.unpack_from('>H', d, o)[0]
    n = (w >> 8) & 15; m = (w >> 4) & 15; hi = w >> 12
    if hi == 0xD: return 'mov.l #%08X,r%d' % (lit(o, w & 255, 4), n)
    if hi == 0x9: return 'mov.w #%d,r%d' % (lit(o, w & 255, 2), n)
    if hi == 0xE: return 'mov #%d,r%d' % (struct.unpack('b', bytes([w & 255]))[0], n)
    if hi == 0x7: return 'add #%d,r%d' % (struct.unpack('b', bytes([w & 255]))[0], n)
    if hi == 0x4 and w & 255 == 0x0B: return 'jsr @r%d' % n
    if hi == 0x4 and w & 255 == 0x2B: return 'jmp @r%d' % n
    if hi == 0x6 and w & 15 == 3: return 'mov r%d,r%d' % (m, n)
    if hi == 0x3 and w & 15 == 0xC: return 'add r%d,r%d' % (m, n)
    if hi == 0x3 and w & 15 == 8: return 'sub r%d,r%d' % (m, n)
    if hi == 0x4 and w & 255 == 0x21: return 'shar r%d' % n
    if hi == 0x4 and w & 255 == 0x01: return 'shlr r%d' % n
    if hi == 0x4 and w & 255 == 0x00: return 'shll r%d' % n
    if hi == 0x4 and w & 255 == 0x08: return 'shll2 r%d' % n
    if hi == 0x4 and w & 255 == 0x09: return 'shlr2 r%d' % n
    if hi == 0x6 and w & 15 == 0xB: return 'neg r%d,r%d' % (m, n)
    if hi == 0x2 and w & 15 == 6: return 'mov.l r%d,@-r%d' % (m, n)
    if hi == 0x6 and w & 15 == 6: return 'mov.l @r%d+,r%d' % (m, n)
    if w == 0x000B: return 'rts'
    if w == 0x0009: return 'nop'
    if hi == 0xA: return 'bra %X' % (o + 4 + (((w & 0xFFF) ^ 0x800) - 0x800) * 2)
    if hi == 0xB: return 'bsr %X' % (o + 4 + (((w & 0xFFF) ^ 0x800) - 0x800) * 2)
    return '.word %04X' % w


a, b = int(sys.argv[1]), int(sys.argv[2])
for o in range(a, b, 2):
    print('%6d %08X  %s' % (o, B + o, dis(o)))
