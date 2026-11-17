"""공용\\*.md → 규칙\\<id>.json. 순서만 부른다: 읽기 → 판단 → 검증 → 저장.
하나라도 스키마 위반이면 아무것도 쓰지 않고 문서명·이유를 출력한 뒤 종료 코드 1."""

import datetime
import json
import os
import sys
from collections import Counter
from pathlib import Path

from logic.classify import (apply_tag_overrides, find_links, find_projects, find_tags, link_project_rules,
                            section_kind)
from logic.parse_md import parse
from logic.publish_check import content_hash, decide, scan
from logic.render_html import render
from logic.validate import validate_project, validate_quiz, validate_rule

HUB = Path(__file__).resolve().parent
RULES_ROOT = HUB.parent
SOURCE_DIR = RULES_ROOT / "공용"
OUT_DIR = HUB / "규칙"
QUIZ_DIR = HUB / "퀴즈"
# 프로젝트 카드(<id>.json)와 결정 기록 방식 소개(_기록방식.md). 비공개 결정이력에서 다시 쓴 글이라 자동 승인 없음.
PROJECT_DIR = HUB / "프로젝트"
METHOD_FILE = PROJECT_DIR / "_기록방식.md"
TAG_OVERRIDE_FILE = HUB / "태그_덮어쓰기.json"
PATTERNS_FILE = HUB / "금지어.json"
APPROVALS_FILE = HUB / "승인" / "승인.json"
STATUS_FILE = HUB / "공개상태.json"
TEMPLATE_FILE = HUB / "템플릿" / "강좌_템플릿.html"
HTML_FILE = HUB / "강좌.html"
# 기존 기초 강좌(옮기지 않고 링크만). SSOT_Coding_File 기준 위치.
COURSE_V2 = RULES_ROOT.parents[1] / "Sand_Box_Coding_Study" / "강좌자료" / "강좌_v2.html"
NOT_PROJECTS = {"공용", "개발자_프로필", "범용규칙 설계도", "범용규칙_Coding_Study", HUB.name}


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def publish_status() -> dict:
    """문서별 {status, hash, hits}. 매번 원본 md에서 새로 계산한다."""
    patterns = load_json(PATTERNS_FILE, [])
    approvals = load_json(APPROVALS_FILE, {})
    sources = [(f.stem, f) for f in sorted(SOURCE_DIR.glob("*.md")) if f.name != "README.md"]
    sources += [(f"project:{f.stem}", f) for f in sorted(PROJECT_DIR.glob("*.json"))]
    if METHOD_FILE.exists():
        sources.append(("project:_기록방식", METHOD_FILE))
    result = {}
    for key, f in sources:
        text = f.read_text(encoding="utf-8")
        h = content_hash(text)
        hits = scan(text, patterns)
        result[key] = {"status": decide("doc", hits, approvals.get(key), h), "hash": h, "hits": hits, "path": str(f)}
    return result


def quiz_status(doc_status: dict) -> dict:
    """퀴즈는 공개용으로 쓴 글이라 금지어만 통과하면 자동 승인(card). 단, 규칙이 approved일 때만 공개."""
    patterns = load_json(PATTERNS_FILE, [])
    result = {}
    for f in sorted(QUIZ_DIR.glob("*.json")):
        text = f.read_text(encoding="utf-8")
        hits = scan(text, patterns)
        own = decide("card", hits, None, content_hash(text))
        rule_ok = doc_status.get(f.stem, {}).get("status") == "approved"
        result[f.stem] = {"status": own if own == "blocked" or rule_ok else "waiting_rule", "hits": hits}
    return result


def load_projects(rules: list[dict], errors: list[str]) -> list[dict]:
    """프로젝트 카드를 읽어 검사하고, 실측·적용 가능 규칙을 붙인다."""
    ids = {r["id"] for r in rules}
    out = []
    for f in sorted(PROJECT_DIR.glob("*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"프로젝트\\{f.name}: JSON 문법 오류 {e}")
            continue
        if p.get("id") != f.stem:
            errors.append(f"프로젝트\\{f.name}: 파일 이름과 id가 다름")
        errors += [f"프로젝트\\{f.name}: {e}" for e in validate_project(p, ids)]
        real, appl = link_project_rules(p, rules)
        out.append({**p, "rules_real": real, "rules_applicable": appl})
    return out


def write_html(rules: list[dict], quizzes: dict, public_only: bool, out_file: Path, course_link: str,
               projects: list[dict] | None = None) -> None:
    status = publish_status()
    method = METHOD_FILE.read_text(encoding="utf-8") if METHOD_FILE.exists() else ""
    html = render(TEMPLATE_FILE.read_text(encoding="utf-8"), rules, quizzes, status, quiz_status(status),
                  public_only=public_only, course_link=course_link, projects=projects or [], method=method)
    out_file.write_text(html, encoding="utf-8")


def report_publish() -> None:
    status = publish_status()
    quizzes = quiz_status(status)
    STATUS_FILE.write_text(json.dumps({"rules": status, "quizzes": quizzes}, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(s["status"] for s in status.values())
    labels = Counter(h["label"] for s in list(status.values()) + list(quizzes.values()) for h in s["hits"])
    print("공개 상태: " + ", ".join(f"{k} {counts.get(k, 0)}" for k in ("approved", "pending", "stale", "blocked")))
    qcounts = Counter(s["status"] for s in quizzes.values())
    print("퀴즈 공개: " + ", ".join(f"{k} {v}" for k, v in qcounts.items()) + " (waiting_rule = 규칙 승인 대기)")
    if labels:
        print("막힌 이유(줄 수): " + ", ".join(f"{k} {v}" for k, v in labels.most_common()))
    print(f"상세: {STATUS_FILE.name} / 승인: 승인.bat")


def main() -> int:
    # 공개 저장소처럼 프로젝트 폴더가 없는 곳에서는 패키지가 남긴 프로젝트.json을 쓴다.
    projects = load_json(HUB / "프로젝트.json", None) or sorted(
        p.name for p in RULES_ROOT.iterdir() if p.is_dir() and p.name not in NOT_PROJECTS)
    files = sorted(f for f in SOURCE_DIR.glob("*.md") if f.name != "README.md")
    ids = {f.stem for f in files}

    rules, errors = [], []
    for f in files:
        text = f.read_text(encoding="utf-8")
        doc = parse(text)
        rule = {
            "id": f.stem,
            "title": doc["title"],
            "source": f"공용/{f.name}",
            "intro": doc["intro"],
            "sections": [{"kind": section_kind(s["heading"]), **s} for s in doc["sections"]],
            "projects": find_projects(text, projects),
            "links": find_links(text, ids, self_id=f.stem),
            "updated": datetime.date.fromtimestamp(f.stat().st_mtime).isoformat(),
            "tags": find_tags(" ".join([doc["title"], doc["intro"], *(s["heading"] for s in doc["sections"])]),
                              text),
        }
        errors += [f"{f.name}: {e}" for e in validate_rule(rule)]
        rules.append(rule)

    # 자동 태그가 틀린 규칙은 태그_덮어쓰기.json에서 직접 정한다(적용 가능 규칙 연결의 정확도).
    errors += apply_tag_overrides(rules, load_json(TAG_OVERRIDE_FILE, {}))

    by_id = {r["id"]: r for r in rules}
    quiz_count, quizzes = 0, {}
    for q in sorted(QUIZ_DIR.glob("*.json")):
        try:
            data = json.loads(q.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"퀴즈\\{q.name}: JSON 문법 오류 {e}")
            continue
        if data.get("rule_id") != q.stem:
            errors.append(f"퀴즈\\{q.name}: 파일 이름과 rule_id가 다름")
        errors += [f"퀴즈\\{q.name}: {e}" for e in validate_quiz(data, by_id)]
        quiz_count += len(data.get("questions", []))
        quizzes[q.stem] = data

    project_cards = load_projects(rules, errors)

    if errors:
        print("스키마 위반 — 아무것도 쓰지 않음")
        print("\n".join(errors))
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    for r in rules:
        (OUT_DIR / f"{r['id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    kinds = Counter(s["kind"] for r in rules for s in r["sections"])
    orphans = sorted(p.stem for p in OUT_DIR.glob("*.json") if p.stem not in ids)
    print(f"변환 {len(rules)}개 → {OUT_DIR}")
    print(f"퀴즈 {len(list(QUIZ_DIR.glob('*.json')))}개 규칙, {quiz_count}문제 검사 통과")
    print("절 종류: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    if orphans:
        print(f"원본 md가 없는 JSON {len(orphans)}개(삭제는 직접): {', '.join(orphans)}")
    course = os.path.relpath(COURSE_V2, HUB).replace("\\", "/") if COURSE_V2.exists() else ""
    print(f"프로젝트 카드 {len(project_cards)}개 검사 통과")
    write_html(rules, quizzes, public_only=False, out_file=HTML_FILE, course_link=course, projects=project_cards)
    print(f"강좌 페이지: {HTML_FILE.name} (개발용 — 전체 규칙, 비공개 배지 표시)")
    report_publish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
