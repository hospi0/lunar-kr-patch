"""
CD-ROM Mode 1 섹터 EDC/ECC 재계산.

2026-07-04: 지금까지 빌드 스크립트가 MXE/FONT12.DAT 바이트를 패치한 뒤
섹터의 EDC(4B)+ECC(276B) 체크섬을 재계산하지 않고 있었음이 밝혀짐 — 원본
디스크가 표준 Mode1 체크섬(EDC: CRC 유사 다항식 0xD8018001, ECC: GF(256)
Reed-Solomon P/Q 패리티)을 쓴다는 걸 실측으로 확인(원본 섹터의 저장된
EDC/ECC와 이 모듈의 계산값이 정확히 일치함, EV_MA001 LBA=1916 섹터로 검증).
체크섬이 안 맞으면 에뮬레이터가 섹터를 읽을 때 내용과 무관하게 크래시가
남 — EV_MA001 자이탄 대사 패치에서 한글/영문 관계없이 무조건 크래시 나던
문제의 진짜 원인이었음.

섹터 구조 (2352B): sync(12) + header(4: MM,SS,FF,mode) + data(2048)
                    + EDC(4) + reserved(8) + P-parity(172) + Q-parity(104)
"""

_ECC_F_LUT = [0] * 256
_ECC_B_LUT = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if (_i & 0x80) else 0)) & 0xFF
    _ECC_F_LUT[_i] = _j
    _ECC_B_LUT[_i ^ _j] = _i

_EDC_LUT = [0] * 256
for _i in range(256):
    _edc = _i
    for _ in range(8):
        _edc = (_edc >> 1) ^ (0xD8018001 if (_edc & 1) else 0)
    _EDC_LUT[_i] = _edc & 0xFFFFFFFF


def _edc_compute(data: bytes) -> int:
    edc = 0
    for b in data:
        edc = (edc >> 8) ^ _EDC_LUT[(edc ^ b) & 0xFF]
    return edc & 0xFFFFFFFF


def _ecc_writepq(address, data, major_count, minor_count, major_mult, minor_inc, ecc_out, ecc_base):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = 0
        ecc_b = 0
        for _ in range(minor_count):
            temp = address[index] if index < 4 else data[index - 4]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= temp
            ecc_b ^= temp
            ecc_a = _ECC_F_LUT[ecc_a]
        ecc_a = _ECC_B_LUT[_ECC_F_LUT[ecc_a] ^ ecc_b]
        ecc_out[ecc_base + major] = ecc_a
        ecc_out[ecc_base + major + major_count] = ecc_a ^ ecc_b


def recalc_sector(sector: bytes) -> bytes:
    """2352바이트 Mode1 섹터를 받아 EDC(2064-2067)+ECC(2076-2351)를 재계산해 반환.
    sync(0-11)/header(12-15)/data(16-2063)는 그대로 유지."""
    sector = bytearray(sector)
    address = bytes(sector[12:16])

    edc = _edc_compute(bytes(sector[0:2064]))
    sector[2064:2068] = edc.to_bytes(4, 'little')
    sector[2068:2076] = b'\x00' * 8  # reserved

    ecc = bytearray(276)
    _ecc_writepq(address, bytes(sector[16:2076]), 86, 24, 2, 86, ecc, 0)          # P
    _ecc_writepq(address, bytes(sector[16:2076]) + bytes(ecc[0:172]),
                 52, 43, 86, 88, ecc, 172)                                        # Q
    sector[2076:2352] = ecc
    return bytes(sector)


def fix_sectors(file_obj, byte_ranges):
    """byte_ranges: [(bin_off, length), ...] — BIN 파일 절대 오프셋 기준으로
    수정된 바이트 구간들. 겹치는 섹터(2352B 단위, sync 시작 기준)를 전부 모아
    한 번씩만 재계산해 다시 써넣는다."""
    dirty_sectors = set()
    for bin_off, length in byte_ranges:
        first = bin_off // 2352
        last = (bin_off + length - 1) // 2352
        for s in range(first, last + 1):
            dirty_sectors.add(s)

    for s in sorted(dirty_sectors):
        off = s * 2352
        file_obj.seek(off)
        sector = file_obj.read(2352)
        if len(sector) != 2352:
            continue
        # Mode1 데이터 섹터만 재계산 (mode byte(15) == 0x01), 그 외(오디오/Mode2 등)는 건드리지 않음
        if sector[15] != 0x01:
            continue
        fixed = recalc_sector(sector)
        if fixed != sector:
            file_obj.seek(off)
            file_obj.write(fixed)
    return len(dirty_sectors)
