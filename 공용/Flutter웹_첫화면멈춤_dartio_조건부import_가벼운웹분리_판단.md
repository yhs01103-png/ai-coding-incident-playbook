# Flutter 앱을 웹으로 켰더니 하얀 화면 — dart:io 함정, 조건부 import, 그리고 "웹은 따로 가볍게" 판단

## 문제

Android·Windows용으로 만든 Flutter 앱에 `flutter create . --platforms web`을 하면 **빌드는 성공**하는데, 브라우저에서 첫 화면이 안 뜬다(하얀 화면).
콘솔에 눈에 띄는 오류도 없다.

**실측(RVS_App, 2026-11-02)**: 원인은 시작 경로에서 웹에 없는 기능을 건드린 것 — `Platform.environment`(접속 주소·OAuth ID 읽기),
`dart:io` `File`(기기 설정·입력 임시 저장·오류 로그), `Platform.isAndroid`(알림·구글 로그인 분기), 알림 플러그인 초기화.

## 고치는 법(앱 구조를 지키면서)

1. **환경변수**: `platform_env.dart`가 조건부 export — `export 'platform_env_web.dart' if (dart.library.io) 'platform_env_io.dart';`
   웹은 빈 표(값은 빌드 때 `--dart-define`으로), 앱은 `Platform.environment`.
2. **기기 저장소**: 키-값 인터페이스(`read/write`) + 구현 둘 — 웹은 `package:web`의 `localStorage`, 앱·시험은 Map.
   `package:web`은 VM 시험에서 컴파일되지 않으므로 반드시 `if (dart.library.js_interop)` 조건부 import 뒤에 둔다. 설정 저장소(파일)는 그대로 두고 웹용 구현 클래스를 하나 더 만든다.
3. **OS 판별**: `Platform.isAndroid` 대신 `kIsWeb` 먼저, 그다음 `defaultTargetPlatform`. 웹에서 안 되는 기능(기기 알림, 플랫폼별 구글 로그인)은 `kIsWeb`이면 건너뛰고 안내만.
4. **`main.dart`**: `kIsWeb ? WebStore() : FileStore()`로 고르고 알림 초기화를 건너뛴다.
5. **포맷 주의**: `dart format lib` 전체를 돌리면 무관한 파일까지 바뀐다 — 바꾼 파일만 지정하고 `git status`로 확인한다.

## 확인할 때의 함정

- Flutter 웹(CanvasKit)은 그림이 **그림자 DOM 안의 캔버스**라 `document.querySelector`로 글자를 찾을 수 없고, 헤드리스 Chrome의 `--screenshot`·`--dump-dom`은 그리기 전에 끝나 빈 화면이 찍힌다.
  → `--remote-debugging-port`로 띄우고 CDP(`Page.captureScreenshot`, `Runtime.evaluate`, `Input.dispatchMouseEvent`)로 실제 시간을 기다려 찍는다.
- 확장이 없는 환경에서도 이 방식으로 클릭·입력까지 된다. 스크립트는 저장소 밖(임시 폴더)에 둔다.

## "웹은 Flutter 그대로 vs 가볍게 따로" 판단

| | Flutter 웹 그대로 | 웹만 가벼운 새 프로젝트(예: Vite+TS) |
|---|---|---|
| 첫 로딩 | 무겁다(RVS 실측 약 20MB: 앱 코드 3MB·엔진 2MB·한글 글꼴 14.7MB) | 수십 KB |
| 링크로 유입되는 웹(가입 없이 바로) | 불리 | 유리 |
| 화면·연출 자유도 | 앱과 같은 부품 | 웹 연출을 자유롭게 |
| 비용 | 한 벌 | 화면 두 벌 — **규칙은 서버로**(→ `다중클라이언트_규칙은_서버한곳_게임판정_도우미대사_패턴.md`) |

RVS는 "링크로 들어오는 게임형 웹"이라 따로 가볍게 갔다. 서버 호출·상태는 순수 TS 모듈로 두고 화면만 작은 함수로 짜 두면,
나중에 Svelte 등으로 옮길 때 화면만 바꾸면 된다. 그래도 Flutter 웹 대응(위 1~4)은 남겨 둘 가치가 있다 — 앱을 데스크톱 브라우저로 시험할 때 쓴다.

## 체크리스트

- [ ] 시작 경로에 `dart:io`·`Platform.*` 호출이 없다(웹에서 실행해 확인)
- [ ] 저장소·환경 읽기가 조건부 import로 갈라져 있고 VM 시험이 통과한다
- [ ] 웹에서 안 되는 기능은 `kIsWeb`로 건너뛰고 안내한다
- [ ] 확인은 CDP로 기다려 찍었다(헤드리스 스크린샷만 믿지 않는다)
