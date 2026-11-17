# FastAPI `@app.middleware("http")`가 연결 끊김을 막는다 — 요청 취소가 화면에서만 되고 서버는 끝까지 돌아 저장한다

2026-11-01 신설(RVS_App 실기기 점검에서 발견). 요청 취소(`request.is_disconnected()` 감시 → 저장 전 중단,
`JudgeCal_Athe/클라이언트_취소_서버_저장전_중단_중복쓰기_방지_패턴.md`)를 만들어 단위 테스트까지 통과시켰는데, **실제 서버에서는 한 번도 작동한 적이 없던** 사례다.

## 증상

- 앱은 "취소했어요"를 띄우고 입력을 남긴다 — 화면만 보면 정상.
- 서버 로그에는 취소한 요청이 끝까지 돌아 `status=ok`로 저장된다(역산·평행세계·정밀 예측 모두). 정밀 예측은 화면에 "한도는 쓰지 않았어요"라고 뜨는데 서버는 한도를 썼다.
- 기록 탭에 취소한 역산 카드가 남는다 — 이게 실기기에서 눈에 띈 첫 단서였다.

## 원인

`app.middleware("http")(함수)`로 붙인 미들웨어는 Starlette의 `BaseHTTPMiddleware`로 감싸진다. 이 래퍼가 라우트에 넘기는 `receive`는
연결 끊김(`http.disconnect`)을 전달하지 않아서, 라우트의 `await request.is_disconnected()`가 **끝까지 False**다. IP 제한·보안 헤더처럼
"요청마다 한 번 보고 지나가는" 흔한 미들웨어 하나만 있어도 생긴다.

확인한 실험(uvicorn을 실제로 띄우고 0.7초 뒤 소켓을 닫음):

| 앱 구성 | 라우트가 끊김을 봤나 |
|---|---|
| 미들웨어 없음 | True |
| `@app.middleware("http")`로 통과만 하는 미들웨어 1개 | **False** |

## 왜 테스트가 못 잡았나

- 감시 로직 테스트는 `is_disconnected()`만 흉내 내는 가짜 요청을 썼다 — 미들웨어를 안 거친다.
- `TestClient`도 실제 소켓이 없어 연결 끊김을 재현하지 못한다.
- 그래서 "감시 로직이 맞다"는 것과 "실제 요청에 신호가 닿는다"는 것이 따로 놀았다. 모의 테스트가 배선 결함을 가린 같은 계열의 함정이다
  (`JudgeCal_Athe/모킹된_테스트가_import_배선_결함을_가린다_함정.md`).

## 해법

미들웨어를 **순수 ASGI 클래스**로 바꾼다 — `receive`를 그대로 넘기므로 끊김 신호가 라우트까지 간다.

```python
class SecurityHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableHeaders(scope=message)   # starlette.datastructures
                for name, value in EXTRA.items():
                    if name not in headers:               # 라우트가 정한 값은 덮지 않는다(setdefault와 같게)
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(IpRateLimit)       # 등록 순서 규칙은 그대로 — 나중에 붙인 것이 바깥
app.add_middleware(SecurityHeaders)
app.add_middleware(CORSMiddleware, ...)
```

- 요청을 막는 미들웨어(IP 제한 429 등)는 `Request(scope)`로 헤더·IP만 읽고, 막을 때는 `await JSONResponse(...)(scope, receive, send)`로 응답한다.
- `@app.middleware("http")` → `app.add_middleware(클래스)`로 바꿔도 **순서 규칙(나중 등록이 바깥)은 같다** — CORS를 맨 바깥에 두던 이유(429에도 CORS 헤더)를 그대로 지킨다.

## 시험 — 진짜 서버로

1. **구조 확인**: `[m for m in app.user_middleware if m.cls is BaseHTTPMiddleware] == []` — 누가 `@app.middleware("http")`를 다시 붙이면 바로 걸린다.
2. **실제 소켓**: 같은 미들웨어를 단 작은 앱을 `uvicorn.Server(...)`로 스레드에서 띄우고(빈 포트), 원시 소켓으로 POST를 보낸 뒤 닫는다 →
   라우트 안의 취소 토큰이 True가 되는지 본다(`srv.started`를 기다린 뒤 보내고, 끝나면 `srv.should_exit = True`). 2초 안팎.
3. **수동 확인**: 서버를 띄우고 원시 소켓으로 오래 걸리는 요청을 보낸 뒤 2초 만에 닫는다 → 로그가 `status=ok`가 아니라 취소로 끝나고 저장이 없어야 한다.
   adb reverse 같은 터널을 의심하기 전에 이걸 먼저 해 보면 원인이 앱/터널이 아니라 서버라는 걸 바로 가른다.

## 범위·남는 것

- 끊김이 닿아도 **이미 나간 외부 호출(LLM 등)은 끝까지 기다린다** — 감시 토큰은 "다음 시도 전·저장 직전"에서만 멈춘다(설계대로). 실측: 취소 뒤 15~19초 걸린 호출은 끝까지 돌고 저장만 안 했다.
- 배포 앞단(프록시·로드밸런서)이 클라이언트 연결을 바로 끊어 주는지는 별개다 — 로컬에서 되는 것을 확인한 뒤 배포 환경에서 한 번 더 본다.
- `BaseHTTPMiddleware`는 스트리밍 응답·`BackgroundTasks`·ContextVar 전파에서도 알려진 제약이 있다 — 새 미들웨어는 처음부터 순수 ASGI로 쓰는 편이 낫다.

관련: `JudgeCal_Athe/클라이언트_취소_서버_저장전_중단_중복쓰기_방지_패턴.md`(취소 설계 본체), `공용/Flutter_실기기_adb_탭_스크린샷_자동검증_절차.md`(실기기에서 서버 로그와 화면을 같이 보는 법).
