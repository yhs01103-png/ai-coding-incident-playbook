"""공개 여부 판정. 기본은 비공개이고, 금지어 검사 통과 + 현재 내용과 같은 해시의 승인이 있을 때만 공개.
공개용으로 처음부터 쓴 사례 카드(kind="card")만 검사 통과 시 자동 승인."""

import difflib
import hashlib
import re


def scan(text: str, patterns: list[dict]) -> list[dict]:
    # 본문 전체에 한 번씩 먼저 걸러 본다(대부분 문서는 여기서 끝). 걸린 금지어만 줄 단위로 위치를 찾는다.
    compiled = [(p["label"], re.compile(p["regex"])) for p in patterns
                if re.search(p["regex"], text, re.MULTILINE)]
    if not compiled:
        return []
    hits = []
    for no, line in enumerate(text.splitlines(), start=1):
        for label, rx in compiled:
            m = rx.search(line)
            if m:
                hits.append({"line": no, "label": label, "match": m.group(0)})
    return hits


def content_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def decide(kind: str, hits: list, approval: dict | None, current_hash: str) -> str:
    """blocked(금지어) / pending(승인 대기) / stale(승인 뒤 바뀜) / approved(공개)."""
    if hits:
        return "blocked"
    if kind == "card":
        return "approved"
    if approval is None:
        return "pending"
    return "approved" if approval.get("hash") == current_hash else "stale"


def rule_approval_text(md_text: str, short: str) -> str:
    """규칙 승인 대상 = 원본 md + 짧은 제목 한 줄. 짧은 제목만 바뀌어도 재승인(바뀐 줄은 이 한 줄)."""
    return md_text.rstrip("\n") + f"\n\n짧은 제목: {short}"


def quiz_public(own: str, rule: str) -> str:
    """퀴즈는 자기 승인과 규칙 승인이 둘 다 있어야 공개."""
    return "waiting_rule" if own == "approved" and rule != "approved" else own


def changed_lines(old: str, new: str) -> list[str]:
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
    return [d for d in diff if d[:1] in "+-" and not d.startswith(("+++", "---"))]
