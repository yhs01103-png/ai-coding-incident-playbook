import json
import re

from logic.render_html import render

TEMPLATE = "<html><script>const DATA = /*__DATA__*/;</script></html>"
RULES = [
    {"id": "a", "title": "A", "sections": [], "projects": ["RVS_App"], "body": "x"},
    {"id": "b", "title": "</script><b>", "sections": [], "projects": [], "body": "y"},
]
QUIZZES = {"a": {"rule_id": "a", "questions": []}, "b": {"rule_id": "b", "questions": []}}
STATUS = {"a": {"status": "approved"}, "b": {"status": "pending"}}
QSTATUS = {"a": {"status": "approved"}, "b": {"status": "waiting_rule"}}


def data_of(html):
    raw = re.search(r"const DATA = (.*);</script></html>$", html, re.S).group(1)
    return json.loads(raw)


def test_dev_build_has_everything_with_public_flag():
    d = data_of(render(TEMPLATE, RULES, QUIZZES, STATUS, QSTATUS, public_only=False, course_link="c.html"))
    assert [r["id"] for r in d["rules"]] == ["a", "b"]
    assert [r["public"] for r in d["rules"]] == [True, False]
    assert set(d["quizzes"]) == {"a", "b"}
    assert d["course_link"] == "c.html"


def test_public_build_keeps_only_approved():
    d = data_of(render(TEMPLATE, RULES, QUIZZES, STATUS, QSTATUS, public_only=True, course_link=""))
    assert [r["id"] for r in d["rules"]] == ["a"]
    assert set(d["quizzes"]) == {"a"}


def test_public_build_filters_projects_method_and_rule_links():
    projects = [
        {"id": "P", "rules_real": ["a", "b"], "rules_applicable": [{"id": "b", "tags": ["x"]}],
         "milestones": [{"ref": "D-1", "rules": ["a", "b"]}]},
        {"id": "Q", "rules_real": [], "rules_applicable": [], "milestones": []},
    ]
    status = {**STATUS, "project:P": {"status": "approved"}, "project:Q": {"status": "pending"},
              "project:_기록방식": {"status": "pending"}}
    d = data_of(render(TEMPLATE, RULES, QUIZZES, status, QSTATUS, public_only=True, course_link="",
                       projects=projects, method="방식"))
    assert [p["id"] for p in d["projects"]] == ["P"]  # 승인 안 된 Q는 빠짐
    p = d["projects"][0]
    assert p["rules_real"] == ["a"] and p["rules_applicable"] == []  # 공개 안 된 b로 가는 연결도 빠짐
    assert p["milestones"][0]["rules"] == ["a"]
    assert d["method"] == ""  # 기록 방식도 승인 전엔 공개 안 됨
    dev = data_of(render(TEMPLATE, RULES, QUIZZES, status, QSTATUS, public_only=False, course_link="",
                         projects=projects, method="방식"))
    assert len(dev["projects"]) == 2 and dev["method"] == "방식"


def test_script_end_tag_in_content_cannot_break_out():
    html = render(TEMPLATE, RULES, QUIZZES, STATUS, QSTATUS, public_only=False, course_link="")
    assert html.count("</script>") == 1  # 템플릿 자신의 닫는 태그 하나뿐
    assert data_of(html)["rules"][1]["title"] == "</script><b>"
