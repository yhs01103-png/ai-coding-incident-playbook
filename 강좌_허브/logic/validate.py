"""규칙 JSON 고정 스키마 검사. 오류 문장 목록을 돌려주고, 비어 있으면 통과."""

from logic.classify import KINDS, TAGS

PROJECT_STATUSES = {"운영", "개발 중", "보류", "완료"}
PROJECT_TEXT = ("id", "name", "category", "summary")
PROJECT_LISTS = ("stack", "design_points", "checks", "milestones")


def validate_project(p: dict, rule_ids: set[str]) -> list[str]:
    errs = [f"{f}: 비어 있음" for f in PROJECT_TEXT if not str(p.get(f, "")).strip()]
    errs += [f"{f}: 목록 아님 또는 없음" for f in PROJECT_LISTS if not isinstance(p.get(f), list)]
    if p.get("grade") not in (1, 2, 3, 4):
        errs.append(f"grade: 1~4 아님 {p.get('grade')!r}")
    if p.get("status") not in PROJECT_STATUSES:
        errs.append(f"status: {sorted(PROJECT_STATUSES)} 중 하나가 아님 {p.get('status')!r}")
    errs += [f"stack: 태그 목록에 없는 {t!r}" for t in p.get("stack") or [] if t not in TAGS]
    for i, m in enumerate(p.get("milestones") or []):
        for f in ("ref", "title", "why", "changed"):
            if not str(m.get(f, "")).strip():
                errs.append(f"milestones[{i}].{f}: 비어 있음")
        errs += [f"milestones[{i}].rules: 없는 규칙 {r!r}" for r in m.get("rules", []) if r not in rule_ids]
    return errs

RULE_FIELDS = {
    "id": str, "title": str, "source": str, "intro": str,
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


def validate_quiz(quiz: dict, rules: dict) -> list[str]:
    errs = []
    rule = rules.get(quiz.get("rule_id"))
    if rule is None:
        return [f"rule_id: 규칙 {quiz.get('rule_id')!r}이(가) 없음"]
    headings = {s["heading"] for s in rule.get("sections", [])}
    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions: 문제가 하나도 없음"]

    seen = set()
    for n, q in enumerate(questions):
        at = f"questions[{n}]"
        qid = q.get("id")
        if not qid:
            errs.append(f"{at}.id: 비어 있음")
        elif qid in seen:
            errs.append(f"{at}.id: 중복 {qid!r}")
        seen.add(qid)
        for field in ("situation", "explain"):
            if not str(q.get(field, "")).strip():
                errs.append(f"{at}.{field}: 비어 있음")
        if "section" in q and q["section"] not in headings:
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
            if len(q["options"]) < 2:
                errs.append(f"{at}.options: 보기 2개 이상 필요")
            if not 0 <= q["answer"] < len(q["options"]):
                errs.append(f"{at}.answer: 보기 범위 밖")
        elif q["type"] == "spot":
            total = len(q["code"].splitlines())
            if not q["answer_lines"] or any(not isinstance(x, int) or not 1 <= x <= total for x in q["answer_lines"]):
                errs.append(f"{at}.answer_lines: 코드 1~{total}줄 범위 밖이거나 비어 있음")
        elif not q["rubric"]:
            errs.append(f"{at}.rubric: 채점 기준이 비어 있음")
    return errs
