"""규칙 JSON 고정 스키마 검사. 오류 문장 목록을 돌려주고, 비어 있으면 통과."""

import re

from logic.classify import KINDS, TAGS

PROJECT_STATUSES = {"운영", "개발 중", "보류", "완료"}
PROJECT_TEXT = ("id", "name", "category", "summary")
PROJECT_LISTS = ("stack", "design_points", "checks", "milestones")


def validate_project(p: dict, rule_ids: set[str]) -> list[str]:
    errs = [f"{f}: 비어 있음" for f in PROJECT_TEXT if not str(p.get(f, "")).strip()]
    errs += [f"{f}: 목록 아님 또는 없음" for f in PROJECT_LISTS if not isinstance(p.get(f), list)]
    if p.get("grade") not in (1, 2, 3, 4, 5):
        errs.append(f"grade: 1~5 아님 {p.get('grade')!r}")
    if p.get("status") not in PROJECT_STATUSES:
        errs.append(f"status: {sorted(PROJECT_STATUSES)} 중 하나가 아님 {p.get('status')!r}")
    errs += [f"stack: 태그 목록에 없는 {t!r}" for t in p.get("stack") or [] if t not in TAGS]
    for i, m in enumerate(p.get("milestones") or []):
        for f in ("ref", "title", "why", "changed"):
            if not str(m.get(f, "")).strip():
                errs.append(f"milestones[{i}].{f}: 비어 있음")
        errs += [f"milestones[{i}].rules: 없는 규칙 {r!r}" for r in m.get("rules", []) if r not in rule_ids]
        # 깊이 항목(버린 대안·검증·뒤집은 번호)은 선택 — 있으면 모양만 본다.
        rej = m.get("rejected")
        if rej is not None and (not isinstance(rej, list) or not all(isinstance(x, str) and x.strip() for x in rej)):
            errs.append(f"milestones[{i}].rejected: 빈칸 없는 문장 목록이어야 함")
        if "verified" in m and not str(m["verified"]).strip():
            errs.append(f"milestones[{i}].verified: 비어 있음")
        if "reverses" in m and not re.fullmatch(r"[A-Z]+-\d+", str(m["reverses"])):
            errs.append(f"milestones[{i}].reverses: 결정 번호(예: D-061) 아님 {m['reverses']!r}")
    return errs

TERM_TEXT = ("id", "term", "category", "short", "explain")
TERM_LISTS = ("aliases", "rules")
# 용어는 코드 개발 용어만 — 분류도 개발 분야로 고정한다.
TERM_CATEGORIES = ("설계·구조", "테스트·검증", "보안·개인정보", "운영·배포", "데이터·저장", "동시성", "언어·프레임워크", "AI·LLM")
TERM_SHORT_MAX = 40
TERM_EXPLAIN = (40, 300)


def appears(word: str, text: str) -> bool:
    return word.lower() in text.lower()


def validate_term(t: dict, rule_texts: dict[str, str]) -> list[str]:
    """용어\\<id>.json 고정 스키마: id, term, category, short(한 줄 뜻), explain, aliases[], rules[], example(선택).
    rule_texts = {규칙 id: 본문}. 연결한 규칙에 용어(또는 별칭)가 실제로 나와야 하고, 별칭은 어느 규칙에든 나와야 한다."""
    errs = [f"{f}: 비어 있음" for f in TERM_TEXT if not str(t.get(f, "")).strip()]
    errs += [f"{f}: 목록 아님 또는 없음" for f in TERM_LISTS if not isinstance(t.get(f), list)]
    if "example" in t and not isinstance(t["example"], str):
        errs.append("example: 문자열 아님")
    extra = set(t) - set(TERM_TEXT) - set(TERM_LISTS) - {"example"}
    errs += [f"모르는 칸 {k!r}" for k in sorted(extra)]
    if t.get("category") and t["category"] not in TERM_CATEGORIES:
        errs.append(f"category: {list(TERM_CATEGORIES)} 중 하나가 아님 {t['category']!r}")
    if len(str(t.get("short", ""))) > TERM_SHORT_MAX:
        errs.append(f"short: {TERM_SHORT_MAX}자 이하여야 함")
    lo, hi = TERM_EXPLAIN
    if t.get("explain") and not lo <= len(t["explain"]) <= hi:
        errs.append(f"explain: {lo}~{hi}자여야 함 (지금 {len(t['explain'])})")
    aliases = t.get("aliases") if isinstance(t.get("aliases"), list) else []
    rules = t.get("rules") if isinstance(t.get("rules"), list) else []
    if isinstance(t.get("rules"), list) and not rules:
        errs.append("rules: 연결 규칙이 1개 이상 필요")
    words = [t.get("term", ""), *aliases]
    for r in rules:
        if r not in rule_texts:
            errs.append(f"rules: 없는 규칙 {r!r}")
        elif not any(w and appears(w, rule_texts[r]) for w in words):
            errs.append(f"rules: {r} 본문에 용어·별칭이 안 나옴")
    for a in aliases:
        if len(str(a).strip()) < 2:
            errs.append(f"aliases: 너무 짧음 {a!r}")
        elif not any(appears(a, txt) for txt in rule_texts.values()):
            errs.append(f"aliases: 어느 규칙에도 안 나오는 별칭 {a!r}")
    return errs


def validate_term_set(terms: list[dict]) -> list[str]:
    """용어·별칭이 두 용어에 걸치면 밑줄이 어느 쪽인지 모호해진다."""
    owner, errs = {}, []
    for t in terms:
        for w in [t.get("term", ""), *(t.get("aliases") or [])]:
            key = str(w).lower()
            if key in owner and owner[key] != t.get("id"):
                errs.append(f"용어 겹침: {w!r} — {owner[key]}, {t.get('id')}")
            owner.setdefault(key, t.get("id"))
    return errs


RULE_FIELDS = {
    "id": str, "title": str, "short": str, "source": str, "intro": str,
    "sections": list, "projects": list, "links": list, "updated": str, "tags": list,
}
REQUIRED_TEXT = ("id", "title", "source", "updated")


def validate_rule(rule: dict) -> list[str]:
    errs = []
    for field, typ in RULE_FIELDS.items():
        if not isinstance(rule.get(field), typ):
            errs.append(f"{field}: {typ.__name__} 아님 또는 없음")
    for field in REQUIRED_TEXT:
        if isinstance(rule.get(field), str) and not rule[field].strip():
            errs.append(f"{field}: 비어 있음")
    sections = rule.get("sections")
    if isinstance(sections, list):
        if not sections:
            errs.append("sections: ## 절이 하나도 없음")
        for i, s in enumerate(sections):
            if s.get("kind") not in KINDS:
                errs.append(f"sections[{i}].kind: 허용되지 않은 값 {s.get('kind')!r}")
            if not str(s.get("heading", "")).strip():
                errs.append(f"sections[{i}].heading: 비어 있음")
    return errs


# 퀴즈 유형: choice(보기 고르기, 자동 채점) / spot(틀린 줄 찾기, 자동 채점) / scenario(기준표 자기 채점)
QUIZ_TYPES = {
    "choice": {"options": list, "answer": int},
    "spot": {"code": str, "answer_lines": list},
    "scenario": {"rubric": list},
}


# 퀴즈 기준(2026-11-18 강화): 규칙 하나에 3문제 이상, 유형 2가지 이상, 자동 채점 문제 1개 이상,
# 모든 문제에 근거 절(section). 상황·해설은 한 줄짜리가 아니라 판단 근거가 보일 만큼.
QUIZ_MIN_QUESTIONS = 3
SITUATION_MIN = 20
EXPLAIN_MIN = 30
CHOICE_OPTIONS = (3, 5)
SPOT_MIN_LINES = 4
RUBRIC_MIN = 3


def validate_quiz(quiz: dict, rules: dict) -> list[str]:
    errs = []
    rule = rules.get(quiz.get("rule_id"))
    if rule is None:
        return [f"rule_id: 규칙 {quiz.get('rule_id')!r}이(가) 없음"]
    headings = {s["heading"] for s in rule.get("sections", [])}
    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions: 문제가 하나도 없음"]
    if len(questions) < QUIZ_MIN_QUESTIONS:
        errs.append(f"questions: {QUIZ_MIN_QUESTIONS}문제 이상 필요 (지금 {len(questions)})")
    types = {q.get("type") for q in questions}
    if len(types) < 2:
        errs.append("questions: 유형이 2가지 이상이어야 함")
    if not types & {"choice", "spot"}:
        errs.append("questions: 자동 채점 문제(choice·spot)가 1개 이상 필요")

    seen = set()
    for n, q in enumerate(questions):
        at = f"questions[{n}]"
        qid = q.get("id")
        if not qid:
            errs.append(f"{at}.id: 비어 있음")
        elif qid in seen:
            errs.append(f"{at}.id: 중복 {qid!r}")
        seen.add(qid)
        for field, least in (("situation", SITUATION_MIN), ("explain", EXPLAIN_MIN)):
            if len(str(q.get(field, "")).strip()) < least:
                errs.append(f"{at}.{field}: {least}자 이상 필요")
        if "section" not in q:
            errs.append(f"{at}.section: 근거 절이 없음")
        elif q["section"] not in headings:
            errs.append(f"{at}.section: 규칙에 없는 절 {q['section']!r}")

        spec = QUIZ_TYPES.get(q.get("type"))
        if spec is None:
            errs.append(f"{at}.type: 허용되지 않은 값 {q.get('type')!r}")
            continue
        bad = [f for f, typ in spec.items() if not isinstance(q.get(f), typ)]
        errs += [f"{at}.{f}: 형식 오류 또는 없음" for f in bad]
        if bad:
            continue
        if q["type"] == "choice":
            lo, hi = CHOICE_OPTIONS
            opts = [str(o).strip() for o in q["options"]]
            if not lo <= len(opts) <= hi:
                errs.append(f"{at}.options: 보기 {lo}~{hi}개 필요")
            if len(set(opts)) != len(opts) or not all(opts):
                errs.append(f"{at}.options: 빈 보기 또는 중복 보기")
            if not 0 <= q["answer"] < len(q["options"]):
                errs.append(f"{at}.answer: 보기 범위 밖")
        elif q["type"] == "spot":
            total = len(q["code"].splitlines())
            if total < SPOT_MIN_LINES:
                errs.append(f"{at}.code: {SPOT_MIN_LINES}줄 이상 필요")
            lines = q["answer_lines"]
            if not lines or any(not isinstance(x, int) or not 1 <= x <= total for x in lines):
                errs.append(f"{at}.answer_lines: 코드 1~{total}줄 범위 밖이거나 비어 있음")
            elif len(set(lines)) != len(lines) or len(lines) >= total:
                errs.append(f"{at}.answer_lines: 중복이거나 모든 줄이 정답")
        elif len([r for r in q["rubric"] if str(r).strip()]) < RUBRIC_MIN:
            errs.append(f"{at}.rubric: 채점 기준 {RUBRIC_MIN}개 이상 필요")
    return errs
