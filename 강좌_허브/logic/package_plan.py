"""공개 패키지에 무엇을 담을지 정한다(화이트리스트). 여기 없는 파일은 절대 담기지 않는다.
허브 README(내부 경로), 승인 스냅샷, 생성물(규칙/, 강좌.html, 공개상태.json), 패키지 스크립트 자신은 제외."""

CODE_FILES = [
    "build.py", "approve.py", "hub_gui.pyw", "test_approve.py",
    "빌드.bat", "승인.bat", "허브.bat",
    "logic/__init__.py", "logic/parse_md.py", "logic/classify.py", "logic/validate.py",
    "logic/publish_check.py", "logic/render_html.py", "logic/package_plan.py",
    "logic/test_logic.py", "logic/test_validate_quiz.py", "logic/test_publish_check.py",
    "logic/test_render_html.py", "logic/test_package_plan.py",
    "템플릿/강좌_템플릿.html",
]


def plan(status: dict, quiz_status: dict) -> list[tuple[str, tuple[str, str]]]:
    """(저장소 안 경로, (출처 종류, 출처 상대경로)). 출처 종류: source=공용 md, hub=허브 파일."""
    out = [(f"공용/{doc_id}.md", ("source", f"{doc_id}.md"))
           for doc_id, s in sorted(status.items()) if s["status"] == "approved"]
    out += [(f"강좌_허브/퀴즈/{qid}.json", ("hub", f"퀴즈/{qid}.json"))
            for qid, s in sorted(quiz_status.items()) if s["status"] == "approved"]
    out += [(f"강좌_허브/{c}", ("hub", c)) for c in CODE_FILES]
    return out


def public_patterns(patterns: list[dict]) -> list[dict]:
    """공개본 금지어 목록: 계정 이름 줄은 자리표시로 바꾼다(목록 자체가 계정 이름을 드러내지 않게)."""
    return [{**p, "regex": "YOUR_ACCOUNT_NAME"} if p["label"] == "계정 이름" else p for p in patterns]
