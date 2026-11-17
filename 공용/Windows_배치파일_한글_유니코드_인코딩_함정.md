# Windows 도구들의 BOM 없는 UTF-8 한글 오독 함정 (범용)

한글(또는 그 외 비-ASCII) 텍스트를 담은 소스/스크립트 파일을 Windows에서 다룰 때
반복적으로 재현되는 함정과 해결 패턴. 원래 `.cmd` 배치파일에서 시작했지만, 같은
근본 원인(BOM 없는 UTF-8을 시스템 ANSI 코드페이지로 오독)이 MSVC C++ 컴파일러에서도
그대로 재현돼 함정 3으로 추가됨(2026-08-12) — 특정 도구 하나의 버그가 아니라
"BOM 없는 UTF-8 + 한글 + Windows 시스템 코드페이지" 조합 자체가 여러 도구에서
반복되는 클래스의 문제로 확인됨. 함정 4(2026-08-19)는 방향이 반대(파일을
잘못 읽는 게 아니라 프로세스가 콘솔로 잘못 쓰는 것)지만 근본 원인
("Windows 코드페이지가 유니코드를 못 만나면 깨지거나 죽는다")은 같은
클래스라 여기 같이 묶었다. 함정 6(2026-09-02)은 파일도 콘솔도 아니라
**Git Bash 파이프로 두 프로세스(curl→python)를 잇는 경로**에서 재현돼,
API 러닝검증 중 실제로는 없는 버그를 있다고 오판하게 만든 사례다.
함정 7(2026-09-03)은 반대로 **실제로 있던 버그**다 — Windows 작업
스케줄러의 콘솔 없는 실행환경에서 PowerShell 파이프/.NET Process
스트림 둘 다 헤드리스 콘솔 프로그램에 한글 프롬프트를 못 넘기고,
cmd.exe의 OS 레벨 파일 리다이렉트(`<`/`>`)만 정상 동작한 사례. 특정
프로젝트에 종속되지 않음 — 어떤
워크스페이스에서든 한글이 든 텍스트를 Windows 환경에서 다룰 때(파일이든
프로세스 출력이든) 이 문서부터 참고한다.

## 함정 1 — cmd.exe 배치 파서가 파일 앞쪽 줄 개수에 따라 뒤 줄의 멀티바이트 텍스트를 깨뜨림

**증상**: 콘솔 코드페이지가 이미 UTF-8(65001)이고, 배치파일도 UTF-8로 저장했는데도
`cd /d <한글경로>` 줄이 "지정된 경로를 찾을 수 없습니다" 또는 `'일부단어'은(는) 내부
또는 외부 명령... 로 인식되지 않습니다` 식으로 실패한다.

**실측 확인된 재현 조건**: 한글(멀티바이트) 텍스트가 들어간 줄 **앞에 다른 줄이
하나라도 있으면** 깨진다 — `REM` 주석이든 그냥 `echo hi`든 종류 불문. 반대로 그
줄이 `@echo off` 바로 다음(파일의 두 번째 줄)에 오면 정상 동작한다. `chcp 65001`을
스크립트 안에 넣어도(앞쪽 줄이 하나 늘어날 뿐) 이 버그 자체는 해결되지 않는다 —
cmd.exe 배치 파서 자체의 오래된 결함이며 사용자 설정 문제가 아니다.

**부수 함정**: `REM` 주석 줄 안에 `&&`, `&`, `|`, `<`, `>` 같은 특수문자가 그대로
들어 있으면, `REM`이 그 줄 전체를 무해화해주지 않는다 — 파서가 특수문자를 먼저
토큰화하므로 `&&` 뒤에 오는 텍스트가 실제 명령으로 실행 시도된다(예:
`REM ...for &&: 어쩌고` → `&&` 뒤 텍스트가 명령으로 실행됨). 배치파일 주석에는
`&`, `|`, `<`, `>`를 쓰지 않는다.

## 함정 2 — Windows PowerShell 5.1이 BOM 없는 UTF-8 `.ps1`을 시스템 코드페이지로 오독

배치파일 대신 `.ps1`로 우회해도, **BOM 없이 UTF-8로 저장된 `.ps1` 파일**은 Windows
PowerShell 5.1(파워셸 코어 아님)에서 시스템 ANSI 코드페이지(한국어 Windows 기준
949)로 잘못 해석되어 한글이 깨진다(`Write` 계열 도구로 그냥 저장하면 보통 BOM 없는
UTF-8이 된다 — 이 경우 반드시 다시 저장해야 함). 반드시 **UTF-8 BOM 포함**으로
저장한다 — PowerShell의 `Set-Content -Encoding utf8` / `Out-File`(기본값)은 BOM을
자동으로 붙여준다.

**재발 사례(2026-10-20, 증상이 `?`가 아니라 "구문 오류"로 나옴)**: `Write` 계열 도구로 만든 일회용 복구 스크립트에 BOM을 안 붙였더니
실행하자마자 `Unexpected token '?덉씪?⑥씠_Javis_…txt') -replace …` 같은 **파싱 에러**가 났다 — 깨진 한글 바이트 안에 따옴표 역할 문자가
섞여 문자열 경계가 어긋났기 때문이다. 같은 작업에서 BOM을 붙인 스크립트는 멀쩡했으므로 "이 파일만 안 돌아간다"면 BOM부터 의심한다.
- 첫 3바이트 확인: `[IO.File]::ReadAllBytes($f)[0..2]` → `EF BB BF`여야 한다(`23 20 EC`처럼 `#`·공백·한글 첫 바이트가 나오면 BOM 없음).
- 만든 직후 습관: `Get-Content $f -Raw -Encoding UTF8` → `[IO.File]::WriteAllText($f, $텍스트, (New-Object Text.UTF8Encoding $true))`로
  BOM 재저장 + `[Management.Automation.Language.Parser]::ParseFile`로 정적 구문 검사 (`PowerShell_5_1_조용히_틀리는_함정_모음.md` 끝 절).

## 권장 해결 패턴 — cmd는 얇은 위임자, 실제 로직은 BOM 있는 .ps1

1. `.cmd` 파일은 **순수 ASCII만** 담고, 바로 옆의 `.ps1`을 호출하는 한 줄짜리
   위임자로만 쓴다(`%~dp0`로 같은 폴더 기준 상대경로 사용):
   ```bat
   @echo off
   powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0open_root.ps1"
   ```
2. 실제 한글 경로/로직은 `.ps1` 쪽에 담고, **UTF-8 BOM으로 저장**한다.
3. 경로 이동은 `cd /d <텍스트>`로 넘기지 말고, `Start-Process -WorkingDirectory <경로>`
   처럼 **구조화된 Unicode API**로 넘긴다 — 텍스트 커맨드라인 파싱을 거치지 않으므로
   함정 1의 버그 자체를 원천 회피한다.
   ```powershell
   $root = "C:\...\한글_경로"
   Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "claude" -WorkingDirectory $root
   ```

**실제 참고 구현**: `Coding_Nomal\모든_표본_일상_전략\scripts\Claude_Code_열기.cmd` +
`scripts\open_root.ps1` — 이 문서의 함정 1·2를 둘 다 실측으로 재현하고 위 패턴으로
고쳐서 검증된 실제 예시.

## 함정 3 — MSVC(cl.exe)도 BOM 없는 UTF-8 소스의 한글을 시스템 코드페이지로 오독

**증상**: BOM 없는 UTF-8로 저장한 `.cpp` 파일에 한글 주석을 넣고 빌드하면,
`warning C4819: 현재 코드 페이지(949)에서 표시할 수 없는 문자가 파일에 들어 있습니다`
경고가 뜬다. `/WX`(경고를 오류로 처리) 옵션이 켜진 프로젝트(Flutter Windows 러너의
`windows/CMakeLists.txt`가 기본으로 이렇게 설정함, `APPLY_STANDARD_SETTINGS` 함수의
`/W4 /WX`)에서는 이게 곧바로 **빌드 실패(에러 C2220)**로 이어진다.

**원인**: 함정 2(PowerShell 5.1)와 완전히 같은 근본 원인 — MSVC도 BOM 없는 UTF-8
소스 파일을 만나면 파일 내용을 유니코드로 신뢰하지 않고 시스템 ANSI 코드페이지
(한국어 Windows 기준 949)로 해석을 시도하다가, 949로 표현 안 되는 바이트 시퀀스를
만나면 경고를 낸다. 즉 "cmd.exe/PowerShell만의 함정"이 아니라 "BOM 없는 UTF-8을
시스템 코드페이지로 잘못 추측하는 Windows 도구 전반의 패턴"이라는 게 이번에 확인된
포인트.

**해결**: 파일을 **UTF-8 BOM 포함**으로 다시 저장한다. PowerShell에서:
```powershell
$path = "파일경로.cpp"
$content = [System.IO.File]::ReadAllText($path)
$utf8bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($path, $content, $utf8bom)
```
저장 후 첫 3바이트가 `239,187,191`(EF BB BF, UTF-8 BOM 시그니처)인지 확인:
```powershell
[System.IO.File]::ReadAllBytes($path)[0..2] -join ','
```

**실제 사례**: `windows/runner/main.cpp`(Flutter Windows 러너 진입점)에 한글 주석을
추가한 뒤 재현·해결(Lazzy_App_OS_Monorepo client, 2026-08-12) — 상세 배경은
`개인프로젝트_클라이언트서버_인증_설계_패턴.md`와 별개로,
[Flutter_Windows_로컬빌드_런타임_트러블슈팅.md](Flutter_Windows_로컬빌드_런타임_트러블슈팅.md)
참고(같은 세션에서 발견된 다른 Windows 로컬빌드 함정들과 묶어 정리).

## 함정 4 — Python 프로세스가 Windows 콘솔로 출력할 때 콘솔 코드페이지가
표현 못 하는 문자를 만나면 죽음(파일 읽기가 아니라 **출력** 쪽 함정)

함정 1~3은 전부 "파일을 잘못 읽는" 문제였는데, 이건 반대 방향 — Python이
`print()`로 콘솔에 **쓸 때** 콘솔 코드페이지(한국어 Windows 기본 cp949)가
표현 못 하는 문자(이모지, em-dash `—`, 일부 한글 조합)를 만나면
`UnicodeEncodeError`로 그 자리에서 죽는다(2026-08-19, kiwipiepy 토크나이저
결과·훅 스크립트 시뮬레이션 출력을 `python -c "print(...)"`로 직접 확인하다
반복 재현). git-bash/PowerShell 어느 쪽에서 Python을 띄워도 콘솔 자체의
코드페이지가 cp949면 동일하게 재현된다.

**구분해서 대응**:
- **사람이 읽는 디버그 출력**(터미널에서 눈으로 확인만 하면 됨) — 콘솔에
  바로 `print()`하지 말고, UTF-8로 파일에 써서(`open(path, 'w',
  encoding='utf-8')`) 그 파일을 다시 읽거나 `cat`으로 표시한다. 이번
  세션에서 실제로 쓴 패턴:
  ```python
  lines = [...]
  open('debug_out.txt', 'w', encoding='utf-8').write('\n'.join(lines))
  ```
- **기계가 파싱하는 출력**(JSON을 stdout으로 내보내 다른 프로세스가 읽는
  경우 — CLI 도구, pytest의 `subprocess.run` 캡처, Claude Code의 Bash 도구
  등) — 애초에 비-ASCII를 stdout에 안 실으면 된다. `json.dumps(...,
  ensure_ascii=True)`(기본값)로 한글/이모지를 전부 `\uXXXX` 이스케이프
  시퀀스로 내보내면, 콘솔 코드페이지가 뭐든 순수 ASCII만 지나가서 이
  함정 자체가 원천봉쇄된다 — 사람이 그 raw stdout을 직접 읽을 일이 없는
  기계-소비 전용 출력이면 이 방식이 가장 안전하다(SSOT_Explorer 프로젝트가
  라우터 CLI들에서 실제로 채택한 패턴 — 성공/에러 출력 둘 다 일관되게
  `ensure_ascii=True`로 통일해서, 한쪽만 예외로 원문 그대로 나가다 사고 나는
  걸 방지함).
- 굳이 콘솔에 유니코드를 그대로 찍어야 하면 `PYTHONIOENCODING=utf-8`
  환경변수를 그 프로세스에 지정하거나, 스크립트 안에서
  `sys.stdout.reconfigure(encoding="utf-8")`를 호출한다(단, 이래도 콘솔
  자체 폰트/렌더링이 그 문자를 못 그리면 화면엔 여전히 깨져 보일 수 있음 —
  인코딩 오류로 죽는 것과 화면에 깨져 보이는 건 별개 문제).

**재확인, 2026-08-21** — 직접 쓴 `print()`뿐 아니라 **stdlib이 대신 만들어
찍어주는 출력**도 똑같이 걸린다: `argparse`의 자동생성 `--help` 텍스트에
한글 설명 + em-dash(`—`)가 들어 있으면, `python cli.py --help`만 쳐도
Windows 기본 콘솔(cp949)에서 `UnicodeEncodeError`로 죽는다(SSOT_Explorer
`cli.py`, D-070 — 새 venv에 실제로 설치해서 `ssot --help`를 돌려보다가
실측 발견, 코드 리뷰만으론 안 보였음). 고친 방법은 위와 동일 —
`main()` 진입 시(파서 만들기 전) `sys.stdout`/`sys.stderr` 양쪽에
`reconfigure(encoding="utf-8")`를 시도하되, 그 메서드가 없는 스트림(리다
이렉트된 파이프 등)일 수도 있으니 `getattr`로 존재를 먼저 확인하고 예외를
삼킨다:
```python
def _fix_windows_console_encoding() -> None:
    import sys
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass
```
교훈: "내가 직접 print를 안 썼다"가 "이 함정에서 안전하다"의 증거가 아니다
— CLI 진입점을 새로 만들 때는 `--help` 하나도 실제 Windows 콘솔에서(또는
최소한 cp949를 흉내내는 환경에서) 한 번은 실행해보고 넘어간다.

## 함정 5 — CSV를 그냥 UTF-8로 저장하면 Excel이 한글을 깨뜨림(BOM 필요)

내보내기(export) 기능이 CSV를 순수 UTF-8(BOM 없음)로 저장하면, 그 파일을
**Excel로 열었을 때**(다른 프로그램이 아니라 Excel 한정 — 텍스트 에디터나
다른 도구는 문제없이 읽는다) 한글이 깨져 보인다. Excel의 CSV 가져오기가
BOM 없는 UTF-8을 시스템 기본 코드페이지로 오독하기 때문 — 함정 2·3과 같은
"BOM 없는 UTF-8을 Windows 도구가 시스템 코드페이지로 잘못 추측" 클래스의
또 다른 사례다.

**해법**: CSV로 저장할 때 `encoding='utf-8-sig'`를 쓴다(Python 기준) — 파일
맨 앞에 UTF-8 BOM을 자동으로 붙여줘서, Excel이 이 파일을 UTF-8로 정확히
인식하게 만든다:
```python
df.to_csv(path, encoding='utf-8-sig', index=False)
# 또는 csv.writer 직접 쓸 때:
with open(path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
```
CSV가 Excel이 아니라 다른 시스템(다른 프로그램으로 재파싱하는 파이프라인
등)으로만 소비된다면 이 문제가 안 생길 수 있지만, "사람이 Excel로 열어볼
가능성이 있는 CSV 내보내기"라면 기본값으로 `utf-8-sig`를 쓰는 게 안전하다.

## 함정 6 — Git Bash(MSYS2) curl→python 파이프가 멀쩡한 서버 응답을 깨뜨려 오탐을 유발

**증상**: Windows에서 Git Bash로 `curl ... | python -c "json.load(sys.stdin)"`을
실행해 로컬 API 서버의 한글 JSON 응답을 확인하면, 텍스트가 유니코드 론
서로게이트(`\udcXX`)로 깨져 나온다 — 서버가 실제로 깨진 텍스트를 반환한
것처럼 보인다.

**실측 확인된 재현/반증 조건**(JudgeCal_Athe 판단보정기 "앱 정밀 분석" 러닝
검증 라운드, 2026-09-02): 로컬 FastAPI 서버가 반환한 AI 폴백 서술 텍스트가
curl+Git Bash 파이프로는 깨져 보였다. 그러나 (1) 같은 SQLite 파일을 앱
코드 없이 독립 `sqlite3` 연결로 직접 열어보니 저장된 텍스트는 완전
정상이었고, (2) 같은 서버·같은 엔드포인트를 curl 대신 Python `httpx`
클라이언트로 재요청하니 완전 정상으로 돌아왔다. 즉 서버/DB는 처음부터
멀쩡했고, curl 결과를 Git Bash 파이프로 python에 넘기는 경로 자체가
손상의 원인이었다 — 최초엔 이걸 실제 앱 버그로 오판해 보고했다가
재검증으로 정정했다.

**원인**: 함정 4(Python 콘솔 출력)와 반대 방향 — 여기선 콘솔에 찍는 게
아니라 **두 네이티브 Windows 실행파일(curl.exe, python.exe) 사이를
MSYS2/Git-Bash 파이프가 중계**하면서 텍스트가 손상된다. 정확한 내부
메커니즘은 미확정(근본원인 규명보다 회피책 확보를 우선함).

**교훈 — 실행검증(러닝 테스트) 중 이상 텍스트를 만나면**:
- 결론을 내리기 전에 **관찰 채널을 하나 더 바꿔서 재현**한다 — (a) 저장소를
  앱 코드 없이 직접 열어보기, (b) 같은 요청을 다른 HTTP 클라이언트(Python
  `httpx`/`requests`, 브라우저 등)로 다시 보내보기 중 하나만 해봐도 "앱이
  깨진 것"과 "내 관찰 도구가 깨진 것"을 즉시 구분할 수 있다.
- Windows + Git Bash에서 curl로 한글 API를 테스트할 계획이면, 애초에
  `curl | python -c "..."` 파이프를 피하고 Python 스크립트 안에서
  `httpx`/`requests`로 직접 요청한다(가장 안전한 기본값).
- **요청 본문**(POST body)에 한글을 담아 보내는 것도 같은 파이프 계열로
  별개로 깨질 수 있다(같은 세션 실측 — curl `-d`에 한글을 주면 서버가
  "error parsing the body"로 거부, ASCII로 바꾸면 정상 동작) — 응답
  쪽(위 증상)과 요청 쪽 둘 다 Git Bash 파이프 함정이니, API 러닝검증
  자체를 Python 클라이언트 스크립트로 하는 게 근본적으로 더 안전하다.

## 함정 7 — Windows 작업 스케줄러 실행환경에서 PowerShell 파이프도 .NET
Process stdin도 콘솔 프로그램에 한글 프롬프트를 못 넘김 — OS 레벨 파일
리다이렉트(`<`/`>`)만 정상 동작

**증상**: `Get-Content $file -Raw | & "콘솔프로그램.exe" ...`(PowerShell
파이프)로 프롬프트 파일을 헤드리스 콘솔 프로그램에 stdin으로 넘기는
스크립트가, **인터랙티브 PowerShell 세션에서 직접 실행하면 완전히
정상**(대상 프로그램이 프롬프트를 받아 여러 턴에 걸쳐 실제 작업을
수행)인데, **같은 스크립트를 Windows 작업 스케줄러(Task Scheduler)로
트리거하면 프롬프트가 아예 전달 안 됨**(대상 프로그램이 빈 입력을 받은
것처럼 기본 응답만 하고 즉시 종료)이 실측 확인됐다(2026-09-03,
JudgeCal_Athe의 headless Claude Code 자동화 — 3일 연속 새벽 스케줄
실행이 전부 1턴/~2초 만에 "오늘 뭘 도와드릴까요?" 식 기본 인사만 하고
종료된 것을 발견, `Start-ScheduledTask`로 즉시 재현 확인).

**1차 시도가 실패한 이유(추가 함정)**: PowerShell 파이프 대신 .NET
`System.Diagnostics.Process`로 자식 프로세스의 `StandardInput`에 프롬프트
문자열을 직접 쓰는 방식으로 바꿔도 작업스케줄러 미전달 문제는 그대로
재현됐다. 게다가 이 방식은 **Windows PowerShell 5.1(.NET Framework
런타임)에는 `ProcessStartInfo.StandardInputEncoding`/`StandardOutput
Encoding`/`StandardErrorEncoding` 프로퍼티 자체가 없다**(.NET Core에서
추가된 프로퍼티라 .NET Framework에선 없는 멤버라는 비종료 오류가 나며
조용히 무시된다 — 스크립트는 계속 실행됨)는 별개 함정까지 새로 만든다.
그 결과 인코딩이 시스템 기본값으로 새어나가 **영어 프롬프트는 정상
동작하는데 한글 프롬프트만 복구 불가능하게 깨짐**(대상 프로그램이
"입력이 깨진 인코딩(mojibake) 상태라 읽을 수 없다"고 인식할 정도).
`$proc.StandardInput.BaseStream`을 UTF8 `StreamWriter`로 직접 감싸
쓰는 우회도 동일하게 실패했다 — 정확한 내부 메커니즘은 미확정.

**원인**: 작업 스케줄러가 콘솔 없이 프로세스를 띄우는 실행 환경 자체가,
PowerShell 파이프든 .NET Process의 스트림 리다이렉션이든 상관없이
자식 프로세스로의 stdin 전달 경로에 영향을 준다 — 인터랙티브 콘솔
세션에서 파이프/스트림이 동작하는 방식과 콘솔이 아예 없는 세션에서
그것들이 동작하는 방식이 근본적으로 다르다(함정 4가 "콘솔에 쓸 때"의
문제였다면, 이건 "콘솔이 아예 없을 때 자식 프로세스에 읽힐 때"의
문제 — 같은 큰 원인 계열의 반대쪽 변종).

**해법 — cmd.exe의 OS 레벨 파일 리다이렉트로 완전히 우회**: PowerShell
파이프도 .NET Process도 아니라, **OS가 파일을 그대로 stdin/stdout
핸들로 연결해주는 `<`/`>` 리다이렉트**(PowerShell엔 `<` 연산자 자체가
없으므로 `cmd.exe /c`로 감싼 작은 `.bat` 헬퍼를 통해서만 쓸 수 있다)로
교체하면 콘솔 유무와 무관하게 안정적으로 동작한다:

```bat
@echo off
REM 인자: %1=기타 옵션 등, %2=프롬프트 파일 경로, %3=출력 파일 경로
"콘솔프로그램.exe" [옵션] < "%~2" > "%~3" 2>&1
```

PowerShell 쪽에서는 이 `.bat`을 인자와 함께 호출하기만 하면 된다:
```powershell
& "$repoRoot\scripts\run_headless.bat" $arg1 $promptPath $outFile
```

**검증 방법**: 실제 작업(수십 KB 프롬프트, 수십 분 소요, 비용 발생)으로
바로 검증하지 말고, 먼저 짧은 한글 왕복 테스트로 저렴하게 확인한다 —
"다음 한 단어만 정확히 그대로 답하라: 감자"류 프롬프트를 파일로 써서
넘기고, 응답이 정확히 그 단어와 일치하는지 **Python에서 문자열 비교로
직접 확인**(터미널에 출력해서 눈으로 보면 함정 4/6에 또 걸려 오탐이
날 수 있음 — `d['result'] == '감자'`처럼 비교 결과만 파일에 써서
확인). 이 저렴한 재현이 통과하면 인터랙티브·`Start-ScheduledTask`(작업
스케줄러를 지금 바로 한 번 수동 트리거하는 커맨드) 양쪽에서 각각
확인한 뒤에만 실제 프롬프트로 최종 검증한다.

**일반화**: 파이프/스트림 리다이렉션을 쓰는 Windows 자동화(작업
스케줄러, 서비스로 등록된 프로세스 등)가 인터랙티브 세션에서는 되는데
무인 실행 환경에서만 이상하게 동작하면, 전달 메커니즘 자체(파이프→
.NET Process 등)를 바꾸기 전에 "콘솔이 아예 없는 조건"을 의심하고
OS 레벨 파일 리다이렉트로 완전히 우회하는 걸 먼저 시도해본다 —
`Windows_작업스케줄러_bare_python_PATH_함정.md`와 같은 "인터랙티브
셸과 무인 실행 환경은 다르다"는 원칙의 또 다른 사례.
