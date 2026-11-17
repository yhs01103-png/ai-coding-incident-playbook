# 실기기 확인을 adb 탭·스크린샷으로 직접 돌리는 절차 (poker_app 2026-10-06 실측)

## 언제
UI 흐름(시트 자동 열림, 결과 화면, 서버 재시작 뒤 이어하기)을 사람 손 없이 실기기에서 확인할 때. 에뮬레이터·위젯 테스트로는 안
잡히는 레이아웃 넘침·문구·실제 서버 연동을 본다.

## 절차
1. `adb devices`로 연결 확인(Windows는 `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` — Git Bash PATH엔 없을 수 있다).
2. 로컬 서버를 프로젝트 스크립트·`.env` 그대로 띄운다(DB 경로가 곧 계정 — 다른 DB로 뜨면 401). 백그라운드 셸이 바로 종료되면
   `Start-Process ... -RedirectStandardError`로 분리 실행하고 로그로 기동 확인.
3. USB면 `adb reverse tcp:PORT tcp:PORT`.
4. ⚠️ **패키지 이름을 빌드 설정(`applicationId`)에서 확인하고 실행** — 같은 기기에 옛 앱(다른 패키지)이 있으면 `monkey -p 옛이름`으로
   엉뚱한 앱을 띄워 "코드에 없는 화면"을 보고 헤맨다. `adb shell pm list packages | findstr 키워드`로 후보부터.
   **`uninstall`·`install`은 더 위험하다**(RVS_App 2026-11-16): 옛 앱(`com.rvs.app`)을 실제 앱으로 착각해 "서버에 연결할 수 없습니다"를
   앱 데이터 문제로 넘겨짚고 `adb uninstall com.rvs.app`을 해서 그 앱의 기기 데이터가 지워졌다. 증상을 보고 지우기 전에 **지금 띄운 앱이
   어느 패키지인지**부터 확인한다. 실행은 `am start …/.MainActivity`가 클래스 이름이 달라 실패할 수 있으니
   `adb shell monkey -p <패키지> -c android.intent.category.LAUNCHER 1`. 화면 캡처는 폰(`screencap`+`pull`)이나 창 단위만 — 전체 화면 캡처는
   무관한 화면이 찍힌다.
5. 스크린샷: `adb shell screencap -p /sdcard/x.png` → `adb pull` → 이미지로 열어 판단. 탭: `adb shell input tap X Y`(스크린샷 좌표가
   `wm size`와 같으면 그대로 사용). 뒤로가기 `input keyevent 4`. 두 동작을 스크립트(tap.ps1/shot.ps1)로 묶으면 한 줄씩 진행된다.
6. 시간이 걸리는 화면 전환은 고정 대기 후 찍고, 로딩 중이면 한 번 더 찍는다.
7. 서버 재시작 복구 같은 시나리오는 "앱 화면 유지 → 서버 프로세스만 종료·재기동 → 앱에서 다음 액션"으로 검증.

## 앱 저장 데이터 평문 점검 (debug 빌드, run-as) — 2026-10-07 Market_Agent_App 실측
암호화 적용 후 "파일에 평문이 남았나"를 기기에서 확인하는 절차. **내용은 화면·보고서에 옮기지 않고 "있음/없음"과
숫자만 남긴다**(대화·알림 원문이라 점검 자체가 새로운 노출이 되면 안 된다).

1. `adb shell run-as <패키지> ls app_flutter` — `*.hive` 목록과 크기. `run-as`는 **debuggable 빌드에서만** 된다.
2. 파일마다 `adb exec-out run-as <패키지> cat app_flutter/<이름>.hive`를 로컬 스크립트(파이썬 `-I`)에 받아 바이트로 검사.
   Windows 콘솔(cp949)에 한글을 그대로 찍으면 깨지니 결과는 `PLAINTEXT`/`none` 같은 영문 라벨 + 숫자로 출력.
3. **"한글 3바이트 패턴이 몇 번 나왔나"로 판정하지 않는다.** 암호문(무작위 바이트)에서도 UTF-8 한글 시퀀스
   (`[ê-í][-¿]{2}`)가 위치당 약 0.1%(= 4/256 × 1/16)로 우연히 맞는다. 암호화된 78,840바이트 파일에서
   기댓값 ≈77건, 실측 74건. 개수가 아니라 **연속 길이**(한글·ASCII 인쇄 가능 문자가 이어지는 구간이 10~15자 이상인
   수)로 본다. 암호화된 박스는 짧은 우연 일치(최장 7~9자)만, 평문이 남은 박스는 긴 구간(최장 114자)이 나왔다.
4. 판정이 갈리면 박스 **키**가 내용인지 의심한다 → `Hive_암호화는_값만_키는_평문_함정_평문박스_1회이전_패턴.md`.
5. 점검 후 로컬에 받은 임시 파일/스크립트는 지운다.

## 다른 세션이 작업 중일 때 — 커밋된 코드만으로 실기기 확인 (RVS_App 2026-10-31 실측)
작업 폴더에 남의 미커밋 변경이 있으면 거기서 빌드·서버를 띄우는 순간 그 반쯤 된 코드를 확인하게 된다(되돌리거나 stash하는 것도 남의 작업을 건드리는 일).

1. `git worktree add --detach <스크래치>/head HEAD` — 저장소 이력은 공유, 작업 파일은 별도. **추적 안 되는 로컬 파일은 따라오지 않는다**: `.env`, 폴더 라벨(`android/app_variant.local`), `android/local.properties`, 데이터 폴더를 직접 복사한다. 데이터는 **사본**이라 시험 중 생긴 계정·기록이 실제 개발 DB를 더럽히지 않는다.
2. Windows 경로 길이: 임시 폴더 아래는 Flutter 빌드 산출물이 260자를 넘어 `Could not write file`. `subst R: <폴더>`로 짧은 드라이브를 만들어 빌드하고 끝나면 `subst R: /d`.
3. 드라이브가 다르면(R:의 프로젝트, C:의 pub 캐시) Kotlin 증분 컴파일이 `Daemon compilation failed: null`로 죽는다 → **사본의** `android/gradle.properties`에만 `kotlin.incremental=false`.
4. **개발용 무인증 스위치(추적 안 되는 파일)를 일부러 빼고 한 번 더 돌린다** — 인증이 켜진 배포 설정에서만 나는 버그가 있다(RVS: 시작 요청 4개가 동시에 거절되자 각자 기기 가입 → 같은 초에 계정 4개). 개발 서버가 무인증이면 이 경로는 영영 안 지나간다.
5. 끝나면 `git worktree remove --force`(긴 경로로 실패하면 폴더를 지우고 `git worktree prune`) — 복사한 `.env`도 함께 사라진다. `git stash`는 worktree끼리 공유되니 사본에서 쓰지 않는다.
6. **앱이 사본 서버에서 받은 로그인 토큰을 기기에 남긴다**: 원래 서버로 돌아가면 모르는 토큰 → 401 → 새 계정 가입 → 기존 데이터가 안 보인다. `pm clear`는 예약 알림·온보딩 기록까지 지우므로, 토큰 저장 파일만 지운다(flutter_secure_storage는 `run-as <패키지> rm shared_prefs/FlutterSecureStorage.xml` — 먼저 그 파일의 키가 토큰뿐인지 `cat`으로 확인, 앱은 `force-stop` 뒤).

## 위젯 테스트로 재현이 안 되는 것 (실기기에서만 보인 것)
- **지연 생성 목록 끝으로 이동**: `ListView.builder`의 `maxScrollExtent`는 아직 안 그린 항목 높이의 추정치라 `jumpTo(max)`가 며칠 전 위치에서 멈췄다. 테스트는 데이터가 동기로 들어와 통과한다. 채팅·타임라인처럼 최신이 아래면 `reverse: true` + `jumpTo(0)`.
- **줄바꿈이 안 되는 라벨 위젯**: 폭 360·글자 ×1.6 시험이 있어도 새로 넣은 조건부 위젯(선택해야 나타나는 칩 묶음의 제목)까지 열지 않으면 못 잡는다 — 조건부 UI를 넣으면 폰 폭 시험이 그 상태까지 열게 늘린다(RVS: 4.4px 넘침).
  같은 날 같은 원인으로 한 번 더(RVS 10-31, 66px): 공용 머리글 위젯이 `Row[Text, Expanded(Divider)]`라 글자가 줄바꿈되지 않아 "예측 중 실제와 가장 가까운 것"(16자)이 넘쳤다 —
  처음엔 칩(ChoiceChip)을 의심해 바꿨는데 그대로였다. **추측하지 말고 넘친 위젯을 찍어 본다**: 폰 폭 시험에서 `tester.takeException()`은 요약만 주므로,
  시험 흐름 앞에 `final old = FlutterError.onError; FlutterError.onError = (d) { debugPrint('DBG ${d.toString()}'); old?.call(d); };`을 잠깐 넣으면
  "relevant error-causing widget was: Row …paper.dart:224" 같은 생성 위치가 나온다(확인 뒤 지운다). 공용 위젯을 고치면 다른 화면까지 바뀌므로 머리글을 짧게
  하는 쪽을 먼저 보고(×1.6·폭 360에서 한글 약 15자), 공용 위젯 수정은 따로 정한다.

## 함께 볼 것
- 발견한 문제는 그 자리에서 목록으로 적고(문구·레이아웃·돈 계산), 고친 뒤 재빌드·재설치해 같은 화면을 다시 찍어 확인.
