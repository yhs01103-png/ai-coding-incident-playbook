"""허브 화면에서 고른 항목(과 그 안의 일부)을 JSON으로 내보낸다 — AI·검색에 상의할 때 붙여 넣는 용도.
판정·승인과 무관한 읽기 전용 변환. 비공개 원문이 들어갈 수 있으므로 금지어 위치를 warnings로 같이 싣는다."""

QTYPE = {"choice": "보기", "spot": "틀린 줄", "scenario": "서술"}


def parts_of(kind: str, data: dict) -> list[tuple[str, str]]:
    """(키, 화면 표시) 목록. 키는 export_item의 selected에 그대로 쓴다."""
    if kind == "rule":
        return [("intro", "머리말")] + [(f"s{i}", f"[{s['kind']}] {s['heading']}") for i, s in enumerate(data.get("sections", []))]
    if kind == "quiz":
        return [(f"q{i}", f"Q{i + 1} {QTYPE.get(q.get('type'), '?')} · {q.get('situation', '')[:40]}")
                for i, q in enumerate(data.get("questions", []))]
    if kind == "project" and "milestones" in data:
        return [("summary", "요약·설계 포인트·확인 항목")] + [
            (f"m{i}", f"{m.get('ref', '')} {m.get('title', '')}") for i, m in enumerate(data["milestones"])]
    return [("all", "전체")]


def _part(kind: str, key: str, data: dict) -> dict:
    if kind == "rule":
        if key == "intro":
            return {"part": "intro", "body": data.get("intro", "")}
        s = data["sections"][int(key[1:])]
        return {"part": "section", "kind": s["kind"], "heading": s["heading"], "body": s["body"]}
    if kind == "quiz":
        return data["questions"][int(key[1:])]
    if kind == "project" and key == "summary":
        return {"part": "summary", **{k: data.get(k) for k in ("summary", "design_points", "checks", "stack")}}
    if kind == "project" and key.startswith("m"):
        return {"part": "milestone", **data["milestones"][int(key[1:])]}
    return {"part": "all", **data}


def export_item(kind: str, key: str, data: dict, selected: list[str], status: str, hits: list[dict]) -> dict:
    keys = [k for k, _ in parts_of(kind, data)]
    chosen = [k for k in keys if k in selected] or keys  # 아무것도 안 고르면 전체
    head = {"kind": kind, "id": key, "status": status}
    if kind == "rule":
        head.update(title=data.get("title"), short=data.get("short"), tags=data.get("tags", []),
                    projects=data.get("projects", []))
    elif kind == "project":
        head.update(name=data.get("name"))
    elif kind == "term":
        head.update(term=data.get("term"))
    return {**head, "parts": [_part(kind, k, data) for k in chosen],
            "warnings": [f"{h['line']}줄 {h['label']}" for h in hits]}
