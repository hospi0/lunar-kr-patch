# -*- coding: utf-8 -*-
r"""RetroArch(Beetle Saturn) .state(RZIP) → work/state/<이름>.raw 풀기
  python tools/state.py <state 파일들...>
"""
import os, struct, sys, zlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unrzip(d):
    assert d[:8] == b'#RZIPv\x01#', d[:8]
    tot = struct.unpack_from('<Q', d, 12)[0]
    o, out = 20, bytearray()
    while o < len(d):
        n = struct.unpack_from('<I', d, o)[0]; o += 4
        out += zlib.decompress(d[o:o + n]); o += n
    assert len(out) == tot
    return bytes(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(os.path.join(ROOT, 'work', 'state'), exist_ok=True)
    k = open(os.path.join(ROOT, 'work', 'KANJI.FNT'), 'rb').read()
    for f in sys.argv[1:]:
        out = unrzip(open(f, 'rb').read())
        n = os.path.basename(f).split('.')[0]
        open(os.path.join(ROOT, 'work', 'state', n + '.raw'), 'wb').write(out)
        print(n, len(out), 'KANJI.FNT 머리', out.find(k[:64]), '전체', out.find(k), '대사', out.find('今年は'.encode('cp932')))
