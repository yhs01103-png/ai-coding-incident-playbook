import json

from approve import approve_ids


def test_approve_writes_hash_and_snapshot_only_for_pending_or_stale(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("A 본문", encoding="utf-8")
    (src / "b.md").write_text("B 본문", encoding="utf-8")
    status = {
        "a": {"status": "pending", "hash": "ha"},
        "b": {"status": "blocked", "hash": "hb"},
    }
    approvals_file = tmp_path / "승인" / "승인.json"
    snap = tmp_path / "승인" / "스냅샷"

    done = approve_ids(["a", "b", "없음"], status, approvals_file, snap, src, today="2026-11-17")

    assert done == ["a"]
    saved = json.loads(approvals_file.read_text(encoding="utf-8"))
    assert saved == {"a": {"hash": "ha", "approved_at": "2026-11-17", "kind": "doc"}}
    assert (snap / "a.md").read_text(encoding="utf-8") == "A 본문"
    assert not (snap / "b.md").exists()
