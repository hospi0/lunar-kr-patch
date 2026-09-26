# -*- coding: utf-8 -*-
r"""조우 간격·경험치 배율 — 빌더(--enc N / --exp N)와 배포 bat(숫자 입력)가 같이 쓴다.
  조우: /1 0x06018338‥ 카운터(0x06052844) = 난수(0‥r4) + 더하기 → 걸음마다 −1, 0 이면 전투. 원본 r4=6, +5 → 평균 8걸음.
        N 배 = r4 6N, 더하기 5N → 평균 8N 걸음(N 1‥20, 둘 다 8비트 부호 즉치 ≤127).
        N=0 = 전투 없음(감소 −1 → 0, /1@69798 71FF→7100).
        (예전 «1/10» 은 r4 64 / +70 = 평균 102걸음 ≈ N 13)
  경험치: /2 0x06039904 «tst r12 / bf / mov #1,r12»(0 이면 1) 자리 → mov #N,r1 / mul.l r1,r12 / sts macl,r12.
        r1 은 바로 뒤 mov.l 로 덮이고, MACL 은 뒤(0x0603997E)에서 새로 곱해 쓴다. N 1‥10.
"""
ENC_MAX, EXP_MAX = 20, 10
ENC_A = (830, 'e406', 834, '7105')       # /1 난수 범위·더하기
ENC_NEVER = (69798, '71ff', '7100')      # /1 카운터 감소
EXP_AT, EXP_OLD = 137476, '2cc88b00ec01'  # /2


def enc_patch(n):
    """→ [(파일, 위치, 원문 hex, 새 hex)] (N=1 이면 빈 목록)"""
    assert 0 <= n <= ENC_MAX, n
    if n == 0:
        return [('/1',) + ENC_NEVER]
    if n == 1:
        return []
    a, old_a, b, old_b = ENC_A
    return [('/1', a, old_a, 'e4%02x' % (6 * n)), ('/1', b, old_b, '71%02x' % (5 * n))]


def exp_patch(n):
    assert 1 <= n <= EXP_MAX, n
    if n == 1:
        return []
    return [('/2', EXP_AT, EXP_OLD, 'e1%02x0c170c1a' % n)]
