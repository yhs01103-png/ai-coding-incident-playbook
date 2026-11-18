import json
import re

from logic.classify import apply_short_titles, auto_short_title
from logic.package_plan import plan
from logic.publish_check import content_hash, quiz_public, rule_approval_text
from logic.render_html import render
from logic.validate import validate_term

TERM = {"id": "게이트", "term": "게이트", "category": "설계·구조", "short": "통과 여부를 정하는 코드",
        "explain": "호출 횟수·예산·동의 여부처럼 이 요청을 지금 처리해도 되는가를 판단하는 한 지점이다.",
        "aliases": ["레이트리미터"], "rules": ["a"]}
TEXTS = {"a": "레이트리미터/게이트는 자기 자신의 실패를 연다", "b": "무관한 본문"}


def test_auto_short_title_drops_suffix_and_subtitle():
    assert auto_short_title("Hive 암호화는 값만 — 키는 평문 (범용)") == "Hive 암호화는 값만"
    assert auto_short_title("그대로 제목") == "그대로 제목"


def test_short_title_overrides_and_errors():
    rules = [{"id": "a", "short": "자동"}, {"id": "b", "short": "자동"}]
    errs = apply_short_titles(rules, {"a": "직접 쓴 짧은 제목", "zz": "없는 규칙", "b": "가" * 31})
    assert rules[0]["short"] == "직접 쓴 짧은 제목"
    assert rules[1]["short"] == "자동"  # 너무 긴 덮어쓰기는 적용하지 않는다
    joined = " ".join(errs)
    assert "zz" in joined and "b" in joined


def test_short_title_is_part_of_rule_approval():
    md = "# 제목\n본문"
    assert rule_approval_text(md, "짧게").endswith("짧은 제목: 짧게")
    assert content_hash(rule_approval_text(md, "짧게")) != content_hash(rule_approval_text(md, "다르게"))


def test_quiz_needs_own_approval_and_approved_rule():
    assert quiz_public("pending", "approved") == "pending"
    assert quiz_public("approved", "pending") == "waiting_rule"
    assert quiz_public("approved", "approved") == "approved"
    assert quiz_public("blocked", "approved") == "blocked"


def test_validate_term():
    assert validate_term(TERM, TEXTS) == []
    bad = dict(TERM, short="", aliases="gate", rules=["zz"], category="잡담")
    joined = " ".join(validate_term(bad, TEXTS))
    for key in ("short", "aliases", "zz", "category"):
        assert key in joined, key


def test_term_must_really_appear_in_linked_rules():
    # 연결한 규칙 본문에 용어·별칭이 실제로 없으면 연결이 아니다.
    assert any("b" in e for e in validate_term(dict(TERM, rules=["a", "b"]), TEXTS))
    assert any("rules" in e for e in validate_term(dict(TERM, rules=[]), TEXTS))  # 규칙 하나 이상
    # 어느 규칙에도 안 나오는 별칭은 밑줄을 못 긋는 죽은 별칭
    assert any("gate" in e for e in validate_term(dict(TERM, aliases=["gate"]), TEXTS))
    assert any("explain" in e for e in validate_term(dict(TERM, explain="짧다"), TEXTS))


def test_aliases_must_not_overlap_between_terms():
    from logic.validate import validate_term_set
    other = dict(TERM, id="x", term="레이트리미터", aliases=[])
    assert any("레이트리미터" in e for e in validate_term_set([TERM, other]))


def test_public_render_keeps_only_approved_terms_and_public_rule_links():
    tpl = "<script>const DATA = /*__DATA__*/;</script>"
    rules = [{"id": "a", "title": "A", "projects": []}, {"id": "b", "title": "B", "projects": []}]
    terms = [dict(TERM, rules=["a", "b"]), dict(TERM, id="x", term="x")]
    status = {"a": {"status": "approved"}, "b": {"status": "pending"},
              "term:게이트": {"status": "approved"}, "term:x": {"status": "pending"}}
    html = render(tpl, rules, {}, status, {}, public_only=True, course_link="", terms=terms)
    d = json.loads(re.search(r"DATA = (.*);</script>", html, re.S).group(1))
    assert [t["id"] for t in d["terms"]] == ["게이트"]
    assert d["terms"][0]["rules"] == ["a"]


def test_plan_routes_quiz_and_term_keys_to_hub_folders():
    status = {"a": {"status": "approved"}, "quiz:a": {"status": "approved"}, "term:게이트": {"status": "approved"},
              "term:x": {"status": "pending"}}
    files = dict(plan(status, {"a": {"status": "approved"}}))
    assert files["강좌_허브/용어/게이트.json"] == ("hub", "용어/게이트.json")
    assert "강좌_허브/용어/x.json" not in files
    assert not any(d.startswith("공용/") and ":" in d for d in files)
    assert "공용/quiz:a.md" not in files
