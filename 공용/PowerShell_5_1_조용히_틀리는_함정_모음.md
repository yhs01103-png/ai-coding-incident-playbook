# Windows PowerShell 5.1 — 에러 없이 조용히 틀린 값을 만드는 함정 모음 (범용)

PowerShell 5.1(Windows 기본 `powershell.exe`)에서 **에러 메시지 없이 틀린 결과**가 나오는 함정 모음. 전부 한 번의
작업 세션(스크립트 수십 개를 만들고 가짜 데이터로 테스트)에서 실제로 밟은 것이다. 특히 1·2번은 데이터를 조용히
손상시켜서 검증을 약하게 하면 못 잡는다(같이 보기: `데이터이전_검증_부분문자열존재확인_거짓통과_원본삭제전_양방향대조_패턴.md`).
파일 인코딩(BOM) 함정은 `Windows_배치파일_한글_유니코드_인코딩_함정.md` 함정 2에 있다.

## 함정 1 — 함수가 1요소 배열을 반환하면 스칼라로 풀려서 `(함수)[0]`이 "첫 글자"가 된다

```powershell
function L($f) { @(Get-Content $f) }        # 줄 배열을 돌려주려는 의도
(L 'oneline.txt')[0]                        # 한 줄짜리 파일 → 문자열 1개로 풀림 → [0] = 첫 "글자"
(L 'multiline.txt')[0]                      # 여러 줄 파일 → 정상: 첫 "줄"
```

여러 줄 파일에선 멀쩡하다가 **한 줄짜리 파일에서만** 값이 한 글자로 잘린다(실측: 한 줄짜리 비밀번호 파일 3개가 `백`, `노`, `B`
한 글자로 저장됨). 파이프라인 출력은 항상 열거되기 때문에 함수 안의 `@()`는 호출 결과를 보호해주지 못한다.
- 해결: 반환형을 `[string[]]`로 고정 — `function L($f) { [string[]](Get-Content $f) }`, 또는 `,@(...)`로 감싸 반환, 또는 호출부에서 `@(L $f)`.
- 한 줄짜리 입력(경계 케이스)을 **일부러 테스트 데이터에 넣는다**.

## 함정 2 — `ConvertFrom-Json`이 JSON 배열을 "배열 하나짜리 객체"로 내보낸다 (5.1)

`$x = Get-Content f.json -Raw | ConvertFrom-Json` 뒤 `@($x)`나 파이프로 다시 감싸면 **배열 안에 배열이 중첩**된다.
`foreach`/`Where-Object`가 요소가 아니라 통째 배열을 한 번만 돌고, 속성 접근은 멤버 열거로 겉보기에 맞는 척한다.
- 해결: 파이프 없이 대입한 뒤 `foreach`로 풀어낸다.
  ```powershell
  $parsed = ConvertFrom-Json (Get-Content f.json -Raw -Encoding UTF8)
  foreach ($x in $parsed) { $x }          # 요소 단위로 방출
  ```
- 반대로 저장할 때는 `ConvertTo-Json -InputObject @($items)`로 단일 요소도 배열로 유지한다(-InputObject 없이 파이프하면 요소 1개일 때 객체로 저장됨).

## 함정 3 — `"…$변수한글…"`에서 한글이 변수 이름의 일부가 된다

PowerShell은 한글도 식별자 문자로 본다. `"$count개 생성"`은 변수 `$count`가 아니라 **`$count개`**(없는 변수 → 빈 문자열)를
읽어 "개 생성"이 아니라 " 생성"이 된다. 에러가 없고 값만 사라진다.
- 해결: 항상 `"${count}개 생성"`. 한글 조사/단위가 붙는 보간은 전부 `${}`.
- 점검 grep: `\$[A-Za-z_][A-Za-z0-9_]*[가-힣]` (스크립트 전체에서 같은 패턴이 여러 번 재발했다).
- `"$i줄:"`처럼 `:`가 뒤따르면 별개 에러다 — `$i:`가 드라이브 한정자로 읽힌다(`${i}:`).

## 함정 4 — `@( … )`는 splat이 아니다

`& $cmd @($line -split ' ')`는 **배열 하나를 인자 하나로** 넘긴다(이후 `"System.Object[]"` 같은 문자열이 인자가 됨).
splat은 변수에만 쓴다: `$parts = $line -split ' '; & $cmd @parts`. 단일 요소 배열을 splat하려면 `@(…)`로 한 번 감싼 **변수**여야
하며, 문자열 변수를 splat하면 글자 단위로 풀린다(`$rest = 'list'; @rest` → `l i s t`).

## 함정 5 — 스크립트블록 안의 `$args`는 바깥 스크립트의 `$args`가 아니다

`Where-Object { $_.name -eq $args[0] }`의 `$args`는 블록 자신의 인자(빈 값) — 아무것도 매치되지 않고 조용히 else 분기로 간다.
블록 밖에서 `$first = $args[0]`로 복사해 쓴다.

## 함정 6 — 변수 이름은 대소문자를 구분하지 않는다

`$d = (파싱 결과)`가 앞에서 정의한 `$D = 'C:\폴더'`를 덮어써서 경로가 객체 문자열로 바뀐다(`Could not find a part of the path
'C:\…\@{schema=…}'`). 테스트 헬퍼 함수 안에서 흔하다 — 헬퍼의 지역 변수는 `$doc`처럼 겹칠 일 없는 이름으로.

## 함정 7 — `-like`는 `[ ]`를 문자 클래스로 해석한다

`$line -like '[이름]*'`는 "이/름 중 한 글자로 시작"이지 문자 그대로의 `[이름]`이 아니다. 대괄호가 든 고정 접두는 `.StartsWith('[이름]')`.
`Select-String`도 `-SimpleMatch`를 쓰지 않으면 정규식이다.

## 함정 8 — .NET 델리게이트로 바뀐 스크립트블록은 바깥 지역 변수를 못 본다

`[array]::FindIndex($lines, [Predicate[string]]{ param($s) $s -match $pat })`에서 `$pat`가 비어 있어 **전부 매치 → 인덱스 0**이
돌아온다(에러 없음, 엉뚱한 줄을 정답으로 사용). 줄 찾기는 일반 `for` 루프 함수로.

## 함정 9 — `Read-Host -AsSecureString`은 stdin 파이프를 읽지 않는다

비밀 입력을 파이프(`"비번" | powershell -File x.ps1`)로 자동 테스트하면 **무한 대기**한다(일반 `Read-Host`는 파이프가 먹는다).
프로덕션에 테스트 훅을 넣지 말고 격리 복사본에서 입력 함수만 치환한다(→ `Windows_DPAPI_로컬_비밀저장소_마스터비번_엔트로피_복원경로_패턴.md` §6).

## 함정 10 — `git commit -F -`에 here-string을 파이프하면 메시지가 "파일 경로"로 읽힌다 (RVS_App 2026-11-16)

`@'…'@ | git commit -F -`나 `git commit -q -F - @'…'@`처럼 쓰면 PowerShell이 here-string을 stdin이 아니라 **인자**로 넘겨
`error: pathspec '커밋 메시지 전문…' did not match any file(s) known to git`이 난다(커밋은 안 되고 스테이징은 남아 있어 다음 커밋에
섞일 수 있다 — 실제로 파일 3개가 스테이징된 채 남았다).

처방: 메시지를 **BOM 없는 UTF-8 파일**로 쓰고 `git commit -F 파일`로 커밋한다.
`[IO.File]::WriteAllText($path, $msg, (New-Object Text.UTF8Encoding $false))`. 커밋 직후 `git log --oneline -1`과 `git status --short`로
정말 커밋됐는지 확인한다(실패해도 다음 명령이 이어서 돌아가 성공처럼 보인다).

## 작성 직후 습관 (스크립트 하나 만들 때마다)

1. **UTF-8 BOM으로 저장**했는지(`Write` 계열 도구로 만든 파일은 BOM이 없다).
2. 실행 전 정적 구문 검사 한 줄 — 파싱 오류를 먼저 잡는다:
   ```powershell
   $e=$null; [void][Management.Automation.Language.Parser]::ParseFile($path,[ref]$null,[ref]$e); $e.Count
   ```
3. **한 줄짜리·빈 파일·요소 1개 배열** 같은 경계 입력으로 한 번 돌려 본다.
4. 가짜 데이터·임시 폴더에서 실행하고, 출력에는 비밀 값 대신 길이·일치 여부만 찍는다.

**실측 출처**: 개인 보안정보 폴더(`coding_admin`)의 비밀 저장소·허브 스크립트 작업(2026-10-20). 함정 1은 실제 비밀번호 3개를
한 글자로 저장해 사용자가 복구 스크립트를 따로 돌려야 했다.
