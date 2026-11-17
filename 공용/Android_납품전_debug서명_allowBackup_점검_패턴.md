# Android 앱을 납품·배포하기 전 점검 — debug 서명, allowBackup, 서명 경고가 안 보이는 문제 (범용)

Flutter 앱을 APK로 고객에게 넘기거나 배포하기 전에, 코드는 멀쩡해도 **빌드 설정이 개발용 그대로**인 경우가 많다.
Market_Agent_App(2026-10-07 실측)과 Lazzy_App_OS_Monorepo 클라이언트가 같은 기본 템플릿 상태였다.

## 1. release 빌드가 debug 키로 서명된다 (Flutter 기본 템플릿)

`android/app/build.gradle.kts`의 기본값은 release에도 `signingConfigs.getByName("debug")`를 쓴다(`flutter run --release`가
되게 하려는 템플릿 주석이 그대로 남아 있다). 결과:

- **업데이트가 막힌다** `[Android 일반 동작 — 이번에 키 불일치 설치는 재현 안 함]`. 같은 패키지 이름이라도 서명 키가 다르면 `adb install -r`/스토어 업데이트가
  `INSTALL_FAILED_UPDATE_INCOMPATIBLE`로 실패해 **앱을 지우고 다시 깔아야 하고, 그러면 앱 안 데이터가 사라진다.**
  debug 키로 한 번이라도 고객에게 나가면, 나중에 진짜 키로 바꾸는 순간 기존 고객은 전부 재설치가 필요하다.
- debug 인증서는 누구나 만들 수 있어 "내가 만든 앱"의 증거가 못 된다.
- **debug 키 서명 APK는 납품용이 아니다.**

**조치**: 키스토어 정보를 `android/key.properties`(저장소에 올리지 않음, `.gitignore`)에 두고 release 서명 설정을
읽게 한다. 파일이 없으면 개발 편의상 debug 키로 빌드하되 **경고를 낸다.** 서명 키 파일과 비밀번호는 **분실하면
복구할 수 없으니** 저장소 밖에 따로 백업한다. 납품할 모든 APK는 처음부터 이 키로 서명한다.

## 2. `allowBackup`을 지정하지 않으면 기본값이 "허용"이다

`AndroidManifest.xml`의 `<application>`에 `android:allowBackup`이 없으면 백업이 허용된다(Android 12+는
`dataExtractionRules`/`fullBackupContent`도 별도로 본다). 앱 데이터(대화·알림 박스 등)가 클라우드 백업과 `adb
backup`에 실려 나간다. 개인정보를 저장하는 앱은 `android:allowBackup="false"`로 둔다. 백업을 끄면 재설치 후
데이터는 복원되지 않는다 — 사용자가 백업에 의존하는 앱인지 먼저 확인한다.

점검(설치된 debug 앱): `adb shell dumpsys package <패키지> | grep -E "flags="` 에 `ALLOW_BACKUP`이 **없어야** 한다
(없으면 차단됨). 이번 실측: 수정 전엔 지정이 없었고 수정 후 `flags=[ DEBUGGABLE HAS_CODE ALLOW_CLEAR_USER_DATA ]`.

## 3. 서명 경고가 `flutter build` 출력에 안 나온다

`build.gradle.kts`의 `logger.warn("...key.properties 없음...")` 같은 경고는 `flutter build apk --release` 출력에
**나오지 않았다**(Gradle 로그를 Flutter가 걸러서 보여 줌, 이번 실측으로 확인). 경고가 안 보인다고 서명이 정상인
것이 아니다. **경고 대신 산출물을 직접 검사한다:**

```
JAVA_HOME="C:/Program Files/Android/Android Studio/jbr"   # apksigner는 java가 PATH/JAVA_HOME에 있어야 한다
apksigner.bat verify --print-certs build/app/outputs/flutter-apk/app-release.apk
# Signer #1 certificate DN: C=US, O=Android, CN=Android Debug   ← 이게 나오면 debug 서명
```

`apksigner`는 `%LOCALAPPDATA%\Android\Sdk\build-tools\<버전>\apksigner.bat`. `flutter doctor -v`의 "Java binary"가
JDK 위치를 알려 주고, 없으면 Android Studio의 `jbr` 폴더를 쓴다.

## 4. 설치가 "성공"처럼 보이는데 안 된 경우 (점검 시 같이 쓰는 확인)

`adb -s <기기> install ... | tail -1`처럼 파이프로 이어 쓰면 설치 실패여도 종료 코드가 0이 된다(파이프의 마지막
명령 코드). 기기가 USB에서 빠져 있어도 명령이 "기기를 기다리는 중"으로 멈췄다가 다음에 연결되면 이어서 진행한다.
설치 후에는 `dumpsys package <패키지> | grep lastUpdateTime`이 **기기의 현재 시각**으로 갱신됐는지로 확인한다.

## 5. 적용 사례: key.properties 폴백 + 세션 토큰 보안 저장 (JudgeCal, 2026-10-12)
- release 서명: `android/key.properties`(gitignore)가 있으면 그 키, 없으면 경고 후 debug 키로 폴백하게 gradle을 짜 두면 키가 없는 지금도 빌드가 깨지지 않고, 배포 때는 파일만 두면 된다. 키스토어는 사용자 확인 없이 만들지 않는다. 폴백 여부는 `java -jar build-tools/<ver>/lib/apksigner.jar verify --print-certs <apk>`의 DN으로 확인(.bat은 출력이 비는 경우가 있었다).
- 토큰 보안 저장: 저장소를 인터페이스(SecretStore)로 감싸 생성자로 주입해야 기존 테스트가 플러그인 없이 돈다. 기본값을 실제 플러그인으로 두면 `load`/`saveSession`을 부르는 기존 테스트가 응답 없이 멈추므로(실측), 해당 테스트 전부에 메모리 구현을 꽂는다.
- 옛 평문 값 이전은 "보안 저장소에 쓰기 → 다시 읽어 확인 → 옛 값 삭제" 순서. 보안 저장소 읽기 실패는 로그아웃으로 처리.
- OneDrive 폴더에서 `flutter test`가 멈추면 build/.dart_tool을 뺀 임시 복사본에서 돌린다(복사한 windows/flutter/ephemeral 링크는 지우고 pub get).

## 함께 볼 것
- 저장 데이터 암호화는 `Hive_암호화는_값만_키는_평문_함정_평문박스_1회이전_패턴.md` — 백업을 끄는 이유가 거기와 이어진다.
- 실기기 확인 절차는 `Flutter_실기기_adb_탭_스크린샷_자동검증_절차.md`.
