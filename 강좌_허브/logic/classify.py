"""절 종류 판정, 관련 프로젝트·문서 링크 추출. 같은 입력이면 항상 같은 결과."""

import re

# 위에서부터 먼저 맞는 것을 쓴다. "실측 함정"은 case, "점검 grep"은 checklist.
KIND_TABLE = [
    ("related", ("함께 볼", "관련 문서")),
    ("case", ("실측", "사례", "적용")),
    ("checklist", ("체크리스트", "점검", "시험", "검증", "감사", "확인")),
    ("context", ("언제", "상황", "범위")),
    ("problem", ("문제", "증상", "함정", "원인", "왜 ", "주의", "하지 말", "놓치", "한계")),
    ("solution", ("해법", "해결", "원칙", "고치는 법", "완화", "지침", "패턴", "절차", "순서", "구조", "설계", "규칙")),
]
NUMBERED = re.compile(r"^\d+(-\d+)?\.\s")  # "3. …" 번호 항목은 규칙 본문
KINDS = {k for k, _ in KIND_TABLE} | {"other"}


def section_kind(heading: str) -> str:
    for kind, words in KIND_TABLE:
        if any(w in heading for w in words):
            return kind
    return "solution" if NUMBERED.match(heading) else "other"


def find_projects(text: str, project_names: list[str]) -> list[str]:
    # 프로젝트 이름을 하나의 정규식으로 묶어 본문을 한 번만 훑는다. 긴 이름 먼저(접두사 겹침 방지).
    if not project_names:
        return []
    names = "|".join(re.escape(p) for p in sorted(project_names, key=len, reverse=True))
    return sorted(set(re.findall(rf"(?<![\w])({names})(?![\w])", text)))


# 기술 스택 태그. 규칙은 제목·머리말·절 제목에 한 번, 또는 본문에 3번 이상 나오면 그 태그를 갖는다.
# 프로젝트 카드의 stack은 이 이름들 중에서만 고른다. 겹치면 "적용 가능 규칙"으로 연결된다.
TAGS = {
    "Flutter": ["Flutter", "Dart", "Riverpod", "위젯"],
    "Android": ["Android", "APK", "adb", "안드로이드", "접근성"],
    "로컬 저장소": ["Hive", "SQLite", "로컬 DB"],
    "FastAPI": ["FastAPI", "미들웨어", "dependency"],
    "Python": ["Python", "파이썬", "pytest", "mypy"],
    "LLM": ["LLM", "Gemini", "프롬프트", "임베딩"],
    "Windows": ["Windows", "PowerShell", "배치파일", "DPAPI", "cmd"],
    "결제·한도": ["결제", "지갑", "환불", "쿼터", "크레딧", "하루 예산"],
    "배포·운영": ["배포", "promote", "서비스용", "승격", "Railway", "Docker"],
    "보안·개인정보": ["시크릿", "암호화", "개인정보", "토큰", "비밀"],
    "웹": ["Vite", "TypeScript", "브라우저", "웹 클라이언트"],
    "AI 에이전트": ["MCP", "서브에이전트", "Claude Code", "CLAUDE.md"],
    "게이트": ["게이트", "레이트리미터", "fail-closed", "fail-open", "동시 요청"],
    # 아래는 단어로 판정하기 어려워 자동으로 붙지 않는다 — 태그_덮어쓰기.json과 프로젝트 stack에서만 쓴다.
    "설계·구조": [],
    "테스트": [],
    "Git·문서": [],
}


def find_tags(head: str, body: str) -> list[str]:
    out = []
    for tag, words in TAGS.items():
        if not words:
            continue
        rx = re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)
        if rx.search(head) or len(rx.findall(body)) >= 3:
            out.append(tag)
    return out


def apply_tag_overrides(rules: list[dict], overrides: dict) -> list[str]:
    """태그_덮어쓰기.json({규칙 id: [태그, ...]})이 자동 태그를 통째로 바꾼다. 없는 규칙·태그는 적용하지 않고 오류로 돌려준다."""
    by_id = {r["id"]: r for r in rules}
    errs = []
    for rid, tags in overrides.items():
        bad = [t for t in tags if t not in TAGS]
        if rid not in by_id:
            errs.append(f"태그_덮어쓰기: 없는 규칙 {rid!r}")
        elif bad:
            errs.append(f"태그_덮어쓰기: {rid} — 태그 목록에 없는 {bad}")
        else:
            by_id[rid]["tags"] = list(tags)
            by_id[rid]["tags_overridden"] = True
    return errs


def link_project_rules(project: dict, rules: list[dict]) -> tuple[list[str], list[dict]]:
    """실측 = 사례에 이 프로젝트가 나오는 규칙. 적용 가능 = 실측이 아니면서 스택 태그가 겹치는 규칙(많이 겹치는 순)."""
    real = sorted(r["id"] for r in rules if project["id"] in r.get("projects", []))
    stack = set(project.get("stack", []))
    appl = []
    for r in rules:
        if r["id"] in real:
            continue
        tags = r.get("tags", [])
        common = [t for t in TAGS if t in stack and t in tags]
        # 2개 이상 겹치거나, 태그가 하나뿐인 규칙이 그 하나로 맞을 때만 — 넓은 태그 하나로 우연히 걸리는 것을 뺀다.
        if len(common) >= 2 or (len(common) == 1 and len(tags) == 1):
            appl.append({"id": r["id"], "tags": common})
    appl.sort(key=lambda x: (-len(x["tags"]), x["id"]))
    return real, appl


MD_REF = re.compile(r"([^\s`'\"()\[\]<>/\\|,*]+)\.md")


def find_links(text: str, known_ids: set[str], self_id: str) -> list[str]:
    # 본문에서 "○○.md"를 한 번만 뽑아 문서 목록과 대조한다(문서마다 전체 목록을 훑으면 n×n이 된다).
    return sorted(({m for m in MD_REF.findall(text)} & known_ids) - {self_id})
