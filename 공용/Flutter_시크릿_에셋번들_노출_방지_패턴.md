# Flutter 시크릿을 에셋 번들로 노출하지 않기 (범용)

`.env`를 pubspec `assets:`에 넣고 `flutter_dotenv`로 런타임 로드하는 흔한 패턴은,
빌드 산출물(APK/앱번들/Windows exe)에 `.env` 원본 파일이 **평문 그대로 패킹**된다는
치명적 함정이 있다. 앱 파일을 압축 해제(APK는 zip, exe도 flutter_assets 폴더가
그대로 딸려나감)하면 누구나 API 키/서버 주소를 그대로 꺼낼 수 있다.

## 핵심 문제

```yaml
# pubspec.yaml — 이렇게 하면 안 됨
flutter:
  assets:
    - .env
```

```dart
// main.dart — 이 조합이 위 문제를 만든다
await dotenv.load(fileName: '.env');
final apiKey = dotenv.env['GEMINI_API_KEY'];
```

`assets:`에 나열된 파일은 빌드 시점에 산출물 안에 **파일 그대로** 복사된다 —
컴파일되어 사라지는 게 아니다. `.gitignore`로 `.env`를 저장소에서 숨겨도 이 문제와는
무관하다(레포에는 안 올라가지만 빌드 산출물에는 그대로 들어간다는 게 이 함정의
핵심 — 두 가지는 완전히 다른 노출 경로).

## 해법 패턴 — dart-define 전환

값을 런타임에 파일로 로드하는 대신, **컴파일타임 상수**로 바이너리에 굽는다.

```dart
// lib/env/app_env.dart — 환경값 레이어, 아무것도 호출하지 않는다
class AppEnv {
  static const String baseUrl = String.fromEnvironment(
    'BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  static const String geminiApiKey = String.fromEnvironment('GEMINI_API_KEY');
}
```

값 주입은 로컬 실행/빌드 스크립트가 `--dart-define-from-file`로 자동 처리한다:

```powershell
# scripts/_dart_defines.ps1
# dart_defines.json은 저장소 루트, .gitignore 처리(실제 값). 커밋되는 건
# dart_defines.example.json(예시/플레이스홀더)뿐이다.
function Get-DartDefineArgs {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
    $definesFile = Join-Path $ProjectRoot "dart_defines.json"
    if (Test-Path $definesFile) {
        # 원소 1개짜리 배열을 return하면 PowerShell 파이프라인이 스칼라로
        # 풀어버려 호출부 @defineArgs 스플래팅이 깨진다(flutter가 "Target
        # file "-" not found"로 죽음, 실측) — unary comma로 감싸서 방지.
        return ,@("--dart-define-from-file=$definesFile")
    }
    Write-Warning "dart_defines.json 없음 — dart_defines.example.json 참고."
    return ,@()
}
```

```powershell
# scripts/run_local.ps1 / build_*.ps1 — ExtraArgs는 반드시 명시 파라미터로
# 받는다. 파라미터 블록 없이 자동변수 $args에 의존하면, _dart_defines.ps1을
# dot-source하는 순간 $args가 그 호출 자체의 인자(없음)로 덮어써져 flutter에
# 손상된 인자가 들어간다(실측 버그).
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $ExtraArgs = @())
. "$PSScriptRoot\_dart_defines.ps1"
$defineArgs = Get-DartDefineArgs
flutter run @ExtraArgs @defineArgs
```

체크리스트:
- `pubspec.yaml`의 `assets:`에서 `.env` 제거, `flutter_dotenv` 의존성 자체를 제거
  (남겨두면 다음 사람이 다시 쓸 여지가 생긴다)
- 값 소비처가 여러 파일에 흩어져 있으면(예: 서비스마다 `dotenv.get('BASE_URL', ...)`을
  각자 인라인으로 복제) 전부 `AppEnv` 같은 단일 창구로 모은다 — 흩어진 채로 두면
  하나 놓치고 지나가기 쉽다(아래 "실측" 참고)
- `.gitignore`에 `dart_defines.json` 추가(실제 키 포함), `dart_defines.example.json`만 커밋
- 수정 후 반드시 `flutter analyze`로 `Undefined name 'dotenv'` 같은 누락 참조가
  없는지 확인 — 여러 파일에 흩어진 소비처 중 하나를 편집 중 놓치는 실수가 실제로
  발생했다(아래 실측 3 참고)

## 런타임에 값을 바꿔야 하는 경우는 dart-define만으론 부족

dart-define은 컴파일타임에 고정되므로, "재시작 없이 서버 주소를 바꾸고 싶다"(설정
화면에서 로컬 서버로 전환 등)는 요구에는 안 맞는다. 이 경우 컴파일타임 기본값 +
런타임 오버라이드를 병행한다("push, 안 당김" 패턴 — 하위 호출부는 값의 출처를 몰라도
됨):

```dart
class JarvisPaths {
  static const String _compiledDefault = String.fromEnvironment('BASE_URL', ...);
  static String? _runtimeOverride;
  static void setBaseUrlOverride(String? url) { _runtimeOverride = url; }
  static String get baseUrl => _runtimeOverride ?? _compiledDefault;
}
```

이 런타임 오버라이드 자체의 설계(버전마커로 원격/로컬 자동전환할지, 언제 이게
오히려 과한지)는 `배포환경_버전마커_자동전환_런처_패턴.md` 참고 — 그 문서는 "어디로
붙을지"를 다루고, 이 문서는 "붙는 값 자체를 어떻게 안전하게 주입할지"를 다뤄
관심사가 분리된다.

## 핵심 교훈 — 한 프로젝트에서 고친 보안수정은 형제 프로젝트로 자동 전파되지 않는다

이 취약점은 같은 개발자의 형제 Flutter 프로젝트 3곳에서 **독립적으로 3번** 발견됐다
(Lazzy_App_OS_Monorepo에서 2026-08-06 최초 발견·수정 → Hub_App_winter에서
2026-08-20까지 미반영 상태로 남아있다 발견·수정 → AllAd Launcher에서 같은 날 세
번째로 발견·수정). 세 프로젝트 모두 같은 개발자가 만들었고 같은 패턴
(`flutter_dotenv` + `.env` in assets)을 각자 독립적으로 채택했을 뿐인데, 한 곳의
수정이 다른 곳에 저절로 퍼지지 않았다 — **코드는 프로젝트 경계를 넘어 스스로
전파되지 않는다**는 당연한 사실이, "이미 한 번 고쳤으니 안전하다"는 착각을 만들기
쉽다는 게 이 반복의 진짜 교훈이다.

같이 보기 — 이 사고(재보정이 "지금 보고 있는 대상"으로만 사정거리가 한정된
실측 사례)는 판단 메커니즘 자체를 다루는
`Coding_Nomal\모든_표본_일상_전략\탐색_판단_전환_모델\탐색_판단_전환_모델.md`
3-3절에서도 같은 근거로 인용된다 — 코드 레벨 수정은 여기서, 판단 구조 쪽
일반화는 그 문서에서.

**같은 스택을 공유하는 형제 프로젝트가 여러 개 있으면**, 보안수정 하나를 적용한
직후 다음 감사를 형제 프로젝트 전체에 돌린다:

```bash
# 형제 프로젝트들을 한 번에 훑는 감사 커맨드
grep -rln "assets:" --include="pubspec.yaml" <프로젝트루트들> | \
  xargs grep -l "\.env"
grep -rln "flutter_dotenv" --include="pubspec.yaml" <프로젝트루트들>
```

발견 즉시 전부 고치지 못하더라도, 이 감사를 **정기적으로 반복 가능한 절차**로
남겨두는 것 자체가 핵심이다 — 체크리스트 문서 하나를 만드는 것보다 실제로 grep을
돌려서 형제 프로젝트를 훑는 행동이 있어야 발견된다(이번 세 번째 발견도 사용자가
"루트에서 가져올만한거 가져와"라고 명시적으로 감사를 요청해서야 나왔다 — 자동으로는
안 드러났다).

## 실측 3 — 여러 파일에 흩어진 소비처는 수정 중 하나를 놓치기 쉽다

Hub_App_winter는 `baseUrl` getter가 5개 서비스 파일에 각자 인라인으로 중복
구현돼 있었다. 5개를 순서대로 고치던 중 `chat_classifier_service.dart` 한 곳을
빠뜨렸는데, `flutter analyze`가 `Undefined name 'dotenv'`로 즉시 잡아냈다 — 이런
류의 다중 파일 일괄 치환은 **눈으로 다 훑었다고 믿지 말고 `flutter analyze`(또는
동급 정적분석)를 마지막 검증 스텝으로 반드시 거친다.**

## 언제 이 패턴이 필요한가

- Flutter 앱이 API 키/서버 주소/토큰처럼 빌드 산출물에 노출되면 안 되는 값을
  `.env` + `flutter_dotenv`로 다루고 있을 때 — 특히 `pubspec.yaml`의 `assets:`
  목록에 `.env`가 직접 들어있으면 즉시 P0로 취급한다.
- 새 Flutter 프로젝트를 시작할 때 처음부터 이 패턴(dart-define + AppEnv +
  `_dart_defines.ps1`)으로 시작하면, 나중에 이미 배포된 빌드에 키가 노출된 뒤
  재발급하는 것보다 훨씬 싸다.
