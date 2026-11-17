# Windows DPAPI 로컬 비밀 저장소 — 마스터 비밀번호 엔트로피 + 복원 경로 (범용)

외부 서비스·설치 없이 Windows만으로 "평문 비밀번호 txt를 없애고, 스크립트 + 암호화 파일만 남기는" 개인용
저장소를 만들 때의 설계. 처음엔 `ConvertFrom-SecureString`(키 없이 쓰면 DPAPI)만으로 충분해 보이지만,
**DPAPI 단독은 "디스크 파일만 훔친 사람"만 막는다.** 아래 한계 둘을 메우는 구조가 이 문서의 내용이다.

## 1. DPAPI 단독의 한계 두 가지

1. **같은 Windows 계정으로 실행되는 모든 프로세스가 복호화할 수 있다.** 키 없이 `ConvertFrom-SecureString`으로 만든
   값은 "현재 사용자" 키로 묶일 뿐이라, 로그인된 채 방치된 PC·열려 있는 터미널·같은 계정의 다른 프로그램이면
   비밀번호 없이 `ConvertTo-SecureString`으로 전부 풀린다.
2. **계정/PC에 묶여 있어 복구 수단이 없다.** 윈도우 재설치, 관리자의 계정 비번 강제 초기화, 다른 PC로 이전하면
   암호화 파일이 영영 안 열린다.

## 2. 해결 구조 — 마스터 비밀번호에서 만든 키를 DPAPI의 추가 엔트로피로

```powershell
Add-Type -AssemblyName System.Security          # PS 5.1은 명시 로드 필요
function KeyFrom([string]$plain, [byte[]]$salt) {
    (New-Object Security.Cryptography.Rfc2898DeriveBytes($plain, $salt, 200000)).GetBytes(32)
}
function Enc([string]$s, [byte[]]$key) {
    [Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect(
        [Text.Encoding]::UTF8.GetBytes($s), $key, 'CurrentUser'))     # $key = optionalEntropy
}
function Dec([string]$h, [byte[]]$key) {
    [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect(
        [Convert]::FromBase64String($h), $key, 'CurrentUser'))
}
```

- 저장하는 것은 **salt(16바이트) + 확인용 blob**(`Enc 'vault-ok' $key`)뿐이다. 마스터 비밀번호도 그 해시도 저장하지 않는다.
- 잠금 해제 = 입력 비번으로 키 계산 → 확인 blob 복호화 시도. 틀리면 `Unprotect`가 예외 → **3회 제한** 후 종료.
- **엔트로피 없이 만든 값은 엔트로피를 준 `Unprotect`로 안 풀린다**(반대도 마찬가지) — 마스터 없이 DPAPI만으로 풀어
  보는 시도가 실제로 차단되는지 테스트에 넣는다.
- 이름·설명·키워드 같은 **비밀이 아닌 메타데이터는 평문으로 두고 비밀 필드(id/pw/memo)만 암호화**하면 목록·검색이
  잠금 없이 되고, 비밀 조회·추가·삭제·내보내기만 잠금 뒤에 둘 수 있다.

## 3. 해제된 키의 수명 — 터미널 세션에 남기지 않는다

허브 스크립트가 한 번 해제한 키를 하위 스크립트에 넘기려고 `$global:` 변수에 담는 구조는, **PowerShell 창에서 스크립트를
직접 실행하면 종료 후에도 그 터미널 세션에 키가 남아** 같은 창에서 다시 실행할 때 비밀번호를 안 묻는다.

```powershell
try { ...작업... } finally { $global:VaultEntropy = $null }   # 허브 종료 시 폐기
```

`cmd` 래퍼(.cmd)로 새 `powershell.exe`를 띄우는 경로는 프로세스가 끝나며 자동 소멸한다. 두 경로를 모두 테스트한다
(같은 세션에서 두 번째 실행이 비번을 다시 묻는지).

## 4. 형식 이전 · 비번 변경은 "전부 검증한 뒤에만 쓰기"

마스터 비밀번호 도입 전(DPAPI 단독) 항목을 옮길 때와 마스터 비밀번호를 바꿀 때 모두 같은 규칙이다.

1. 메모리에서 **전 항목을 복호화 → 새 키로 재암호화 → 각 항목을 다시 복호화해 원문과 같은지** 확인한다.
2. 하나라도 틀리면 예외로 중단 — 파일에는 아무것도 쓰지 않는다.
3. 통과하면 `vault.dat.tmp`·`vault.meta.tmp`에 먼저 쓰고 `Move-Item -Force`로 둘을 교체한다(중간 실패 시 기존 유지).
4. 이전용 옛 형식 복호화 코드는 이전 함수 안에서만 쓰고, 이전 뒤 옛 형식 파일(.bak)을 **남기지 않는다** — 남기면 그
   파일은 마스터 없이 DPAPI만으로 풀려서 잠금이 무의미해진다.

## 5. 복원 경로 — 평문 내보내기/가져오기

DPAPI는 계정/PC에 묶이므로(한계 2) **복구 수단은 평문 사본뿐**이다. `export <경로>`(복호화한 평문 파일)와
`import <경로>`(평문을 읽어 현재 환경의 마스터 비번으로 재암호화)를 처음부터 만든다.

- `import`는 마스터 비번이 아직 없으면 **새 마스터 비번 설정부터** 시작하게 해서 새 PC 복원이 한 번에 된다.
- 내보내기 파일에는 비밀번호가 그대로 들어가므로 **USB는 BitLocker To Go** 등으로 암호화하고, 설정 시점에
  "마스터 비밀번호 분실 시 복구 불가 — USB 평문이 유일한 복구 수단"을 안내한다.
- export → 저장소 삭제 → import → 다시 export 한 결과가 **바이트 단위로 같은지**로 왕복을 검증한다.
- 마스터 비번 자체는 저장하지 않으므로 "조회"는 만들 수 없다(변경만 가능) — 메뉴에서 오해하지 않게 명시.

## 6. 테스트 함정

- **`Read-Host -AsSecureString`은 stdin 파이프 입력을 읽지 않고 실제 콘솔을 기다린다** — `"비번" | powershell -File x.ps1`로
  테스트하면 무한 대기한다(일반 `Read-Host`는 파이프가 먹는다). 프로덕션 코드에 테스트 훅(환경변수로 비번 주입 등)을
  넣지 말고, **격리 복사본에서 입력 함수 한 줄만 치환**해서 돌린다.
  ```powershell
  $s = (Get-Content $copy -Raw).Replace('function ReadSecret([string]$prompt) {',
        'function ReadSecret([string]$prompt) { return (Read-Host $prompt)')
  ```
- **실제 저장소 복사본으로 "최초 이전" 경로를 테스트하면 이미 새 형식이라** 옛 형식 복호화에서 엉뚱한
  `FormatException`이 난다 — 코드 버그로 오인하기 쉽다. 옛 형식 가짜 데이터를 합성해서 테스트한다.
- 테스트는 가짜 항목·임시 폴더에서만 하고 끝나면 지운다. 출력에는 값 대신 **길이·일치 여부**만 찍는다.

## 체크리스트

- [ ] 값은 DPAPI + 마스터 파생 엔트로피로 암호화, 마스터/해시는 저장 안 함
- [ ] 마스터 없이 DPAPI만으로 푸는 시도가 실패하는 테스트
- [ ] 틀린 비번 N회 제한, 틀린 뒤 정상 비번 성공 테스트
- [ ] 이전·비번 변경: 전체 왕복 검증 후 tmp→교체, 평문/옛형식 잔존 파일 없음
- [ ] 허브 종료 시 키 폐기(같은 세션 재실행 시 비번 재요구 확인)
- [ ] export/import 왕복 동일성, 새 PC에서 import로 새 마스터 설정 가능
- [ ] 평문 사본(USB) 암호화 안내, 마스터 분실 경고

**실측 출처**: 개인 보안정보 폴더(`coding_admin`) — 평문 txt 6개를 암호화 저장소 + 허브 스크립트로 이전한 작업(2026-10-20).
