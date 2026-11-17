# Dart에서 이름있는 매개변수 그룹 뒤의 후행 쉼표는 `}`/`]` 안쪽에만 올 수 있다 (범용)

Dart(Flutter 포함) 메서드/함수 시그니처가 위치 인자 + 이름있는 매개변수
그룹(`{...}`, 또는 선택적 위치 매개변수 `[...]`)을 함께 쓸 때, 그 시그니처를
손으로 여러 줄로 재포맷하거나 다른 파일의 기존 시그니처를 옮겨적을 때 걸리는
순수 문법 함정.

## 함정

```dart
// ❌ 컴파일 에러 — "Expected to find ')'"
Future<int> bar(
  String stat, int tier, {bool isDayPass = false},
) async { ... }
```

```dart
// ✅ 정상 — 후행 쉼표가 `}` **안쪽**에 있고, `}`와 `)`가 같은 줄에 붙어있다
Future<int> bar(
  String stat, int tier, {bool isDayPass = false,
}) async { ... }
```

두 형태는 줄바꿈 위치만 다르고 겉보기엔 사소한 차이지만, Dart 문법상
후행 쉼표는 이름있는 매개변수 그룹 **안쪽**(마지막 매개변수 뒤, `}` 앞)에만
허용되고, `}` **뒤**에 또 쉼표를 두는 건 항상 무효다(줄바꿈 여부와 무관 —
같은 줄에 `{...}, )`로 붙여 써도 똑같이 에러). 기존에 정상 동작하던 파일의
시그니처를 복사해서 다른 곳(테스트 더블의 override 메서드 등)에 붙여넣는
과정에서 무심코 재포맷하다가 이 형태로 바뀌면, 원본과 "똑같아 보이는" 코드가
컴파일이 깨진다.

**드물게 친절한 함정** — 다른 유사 함정들(예: 다중 클래스 반복 치환 시
괄호가 엉뚱한 곳으로 새는 경우)과 달리, 이 에러는 실제 원인 줄·칼럼(후행
쉼표 위치)을 정확히 짚어준다 — `dart analyze`/`flutter analyze`/`flutter
test` 컴파일 단계가 전부 동일하게 정확한 위치를 보고하므로, 에러 메시지의
줄 번호를 그대로 믿고 그 지점의 쉼표/괄호 배치만 확인하면 빠르게 해결된다.

## 해법

1. 이름있는 매개변수 그룹으로 끝나는 시그니처를 여러 줄로 쓸 땐 항상
   `}) async {` 처럼 **닫는 `}`와 `)`를 같은 줄에 붙여 쓰고**, 후행 쉼표는
   그 직전(마지막 매개변수 뒤)에 둔다.
2. 다른 파일의 기존 시그니처를 복사할 때는 개행 위치까지 통째로 그대로
   옮기고, 옮기면서 임의로 재포맷하지 않는다 — 특히 여러 개의 override
   메서드를 연달아 작성할 때(테스트 더블/페이크 클라이언트 등) 자기도
   모르게 스타일을 "정리"하다가 이 형태로 바뀌기 쉽다.
3. `dart format <파일>`(또는 IDE의 포맷 온 세이브)을 신뢰할 수 있으면 그걸
   돌려서 정규 포맷으로 맞추는 게 가장 안전 — 이 규칙을 외울 필요 자체가
   없어진다.
4. 에러 메시지가 "Expected to find ')'" 이고 그 위치가 `{...}` 뒤 쉼표
   근처라면, 다른 원인을 찾아 헤매지 말고 이 패턴부터 의심한다.

## 실측 사례 (poker_app, 2026-09-15)

`poker_server_client.dart`에 실제로 동작하던
```dart
Future<PurchaseBuffCardResult> purchaseBuffCard(
  String stat, int tier, {bool isDayPass = false,
}) async { ... }
```
를 `test/ui/consortium_provider_test.dart`의 페이크 클라이언트(`_CardClient`)
override 메서드로 옮겨적으면서, 다른 override들과 시각적 통일감을 주려고
무심코
```dart
Future<PurchaseBuffCardResult> purchaseBuffCard(
  String stat, int tier, {bool isDayPass = false},
) async { ... }
```
로 재포맷 — `flutter test`가 정확히 그 줄·칼럼(닫는 `}` 바로 뒤 쉼표)을
"Expected to find ')'"로 짚어줘, `dart analyze`로 최소 재현(`class Foo {
Future<int> bar(String stat, int tier, {bool isDayPass = false}, ) async {
... }}`)까지 만들어 원인을 확정한 뒤 원본과 동일한 `}) async {` 형태로
되돌려 해결했다.
