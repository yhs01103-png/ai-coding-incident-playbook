from logic.export import export_item, parts_of

RULE = {"id": "g", "title": "긴 제목", "short": "짧은 제목", "intro": "머리말", "tags": ["게이트"], "projects": ["P"],
        "sections": [{"kind": "problem", "heading": "함정", "body": "본문1"},
                     {"kind": "solution", "heading": "원칙", "body": "본문2"}]}
QUIZ = {"rule_id": "g", "questions": [{"id": "q1", "type": "choice", "situation": "상황1"},
                                      {"id": "q2", "type": "scenario", "situation": "상황2"}]}


def test_parts_of_lists_selectable_pieces():
    assert [k for k, _ in parts_of("rule", RULE)] == ["intro", "s0", "s1"]
    assert [k for k, _ in parts_of("quiz", QUIZ)] == ["q0", "q1"]


def test_export_only_selected_parts_with_context():
    out = export_item("rule", "g", RULE, ["s1"], status="approved", hits=[])
    assert out["id"] == "g" and out["short"] == "짧은 제목" and out["title"] == "긴 제목"
    assert out["parts"] == [{"part": "section", "kind": "solution", "heading": "원칙", "body": "본문2"}]


def test_export_everything_when_nothing_selected_and_keeps_hit_warning():
    out = export_item("quiz", "quiz:g", QUIZ, [], status="pending", hits=[{"line": 3, "label": "이메일", "match": "x"}])
    assert [p["id"] for p in out["parts"]] == ["q1", "q2"]
    assert out["warnings"] == ["3줄 이메일"]  # 밖에 붙이기 전에 볼 수 있게
