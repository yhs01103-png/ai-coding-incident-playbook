from logic.package_plan import CODE_FILES, plan, public_patterns

STATUS = {"a": {"status": "approved"}, "b": {"status": "pending"}, "c": {"status": "stale"}}
QSTATUS = {"a": {"status": "approved"}, "b": {"status": "waiting_rule"}}


def test_plan_takes_only_approved_docs_and_public_quizzes():
    files = dict(plan(STATUS, QSTATUS))
    assert "공용/a.md" in files and "공용/b.md" not in files and "공용/c.md" not in files
    assert "강좌_허브/퀴즈/a.json" in files and "강좌_허브/퀴즈/b.json" not in files
    assert files["공용/a.md"] == ("source", "a.md")


def test_plan_never_ships_internal_or_generated_files():
    dests = {d for d, _ in plan(STATUS, QSTATUS)}
    for bad in ("강좌_허브/README.md", "강좌_허브/공개상태.json", "강좌_허브/강좌.html",
                "강좌_허브/승인/스냅샷", "강좌_허브/규칙"):
        assert not any(d == bad or d.startswith(bad + "/") for d in dests), bad
    assert all(f"강좌_허브/{c}" in dests for c in CODE_FILES)


def test_plan_ships_approved_project_cards_to_project_folder():
    status = dict(STATUS, **{"project:P": {"status": "approved"}, "project:Q": {"status": "pending"},
                             "project:_기록방식": {"status": "approved"}})
    files = dict(plan(status, QSTATUS))
    assert files["강좌_허브/프로젝트/P.json"] == ("hub", "프로젝트/P.json")
    assert files["강좌_허브/프로젝트/_기록방식.md"] == ("hub", "프로젝트/_기록방식.md")
    assert "강좌_허브/프로젝트/Q.json" not in files
    assert not any(":" in d for d in files)  # project 키가 공용 md 경로로 새지 않는다


def test_public_tag_overrides_keep_only_approved_rules():
    from logic.package_plan import public_tag_overrides
    assert public_tag_overrides({"a": ["Windows"], "b": ["LLM"]}, {"a", "project:P"}) == {"a": ["Windows"]}


def test_public_patterns_replace_account_name_only():
    pats = [{"label": "계정 이름", "regex": "secretname"}, {"label": "이메일", "regex": "x@y"}]
    out = public_patterns(pats)
    assert "secretname" not in str(out)
    assert out[1] == {"label": "이메일", "regex": "x@y"}
