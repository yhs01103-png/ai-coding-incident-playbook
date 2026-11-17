from logic.parse_md import parse
from logic.classify import section_kind, find_projects, find_links
from logic.validate import validate_rule

MD = """# 게이트 제목

머리 설명.

## 함정

본문 1

```python
# 코드 안 주석은 제목이 아니다
## 이것도 아니다
```

## 실측 사례 (poker_app, 2026-09)

RVS_App 에서도 재현. `Hive_암호화는_값만_키는_평문_함정.md` 참고.
"""


def test_parse_skips_headings_inside_code_fence():
    d = parse(MD)
    assert d["title"] == "게이트 제목"
    assert d["intro"] == "머리 설명."
    assert [s["heading"] for s in d["sections"]] == ["함정", "실측 사례 (poker_app, 2026-09)"]
    assert "# 코드 안 주석은 제목이 아니다" in d["sections"][0]["body"]


def test_section_kind_table():
    assert section_kind("함정 1 — 무엇") == "problem"
    assert section_kind("원칙 — 열림") == "solution"
    assert section_kind("실측 사례 (poker_app)") == "case"
    assert section_kind("체크리스트") == "checklist"
    assert section_kind("함께 볼 것") == "related"
    assert section_kind("언제 쓰나") == "context"
    assert section_kind("왜 테스트가 못 잡았나") == "problem"
    assert section_kind("3. 시험 — 가짜 서버로") == "checklist"
    assert section_kind("2. 보정은 사후 평균") == "solution"
    assert section_kind("Claude Code 공식 import") == "other"


def test_find_projects_and_links():
    assert find_projects(MD, ["poker_app", "RVS_App", "JudgeCal_Athe"]) == ["RVS_App", "poker_app"]
    assert find_links(MD, {"Hive_암호화는_값만_키는_평문_함정", "게이트"}, self_id="게이트") == [
        "Hive_암호화는_값만_키는_평문_함정"
    ]


def test_find_links_with_path_prefix_and_unknown_names():
    text = "참고: 공용/게이트_실패시_열림_패턴.md, (`없는_문서.md`) 그리고 README.md"
    ids = {"게이트_실패시_열림_패턴", "README_아님"}
    assert find_links(text, ids, self_id="x") == ["게이트_실패시_열림_패턴"]


def test_validate_rule_reports_missing_fields():
    good = {"id": "a", "title": "t", "source": "공용/a.md", "intro": "",
            "sections": [{"kind": "problem", "heading": "함정", "body": "x"}],
            "projects": [], "links": [], "updated": "2026-11-17", "tags": []}
    assert validate_rule(good) == []
    bad = dict(good, title="", sections=[{"kind": "zzz", "heading": "", "body": ""}])
    errs = validate_rule(bad)
    assert any("title" in e for e in errs)
    assert any("kind" in e for e in errs)
    assert any("heading" in e for e in errs)
