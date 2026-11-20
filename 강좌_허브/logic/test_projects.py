from logic.classify import TAGS, find_tags, link_project_rules
from logic.validate import validate_project


def test_find_tags_from_title_or_repeated_body():
    tags = find_tags("Hive 암호화는 값만 — Flutter 앱", "본문에 Gemini 한 번")
    assert "로컬 저장소" in tags and "Flutter" in tags
    assert "LLM" not in tags  # 본문에 한 번 나온 건 태그가 아니다
    assert "LLM" in find_tags("제목", "Gemini 호출, Gemini 재시도, 임베딩")


def test_link_project_rules_real_first_then_applicable_by_overlap():
    rules = [
        {"id": "a", "title": "A", "projects": ["P"], "tags": ["Flutter"]},
        {"id": "b", "title": "B", "projects": [], "tags": ["Flutter", "LLM"]},
        {"id": "c", "title": "C", "projects": [], "tags": ["LLM"]},
        {"id": "d", "title": "D", "projects": [], "tags": ["Windows"]},
        {"id": "e", "title": "E", "projects": [], "tags": ["Flutter", "Windows"]},
    ]
    real, appl = link_project_rules({"id": "P", "stack": ["Flutter", "LLM"]}, rules)
    assert real == ["a"]
    # 겹침 2개(b)가 먼저, 태그가 하나뿐인 규칙은 그 하나가 맞으면 포함(c).
    # 태그 2개 중 1개만 겹치는 규칙(e)은 우연히 걸린 것이라 뺀다. 실측(a)·무관(d)도 제외.
    assert [x["id"] for x in appl] == ["b", "c"]
    assert appl[0]["tags"] == ["Flutter", "LLM"]


GOOD = {
    "id": "P", "name": "앱", "category": "모바일", "grade": 3, "status": "개발 중",
    "stack": ["Flutter"], "summary": "요약", "design_points": ["점"], "checks": ["확인"],
    "milestones": [{"ref": "D-001", "date": "2026-10-01", "title": "제목", "why": "이유", "changed": "바뀐 것",
                    "rules": ["a"]}],
}


def test_validate_project_ok():
    assert validate_project(GOOD, {"a"}) == []


def test_validate_project_catches_bad_values():
    assert validate_project(dict(GOOD, grade=5), {"a"}) == []  # ★5 운영 설계
    bad = dict(GOOD, grade=6, status="몰라", stack=["없는태그"],
               milestones=[{"ref": "", "title": "t", "why": "", "changed": "c", "rules": ["zz"]}])
    errs = " ".join(validate_project(bad, {"a"}))
    for key in ("grade", "status", "stack", "ref", "why", "zz"):
        assert key in errs, key


def test_validate_project_milestone_depth_fields():
    deep = {"ref": "D-002", "title": "t", "why": "w", "changed": "c", "rules": [],
            "rejected": ["버튼 단계 — 사람이 먼저 알아챌 일이 없음"], "verified": "테스트 12건 통과", "reverses": "D-001"}
    assert validate_project(dict(GOOD, milestones=[deep]), {"a"}) == []
    bad = dict(deep, rejected="문자열", verified="  ", reverses="예전 결정")
    errs = " ".join(validate_project(dict(GOOD, milestones=[bad]), {"a"}))
    for key in ("rejected", "verified", "reverses"):
        assert key in errs, key
    errs = " ".join(validate_project(dict(GOOD, milestones=[dict(deep, rejected=["", 3])]), {"a"}))
    assert "rejected" in errs


def test_tag_overrides_replace_auto_tags_and_report_bad_entries():
    from logic.classify import apply_tag_overrides
    rules = [{"id": "a", "tags": ["Flutter", "LLM"]}, {"id": "b", "tags": ["Windows"]}]
    errs = apply_tag_overrides(rules, {"a": ["Windows"], "zz": ["Flutter"], "b": ["없는태그"]})
    assert rules[0]["tags"] == ["Windows"] and rules[0]["tags_overridden"] is True
    assert rules[1]["tags"] == ["Windows"]  # 잘못된 덮어쓰기는 적용하지 않는다
    joined = " ".join(errs)
    assert "zz" in joined and "없는태그" in joined


def test_tag_vocabulary_is_fixed():
    assert "Flutter" in TAGS and "LLM" in TAGS
