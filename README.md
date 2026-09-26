# 마법학원 루나! (새턴 일본판) 한글화

> **내려받기**: [Releases](https://github.com/hospi0/lunar-kr-patch/releases) 의 v0.9 zip — 트랙 1번 xdelta 하나 + `패치적용.bat`.
> 적용할 때 **조우 간격 배율(0~20, 0 = 랜덤 전투 없음)** 과 **경험치 배율(1~10)** 을 숫자로 고를 수 있습니다. 자세한 건 zip 안 readme.txt.

Mahou Gakuen Lunar! (세가 새턴, 1997 GAME ARTS/角川書店) 한글 패치 작업 저장소.
**`docs/01_초기조사.md` 부터.** ROM·스테이트·빌드 결과물은 올리지 않는다.

- 대사: `work/text/scr.tsv` (S00‥S12.FLD, `tools/scr.py`)
- UI: `work/text/ui.tsv` · `work/text/ui_extra.tsv` (실행 파일 /0‥/4, `tools/exestr.py`)
- 동영상 대사 자막: `work/text/movie_sub.tsv` (`tools/moviesub.py`), 오프닝 가사 (`tools/opening.py` → `tools/opening_enc.py`)
- 빌드: `python tools/build.py --write` (기본 조우 1/10 · 경험치 ×3), 배포: `python tools/make_dist.py`
