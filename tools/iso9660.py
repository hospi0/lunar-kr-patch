# -*- coding: utf-8 -*-
"""MODE1/2352 raw CD 트랙에서 ISO9660 디렉터리 트리를 읽는다 (seek 기반).

Azel(Panzer Dragoon Saga) Track 01은 645MB라 통짜 로드를 피한다.
silmirage/gdm 프로젝트의 iso9660.py와 같은 규약이지만
  - 파일 핸들 기반 랜덤 액세스
  - 서브디렉터리 재귀
두 가지가 다르다.
"""
import struct

SECTOR = 2352
DATA_OFF = 16      # sync(12) + header(4)
DATA_LEN = 2048


class Iso:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        self.f.seek(0, 2)
        self.nsec = self.f.tell() // SECTOR

    def sector(self, lba):
        self.f.seek(lba * SECTOR + DATA_OFF)
        return self.f.read(DATA_LEN)

    def read(self, lba, length):
        """LBA부터 length 바이트를 논리적으로 읽는다."""
        out = bytearray()
        while len(out) < length:
            if lba >= self.nsec:
                raise EOFError('LBA %d 가 트랙 끝(%d)을 넘음' % (lba, self.nsec))
            out += self.sector(lba)
            lba += 1
        return bytes(out[:length])

    # --- ISO9660 ---------------------------------------------------------
    def pvd(self):
        p = self.sector(16)
        assert p[1:6] == b'CD001', 'PVD가 LBA16에 없음 — MODE1/2352 여부 확인'
        return p

    def root(self):
        rec = self.pvd()[156:156 + 34]
        return struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]

    @staticmethod
    def _records(data):
        out = []
        pos = 0
        while pos < len(data):
            rec_len = data[pos]
            if rec_len == 0:
                pos = (pos // DATA_LEN + 1) * DATA_LEN
                if pos >= len(data):
                    break
                continue
            rec = data[pos:pos + rec_len]
            lba = struct.unpack_from('<I', rec, 2)[0]
            size = struct.unpack_from('<I', rec, 10)[0]
            flags = rec[25]
            name_len = rec[32]
            name = rec[33:33 + name_len].decode('ascii', 'replace')
            out.append((name, lba, size, bool(flags & 0x02)))
            pos += rec_len
        return out

    def walk(self, lba=None, size=None, prefix='/'):
        """[(path, lba, size)] 전체 파일 목록 (재귀)."""
        if lba is None:
            lba, size = self.root()
        out = []
        for name, l, s, is_dir in self._records(self.read(lba, size)):
            if name in ('\x00', '\x01'):
                continue
            base = name.split(';')[0]
            if is_dir:
                out.append((prefix + base + '/', l, s))
                out += self.walk(l, s, prefix + base + '/')
            else:
                out.append((prefix + base, l, s))
        return out


if __name__ == '__main__':
    import sys
    iso = Iso(sys.argv[1])
    ents = iso.walk()
    tot = 0
    for path, lba, size in ents:
        print('%-40s lba=%-8d size=%d' % (path, lba, size))
        if not path.endswith('/'):
            tot += size
    print('---- 항목 %d개, 파일 합계 %d B' % (len(ents), tot))
