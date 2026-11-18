from logic.validate import validate_quiz

RULE = {"id": "gate", "sections": [{"heading": "원칙 — 열림"}]}


def quiz(**q):
    return {"rule_id": "gate", "questions": [q]}


SIT = "카운트 조회가 DB 장애로 실패했을 때 게이트는 무엇을 해야 하나요?"
EXP = "남용 방지 게이트는 자기 인프라 장애로 정상 사용자를 막지 않도록 열림 쪽으로 넘어가야 합니다."
SEC = "원칙 — 열림"
GOOD = {"rule_id": "gate", "questions": [
    {"id": "q1", "type": "choice", "situation": SIT, "options": ["막는다", "허용한다", "재시도만 한다"], "answer": 1,
     "explain": EXP, "section": SEC},
    {"id": "q2", "type": "spot", "situation": SIT, "code": "try:\n  n = count()\nexcept E:\n  return False\nreturn True",
     "answer_lines": [4], "explain": EXP, "section": SEC},
    {"id": "q3", "type": "scenario", "situation": SIT, "rubric": ["기준 하나", "기준 둘", "기준 셋"], "explain": EXP,
     "section": SEC},
]}


def test_valid_three_types_pass():
    assert validate_quiz(GOOD, {"gate": RULE}) == []


def strict_errs(**change):
    qs = [dict(q) for q in GOOD["questions"]]
    for k, v in change.items():
        n, field = k.split("__")
        n = n[1:]  # "q0" → "0"
        if v is None:
            qs[int(n)].pop(field)
        else:
            qs[int(n)][field] = v
    return " ".join(validate_quiz({"rule_id": "gate", "questions": qs}, {"gate": RULE}))


def test_strict_quiz_rules():
    assert "section" in strict_errs(q0__section=None)  # 모든 문제는 근거 절이 있어야 한다
    assert "situation" in strict_errs(q0__situation="짧음")
    assert "explain" in strict_errs(q1__explain="짧음")
    assert "options" in strict_errs(q0__options=["a", "b"])  # 보기 3개 이상
    assert "options" in strict_errs(q0__options=["a", "a", "b"])  # 보기 중복
    assert "code" in strict_errs(q1__code="a\nb\nc", q1__answer_lines=[2])  # 코드 4줄 이상
    assert "rubric" in strict_errs(q2__rubric=["하나", "둘"])  # 기준 3개 이상


def test_quiz_set_needs_three_questions_and_mixed_types():
    two = {"rule_id": "gate", "questions": GOOD["questions"][:2]}
    assert any("3문제" in e for e in validate_quiz(two, {"gate": RULE}))
    same = {"rule_id": "gate", "questions": [dict(GOOD["questions"][2], id=f"s{i}") for i in range(3)]}
    joined = " ".join(validate_quiz(same, {"gate": RULE}))
    assert "유형" in joined and "자동 채점" in joined


def test_rule_must_exist():
    errs = validate_quiz(quiz(id="q1", type="scenario", situation="s", rubric=["r"], explain="e"), {})
    assert any("rule_id" in e for e in errs)


def test_choice_answer_out_of_range():
    errs = validate_quiz(quiz(id="q1", type="choice", situation="s", options=["a", "b"], answer=2, explain="e"),
                         {"gate": RULE})
    assert any("answer" in e for e in errs)


def test_spot_line_outside_code():
    errs = validate_quiz(quiz(id="q1", type="spot", situation="s", code="a\nb", answer_lines=[5], explain="e"),
                         {"gate": RULE})
    assert any("answer_lines" in e for e in errs)


def test_unknown_section_and_duplicate_id():
    q = {"rule_id": "gate", "questions": [
        {"id": "q1", "type": "scenario", "situation": "s", "rubric": ["r"], "explain": "e", "section": "없는 절"},
        {"id": "q1", "type": "scenario", "situation": "s", "rubric": ["r"], "explain": "e"},
    ]}
    errs = validate_quiz(q, {"gate": RULE})
    assert any("section" in e for e in errs)
    assert any("중복" in e for e in errs)
