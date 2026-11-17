# 패키지 `__getattr__`로 구현을 넘기는 모듈을 monkeypatch하면 전환이 고정된다

2026-11-15 신설(RVS_App `constraints` 패키지 — rules/noop 짝을 `__getattr__`로 전환).

## 증상

- 시험 하나에서 `monkeypatch.setattr(constraints, "guest_trial_enabled", lambda: True)`를 했더니, 그 뒤 **다른 시험의** `constraints.use("noop")` 전환이 안 먹고 엉뚱한 값이 나온다. 단독 실행은 통과, 전체 실행에서만 깨진다.

## 원인

- 패키지가 `__getattr__(name)`으로 "현재 구현(rules|noop)의 같은 이름"을 돌려주는 구조다. `setattr(패키지, name, ...)`은 **패키지 모듈 `__dict__`에 그 이름을 실제로 만든다.** 이후 접근은 `__getattr__`까지 안 가고 그 값(또는 monkeypatch 복원 시 남은 흔적)에 고정돼, 구현 전환이 이름 하나에 대해서만 안 먹는다.

## 지침

- 구현 모듈 쪽을 패치한다: `monkeypatch.setattr(constraints.rules, "_GUEST_POOL_DAILY", 20)` / `constraints.rules.guest_trial_enabled`. 패키지 객체에 직접 `setattr`하지 않는다.
- 값 전환이 목적이면 패키지가 제공하는 `use("noop")` 같은 공식 스위치를 쓰고, 시험 끝에 원복한다(autouse 픽스처).
- 이런 구조의 패키지를 새로 만들면 README/주석에 "패치는 구현 모듈에 한다"를 한 줄 적는다.
