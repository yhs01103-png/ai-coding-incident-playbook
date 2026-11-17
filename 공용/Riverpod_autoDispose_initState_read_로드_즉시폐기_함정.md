# Riverpod autoDispose provider를 initState에서 ref.read(...).load()로 채우면 바로 버려진다 (poker_app 실측, 2026-10-07)

## 증상
탭 화면(TabBarView)에서 두 번째·세 번째 탭이 무한 로딩. 서버 응답·JSON 파싱을 각각 단독으로 확인하면 정상이고, 오류 로그도 없다
(provider가 실패를 삼키고 false만 돌려주는 구조였다).

## 원인
- `StateNotifierProvider.autoDispose`를 화면 `initState`의 postFrame에서 `ref.read(p.notifier).load()`로 불렀다.
- 그 시점에 그 provider를 `watch`하는 위젯이 없었다(TabBarView는 보이는 탭만 만든다 — 첫 탭은 다른 provider를 본다).
- `ref.read`는 구독이 아니라서, 읽은 직후 리스너 0개 → autoDispose가 notifier를 폐기. `load()`는 폐기된 notifier에 state를 쓴다.
- 나중에 탭을 열면 `watch`가 **새** notifier를 만들어 초기값(null) → 로딩 표시 그대로.

## 해결
- 로드를 거는 화면이 그 provider를 `ref.watch(p)`로 붙잡는다(화면이 살아 있는 동안 유지). 또는
- 데이터를 쓰는 위젯(탭) 자신이 `initState`에서 load하게 하거나, `FutureProvider.autoDispose`처럼 watch가 곧 로드인 형태로.
- autoDispose를 빼는 건 마지막 수단(화면을 닫아도 메모리에 남는다).

## 점검 grep
`ref.read(` 로 `.load(` 를 부르는 곳 중 대상 provider가 `.autoDispose`인 것 → 같은 화면에 그 provider의 `ref.watch`가 있는지.
