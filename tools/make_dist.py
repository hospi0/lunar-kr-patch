# -*- coding: utf-8 -*-
r"""배포 묶음 — dist/MahouGakuenLunar_KR_<VER>/
  한글 패치 xdelta 하나(원본 조우·경험치) + opt/ 섹터 조각 + 패치적용.bat(조우 간격·경험치 배율을 숫자로 입력).
  옵션은 섹터 하나씩(EDC/ECC 까지 계산해 둔 2352 B) — bat 가 PowerShell 로 그 자리에 덮어쓴다.
    조우 N(0‥20): N=0 → opt/e0.bin @ 감소 명령 섹터, N≥2 → opt/eN.bin @ 난수·더하기 섹터, N=1 → 안 씀
    경험치 N(1‥10): N≥2 → opt/xN.bin @ 경험치 섹터
  검증: 원본 → xdelta → 기본 md5, 그리고 조합 몇 개를 «조각 덮어쓰기» 와 «build.py 직접 빌드» 로 만들어 md5 대조.
  python tools/make_dist.py
"""
import hashlib, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scr, options
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
from cdrom_ecc import recalc_sector

VER = 'v0.91'
XDELTA = r'C:\claude\utils\xdelta.exe'
BIN = os.path.basename(scr.TRACK1)
ROM = BIN.replace(' (Track 01).bin', '')
NAME = 'MahouGakuenLunar_KR_' + VER
CHECK = [(13, 3), (0, 1), (20, 10), (2, 2)]     # build.py 로 직접 만들어 대조할 조합


def md5b(b):
    return hashlib.md5(b).hexdigest().upper()


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


def build(args, dst):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'build.py'), '--write'] + args,
                       capture_output=True, text=True, encoding='utf-8', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode:
        sys.exit('빌드 실패 %s\n%s%s' % (args, r.stdout, r.stderr))
    shutil.copyfile(os.path.join(ROOT, 'work', 'out', BIN), dst)


def sector_for(img, lba, pats):
    """pats(한 섹터 안) 를 base 이미지 섹터에 넣고 EDC/ECC 재계산 → (바이트 위치, 2352 B)"""
    secs = {(lba[fp] + off // DATA_LEN) for fp, off, _, _ in pats}
    assert len(secs) == 1, pats
    s = secs.pop()
    pos = s * SECTOR
    sec = bytearray(img[pos:pos + SECTOR])
    for fp, off, old, new in pats:
        n = len(old) // 2
        k = DATA_OFF + off % DATA_LEN
        assert off % DATA_LEN + n <= DATA_LEN
        assert bytes(sec[k:k + n]) == bytes.fromhex(old), (fp, off)
        sec[k:k + n] = bytes.fromhex(new)
    return pos, recalc_sector(bytes(sec))


README = '''28개의 트랙으로 이루어진 @ROM@ 의
트랙 1번에 패치하시면 됩니다.

원본md5 : @SRC@
패치md5 : @DST@ (조우 1 · 경험치 1 = 원본 게임 밸런스)
          조우·경험치 배율을 바꾸면 md5 도 바뀝니다(패치적용.bat 가 끝에 보여 줍니다).

입니다.


마법학원 루나! (새턴 일본판) 한글 패치 @VER@
==========================================

[ 적용 방법 ]

1. 이 묶음을 원본 「@BIN@」 과 같은 폴더에 풉니다.
2. 「패치적용.bat」 을 실행하고 두 숫자를 넣습니다(그냥 Enter = 1).

   ■ 조우 간격 배율 (0~20)
       0 = 랜덤 전투 없음(이벤트·보스 전투는 그대로)
       1 = 원본(평균 약 8걸음마다 전투)
       N = 평균 약 8×N 걸음마다 전투  (예: 5 → 약 40걸음, 13 → 약 100걸음)
   ■ 경험치 배율 (1~10)
       N = 전투 경험치 N배

   원본 MD5 를 먼저 확인하고, 한글 패치 뒤 MD5 를 검사한 다음 배율을 넣습니다.
   원본은 「.bak」 으로 남겨 둡니다. (배율을 다시 고르려면 .bak 을 원래 이름으로 되돌린 뒤 다시 실행)
3. .cue 와 다른 트랙(2~28번)은 그대로 씁니다. 파일 크기도 바뀌지 않습니다.
   (Windows 가 아니면 Delta Patcher 같은 xdelta3 도구로 「@PATCH@」 을 트랙 1번에 적용하세요. 배율 1·1 입니다.)


[ 바뀌는 것 ]

■ 본편 대사 전부
■ 메뉴·전투·상태 화면 등 시스템 문구, 마법·아이템 이름
■ 장 제목 그림, 저장 화면 그림 글자
■ 오프닝 동영상 가사(일본어 가사를 가리고 한글 가사)


[ 알려진 사항 ]

■ 오프닝 말고 다른 동영상 속 대사는 자막이 없습니다.
■ 이전 테스트 빌드에서 만든 세이브스테이트는 글자가 깨질 수 있습니다.
'''

BAT = r'''@echo off
setlocal
set NAME=@BIN@
set PATCH=@PATCH@
set SRCMD5=@SRC@
set DSTMD5=@DST@
set DIR=%~dp0

echo.
echo  @BAR@
echo    Mahou Gakuen Lunar! ^(Saturn JP^) Korean Patch @VER@
echo  @BAR@
echo.

if not exist "%NAME%" (
  echo  [!] "%NAME%" 파일이 이 폴더에 없습니다.
  echo      원본 트랙 1번 .bin 과 같은 폴더에 두고 실행하세요.
  goto END
)
if not exist "%DIR%xdelta.exe" (
  echo  [!] xdelta.exe 가 없습니다. 패치 묶음을 그대로 풀고 실행하세요.
  goto END
)

:ASKE
set "E=1"
set /p "E=  조우 간격 배율 (0=전투 없음, 1=원본, 2~@EMAX@ = 평균 8xN 걸음) [Enter=1] : "
echo %E%| findstr /r /x "[0-9] [1-9][0-9]" >nul
if errorlevel 1 goto BADE
if %E% GTR @EMAX@ goto BADE
goto ASKX
:BADE
echo  [!] 0~@EMAX@ 사이 숫자를 넣으세요.
goto ASKE

:ASKX
set "X=1"
set /p "X=  경험치 배율 (1~@XMAX@) [Enter=1] : "
echo %X%| findstr /r /x "[1-9] [1-9][0-9]" >nul
if errorlevel 1 goto BADX
if %X% GTR @XMAX@ goto BADX
goto GO
:BADX
echo  [!] 1~@XMAX@ 사이 숫자를 넣으세요.
goto ASKX

:GO
echo.
echo  [1/4] 원본 검사 중...
call :MD5 "%NAME%"
if /I not "%HASH%"=="%SRCMD5%" (
  echo.
  echo  [!] 원본 MD5 가 다릅니다. 패치하지 않고 중단합니다.
  echo      필요 : %SRCMD5%
  echo      현재 : %HASH%
  echo      ^(이미 패치한 파일이면 .bak 을 원래 이름으로 되돌린 뒤 실행하세요^)
  goto END
)

echo  [2/4] 한글 패치 적용 중...
"%DIR%xdelta.exe" -d -f -s "%NAME%" "%DIR%%PATCH%" "%NAME%.kr"
if errorlevel 1 (
  echo  [!] 패치에 실패했습니다.
  if exist "%NAME%.kr" del "%NAME%.kr"
  goto END
)
call :MD5 "%NAME%.kr"
if /I not "%HASH%"=="%DSTMD5%" (
  echo  [!] 한글 패치 결과 MD5 가 다릅니다. 원본은 그대로 두고 중단합니다.
  del "%NAME%.kr"
  goto END
)

echo  [3/4] 배율 적용 중... 조우 %E% / 경험치 %X%
if %E%==0 call :PUT e0.bin @OFF_NEVER@
if %E% GTR 1 call :PUT e%E%.bin @OFF_ENC@
if %X% GTR 1 call :PUT x%X%.bin @OFF_EXP@
if defined FAIL (
  echo  [!] 배율 적용에 실패했습니다. 원본은 그대로 두고 중단합니다.
  del "%NAME%.kr"
  goto END
)

echo  [4/4] 마무리 중...
call :MD5 "%NAME%.kr"
move /y "%NAME%" "%NAME%.bak" >nul
move /y "%NAME%.kr" "%NAME%" >nul
echo.
echo  [OK] 한글 패치 완료 ^(조우 %E% / 경험치 %X%^). 원본은 "%NAME%.bak" 으로 남겨 두었습니다.
echo       결과 MD5 : %HASH%
goto END

:PUT
if not exist "%DIR%opt\%~1" (
  echo  [!] opt\%~1 이 없습니다.
  set FAIL=1
  goto :EOF
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f=[IO.File]::Open('%CD%\%NAME%.kr','Open','ReadWrite'); $b=[IO.File]::ReadAllBytes('%DIR%opt\%~1'); [void]$f.Seek(%~2,'Begin'); $f.Write($b,0,$b.Length); $f.Close()"
if errorlevel 1 set FAIL=1
goto :EOF

:MD5
set HASH=
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%~1" MD5') do (
  if not defined HASH set HASH=%%H
)
set HASH=%HASH: =%
goto :EOF

:END
echo.
pause
'''

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    src = scr.TRACK1
    smd5 = md5(src)
    out = os.path.join(ROOT, 'dist', NAME)
    opt = os.path.join(out, 'opt')
    os.makedirs(opt, exist_ok=True)
    # 1) 기본 빌드 + xdelta
    base = os.path.join(ROOT, 'work', '_dist_base.bin')
    build(['--enc', '1', '--exp', '1'], base)
    dmd5 = md5(base)
    patch = NAME + '.xdelta'
    pp = os.path.join(out, patch)
    if os.path.exists(pp):
        os.remove(pp)
    subprocess.run([XDELTA, '-e', '-9', '-s', src, base, pp], check=True)
    chk = os.path.join(ROOT, 'work', '_distcheck.bin')
    subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
    assert md5(chk) == dmd5, 'xdelta 적용 검증 실패'
    os.remove(chk)
    print('기본', patch, '패치본', dmd5, 'xdelta', md5(pp))
    # 2) 옵션 섹터 조각
    img = open(base, 'rb').read()
    lba = {f[0]: f[1] for f in Iso(src).walk()}
    offs, blobs = {}, {}
    for n in range(0, options.ENC_MAX + 1):
        if n == 1:
            continue
        pos, b = sector_for(img, lba, options.enc_patch(n))
        offs.setdefault('never' if n == 0 else 'enc', set()).add(pos)
        blobs['e%d.bin' % n] = (pos, b)
    for n in range(2, options.EXP_MAX + 1):
        pos, b = sector_for(img, lba, options.exp_patch(n))
        offs.setdefault('exp', set()).add(pos)
        blobs['x%d.bin' % n] = (pos, b)
    assert all(len(v) == 1 for v in offs.values()), offs
    OFF = {k: v.pop() for k, v in offs.items()}
    assert len(set(OFF.values())) == 3
    for fn, (pos, b) in blobs.items():
        open(os.path.join(opt, fn), 'wb').write(b)
    print('옵션 조각 %d개 · 위치 %s' % (len(blobs), OFF))

    # 3) 조합 대조: 조각 덮어쓰기 == build.py 직접 빌드
    def combo(e, x):
        m = bytearray(img)
        for fn in ((['e%d.bin' % e] if e != 1 else []) + (['x%d.bin' % x] if x != 1 else [])):
            pos, b = blobs[fn]
            m[pos:pos + SECTOR] = b
        return md5b(m)
    ok = True
    for e, x in CHECK:
        ref = os.path.join(ROOT, 'work', '_dist_ref.bin')
        build(['--enc', str(e), '--exp', str(x)], ref)
        a, b = combo(e, x), md5(ref)
        os.remove(ref)
        print('  대조 조우 %d · 경험치 %d : %s %s' % (e, x, a, 'OK' if a == b else '⛔불일치 ' + b))
        ok &= a == b
    os.remove(base)
    # 4) 옛 3종 파일 정리(이 폴더 안 파일만)
    for fn in os.listdir(out):
        if fn.endswith('.xdelta') and fn != patch or fn.startswith('패치적용_') or fn.endswith('.cht'):
            os.remove(os.path.join(out, fn))
    shutil.copyfile(XDELTA, os.path.join(out, 'xdelta.exe'))
    rep = lambda s: s.replace('@ROM@', ROM).replace('@BIN@', BIN).replace('@SRC@', smd5).replace('@DST@', dmd5) \
        .replace('@VER@', VER).replace('@PATCH@', patch) \
        .replace('@EMAX@', str(options.ENC_MAX)).replace('@XMAX@', str(options.EXP_MAX)) \
        .replace('@BAR@', '=' * (len('Mahou Gakuen Lunar! (Saturn JP) Korean Patch ' + VER) + 4)).replace('@OFF_NEVER@', str(OFF['never'])).replace('@OFF_ENC@', str(OFF['enc'])).replace('@OFF_EXP@', str(OFF['exp']))
    open(os.path.join(out, 'readme.txt'), 'wb').write(rep(README).replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(out, '패치적용.bat'), 'wb').write(rep(BAT).replace('\n', '\r\n').encode('cp949'))
    print('배포', out, '· 원본', smd5, '· 대조', 'OK' if ok else '⛔실패')
