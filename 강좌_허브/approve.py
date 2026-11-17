"""묶음 승인. 금지어 검사를 통과했지만 승인이 없거나(pending) 승인 뒤 바뀐(stale) 문서를 보여 주고,
사용자가 고른 것만 현재 내용의 해시로 승인한다. 승인한 내용은 스냅샷으로 남겨 다음에 바뀐 줄만 보여 준다.
사용법: python approve.py         (목록 → 번호 입력)
        python approve.py --list  (목록만)"""

import datetime
import json
import sys

from build import APPROVALS_FILE, SOURCE_DIR, load_json, publish_status
from logic.publish_check import changed_lines

SNAP_DIR = APPROVALS_FILE.parent / "스냅샷"


def approve_ids(doc_ids, status, approvals_file=APPROVALS_FILE, snap_dir=SNAP_DIR, source_dir=SOURCE_DIR,
                today=None) -> list[str]:
    """pending/stale 문서만 현재 해시로 승인하고 스냅샷을 남긴다. 승인한 id 목록을 돌려준다."""
    approvals = load_json(approvals_file, {})
    today = today or datetime.date.today().isoformat()
    snap_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for doc_id in doc_ids:
        s = status.get(doc_id)
        if not s or s["status"] not in ("pending", "stale"):
            continue
        approvals[doc_id] = {"hash": s["hash"], "approved_at": today, "kind": "doc"}
        (snap_dir / f"{doc_id}.md").write_text((source_dir / f"{doc_id}.md").read_text(encoding="utf-8"), encoding="utf-8")
        done.append(doc_id)
    approvals_file.write_text(json.dumps(approvals, ensure_ascii=False, indent=2), encoding="utf-8")
    return done


def main() -> int:
    status = publish_status()
    todo = [(i, s) for i, s in status.items() if s["status"] in ("pending", "stale")]
    blocked = sum(1 for s in status.values() if s["status"] == "blocked")
    print(f"승인 대상 {len(todo)}개 (금지어로 막힌 {blocked}개는 원본을 고친 뒤 다시 빌드)")
    for n, (doc_id, s) in enumerate(todo, start=1):
        print(f"\n[{n}] {doc_id} ({'바뀜' if s['status'] == 'stale' else '새 문서'})  공용\\{doc_id}.md")
        snap = SNAP_DIR / f"{doc_id}.md"
        if s["status"] == "stale" and snap.exists():
            diff = changed_lines(snap.read_text(encoding="utf-8"), (SOURCE_DIR / f"{doc_id}.md").read_text(encoding="utf-8"))
            print("\n".join("    " + d for d in diff[:30]) + ("\n    …" if len(diff) > 30 else ""))

    if "--list" in sys.argv or not todo:
        return 0
    answer = input("\n승인할 번호(예: 1,3,5) / all / 엔터=취소: ").strip().lower()
    if not answer:
        print("취소")
        return 0
    picks = range(1, len(todo) + 1) if answer == "all" else [int(x) for x in answer.split(",") if x.strip().isdigit()]

    ids = [todo[n - 1][0] for n in picks if 1 <= n <= len(todo)]
    for doc_id in approve_ids(ids, status):
        print(f"승인: {doc_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
