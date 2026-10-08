---
name: make
description: "`/make videos` — 타이포그래피 모션 영상(릴스/쇼츠/가로형)을 장면·효과를 골라 만드는 스킬. 사용자가 '/make videos', '/make videos help', '렌더', 'help'로 영상 제작을 요청할 때 사용."
---

# /make videos — 타이포 모션 영상 메이커

엔진: 이 스킬 폴더의 `scripts/engine.py` (Python + Pillow + ffmpeg, 120BPM 박자, 팔레트 3색, 음악 없음).
실행은 항상 `python "<스킬 폴더>/scripts/engine.py" <명령>` 형태. `<스킬 폴더>`는 스킬 로드 시 맨 위에 표시되는 "Base directory for this skill" 경로(보통 `~/.claude/skills/make`)이고, Bash에서는 `$HOME`을 써서 절대경로로 만든다. 아래 `$ENGINE`으로 줄여 쓴다.

## 인자 처리
- `/make videos help` 또는 대화 중 사용자가 `help`를 입력 → **가이드 모드**
- `/make videos` → **제작 모드**
- 대화 중 사용자가 `렌더`라고 쓰면 → 확정된 spec으로 즉시 렌더 (아래 4번)

## 가이드 모드 (help)
`$ENGINE list`를 실행해 장면/효과/와이프/프리셋 목록을 보여주고, 아래 순서를 짧게 안내한다.
1. `/make videos` 실행 → 문구·비율 입력
2. 장면 선택(순서대로) → 효과 선택 → 장면별 길이/전환 확정
3. 미리보기 PNG 확인 → 수정 요청 가능
4. `렌더` 입력 → MP4 생성
5. 이후 수정: "3번 장면 빼줘", "비율 9:16으로" 등 말하면 spec만 고쳐 다시 미리보기
규칙도 한 줄씩 안내: 장면마다 최소 길이가 있음, 길이는 0.5초(박자) 배수 권장, 전환은 하드컷/와이프만(페이드 없음).

## 제작 모드
1. **빌더 대화창 띄우기** — `assets/builder.html`을 Read로 읽어, 내용을 그대로 `mcp__visualize__show_widget`의 `widget_code`로 넘긴다 (먼저 `mcp__visualize__read_me`를 modules `["interactive"]`로 1회 호출, 이 호출은 사용자에게 언급하지 않는다). title은 `make_videos_builder`.
   - 대화창에서 사용자가 버튼으로: 문구 입력 · 비율(16:9/9:16/1:1) · 프리셋(lookbook/short) · **장면 버튼을 눌러 여러 개 추가** · 길이(±0.5초)/전환/순서/삭제 조정 · 효과(shake/pulse) 토글 → "미리보기 만들기" 클릭.
   - 위젯 위에는 한 줄만: "아래에서 장면을 눌러 구성하고 '미리보기 만들기'를 눌러주세요."
   - 위젯을 쓸 수 없는 환경이면 AskUserQuestion(multiSelect)으로 대체: 문구/비율/시작점 → 장면 → 효과.
2. **빌더 결과 처리** — 사용자가 보낸 `영상 구성 확정` 메시지(문구/비율/효과/장면 `이름 길이s 전환`)를 파싱해 spec을 만든다.
   - 작업 폴더 `./videos/<이름>/spec.json` 저장 (포맷은 engine.py 상단 docstring; `$ENGINE preset short spec.json`으로 틀을 만든 뒤 text/ratio/effects/scenes를 덮어써도 됨. `copyright`, `palette`, `font`, `out` 선택 지정 가능).
   - 문구에 한글/비라틴 글자가 있으면 `font`를 `C:/Windows/Fonts/malgunbd.ttf`(맑은 고딕 Bold, Windows. 다른 OS는 한글 지원 굵은 ttf 경로)로 지정하고 사용자에게 알린다 (Impact에는 한글이 없음).
3. **미리보기** — `$ENGINE preview spec.json` 실행 → `preview/contact_sheet.png`를 Read로 확인, 글자 잘림/겹침이 있으면 spec 조정. 사용자에게 보여주고 "수정할 점은 말씀하시거나 빌더를 다시 열어 바꿀 수 있어요(`/make videos`). 괜찮으면 `렌더`라고 입력하세요"라고 안내.
4. **렌더** — 사용자가 `렌더`를 입력하면 `$ENGINE render spec.json` 실행 (15초 ≈ 1분, timeout 600000). 완료 후 MP4 경로, 길이, 해상도를 알려준다. 미리보기 확인 없이 렌더하지 않는다(사용자가 "바로 렌더"라고 하면 예외).

## 제약 (항상 지킬 것)
- 색은 크림/잉크/포인트 3색만 (palette로 바꾸더라도 3색 유지). 철자는 사용자가 준 문구 그대로.
- 의존성이 없으면 `pip install pillow imageio-ffmpeg` (시스템 ffmpeg 불필요).
- 폰트는 엔진이 Impact → Arial Black → DejaVu Bold 순으로 찾는다. 다른 폰트는 spec의 `font`에 ttf 경로 지정. 어떤 폰트를 썼는지 사용자에게 알린다.
- 새 장면/효과를 추가하려면 engine.py에 `sc_<이름>(self, t, dur)` 메서드와 SCENE_INFO/PEAK 항목을 추가한다.
