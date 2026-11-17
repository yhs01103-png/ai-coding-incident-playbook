from logic.validate import validate_quiz

RULE = {"id": "gate", "sections": [{"heading": "원칙 — 열림"}]}


def quiz(**q):
    return {"rule_id": "gate", "questions": [q]}


def test_valid_three_types_pass():
    q = {"rule_id": "gate", "questions": [
        {"id": "q1", "type": "choice", "situation": "s", "options": ["a", "b"], "answer": 1, "explain": "e",
         "section": "원칙 — 열림"},
        {"id": "q2", "type": "spot", "situation": "s", "code": "a\nb\nc", "answer_lines": [2], "explain": "e"},
        {"id": "q3", "type": "scenario", "situation": "s", "rubric": ["기준"], "explain": "e"},
    ]}
    assert validate_quiz(q, {"gate": RULE}) == []


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
