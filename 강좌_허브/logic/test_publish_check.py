from logic.publish_check import content_hash, decide, scan, changed_lines

PATTERNS = [
    {"label": "내부 경로", "regex": r"[A-Za-z]:\\Users\\"},
    {"label": "의뢰 관련", "regex": "크몽|의뢰인"},
]


def test_scan_reports_line_and_label_and_skips_clean_text():
    text = "첫 줄\n경로는 C:\\Users\\me\\x\n크몽 의뢰인 이야기"
    hits = scan(text, PATTERNS)
    assert [(h["line"], h["label"]) for h in hits] == [(2, "내부 경로"), (3, "의뢰 관련")]
    assert scan("깨끗한 글", PATTERNS) == []


def test_hash_ignores_line_ending_only():
    assert content_hash("a\r\nb") == content_hash("a\nb")
    assert content_hash("a\nb") != content_hash("a\nc")


def test_decide_default_is_private():
    h = content_hash("본문")
    # 금지어가 걸리면 승인 기록이 있어도 막힌다
    assert decide("doc", hits=[{"line": 1}], approval={"hash": h}, current_hash=h) == "blocked"
    # 검사 통과 + 승인 없음 → 승인 대기(공개 아님)
    assert decide("doc", hits=[], approval=None, current_hash=h) == "pending"
    # 승인 해시와 같음 → 공개
    assert decide("doc", hits=[], approval={"hash": h}, current_hash=h) == "approved"
    # 승인 뒤 내용이 바뀜 → 다시 비공개
    assert decide("doc", hits=[], approval={"hash": "old"}, current_hash=h) == "stale"


def test_decide_card_is_auto_approved_only_when_clean():
    h = content_hash("카드")
    assert decide("card", hits=[], approval=None, current_hash=h) == "approved"
    assert decide("card", hits=[{"line": 1}], approval=None, current_hash=h) == "blocked"


def test_real_forbidden_list_blocks_real_risks_but_not_general_advice():
    import json
    from pathlib import Path
    patterns = json.loads((Path(__file__).parent.parent / "금지어.json").read_text(encoding="utf-8"))
    must_block = ["C:\\Users\\kim\\proj", "OneDrive\\Desktop\\x", "API_KEY=abcd1234efgh5678",
                  "key: AIzaSyA1234567890abcdefghijk", "메일 a.b@example.com", "크몽 의뢰"]
    must_pass = ["`C:\\Users\\<사용자이름>\\...` 같은", "OneDrive 같은 동기화 폴더", "개발 DB는 동기화 폴더(OneDrive) 밖",
                 'JAVA_HOME="C:/Program Files/Android/Android Studio/jbr"', "PATH=/usr/local/bin:/usr/bin"]
    for t in must_block:
        assert scan(t, patterns), f"막아야 함: {t}"
    for t in must_pass:
        assert not scan(t, patterns), f"통과해야 함: {t}"


def test_changed_lines_shows_only_diff():
    out = changed_lines("a\nb\nc", "a\nB\nc")
    assert "-b" in out and "+B" in out
    assert not any(line in ("-a", "+a", "-c", "+c") for line in out)
