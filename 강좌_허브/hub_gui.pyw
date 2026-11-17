"""강좌 허브 화면 — 빌드·변환 결과·공개 상태·바뀐 줄·승인을 한 창에서 본다.
화면만 담당한다. 판정은 logic\\publish_check.py, 변환은 build.py, 승인 기록은 approve.approve_ids가 한다."""

import contextlib
import datetime
import difflib
import io
import json
import tkinter as tk
from collections import Counter
from tkinter import messagebox, ttk

import build
from pathlib import Path

from approve import approve_ids, snapshot_path

FONT = "Malgun Gothic"
MONO = "Consolas"
C = {
    "bg": "#f5f6f8", "panel": "#ffffff", "ink": "#1d2433", "sub": "#6b7385", "line": "#e3e6ec",
    "head": "#1f2433", "head_ink": "#ffffff", "accent": "#3b6ef5",
    "approved": "#1e8e4e", "pending": "#b7791f", "stale": "#2f6fd6", "blocked": "#c53030",
    "add_bg": "#e3f5e9", "del_bg": "#fde8e8", "hit_bg": "#fff3c4", "code_bg": "#f1f3f6",
}
STATUS_KO = {"approved": "공개", "pending": "승인 대기", "stale": "바뀜·재승인", "blocked": "금지어 막힘"}


def load_rows() -> list[dict]:
    status = build.publish_status()
    approvals = build.load_json(build.APPROVALS_FILE, {})
    quizzes = build.quiz_status(status)
    rows = []
    for doc_id, s in status.items():
        src = Path(s["path"])
        text = src.read_text(encoding="utf-8")
        if doc_id.startswith("project:"):  # 프로젝트 카드·기록 방식 — 화면에서 구분되게 이름 앞에 표시
            card = json.loads(text) if src.suffix == ".json" else {}
            rule = {"title": "[프로젝트] " + card.get("name", src.stem)}
        else:
            rule_file = build.OUT_DIR / f"{doc_id}.json"
            rule = json.loads(rule_file.read_text(encoding="utf-8")) if rule_file.exists() else {}
        snap = snapshot_path(doc_id)
        old = snap.read_text(encoding="utf-8") if snap.exists() else None
        appr = approvals.get(doc_id)
        if appr is None:
            change, plus, minus = "미승인", 0, 0
        elif appr.get("hash") == s["hash"]:
            change, plus, minus = "안 바뀜", 0, 0
        else:
            d = list(difflib.ndiff((old or "").splitlines(), text.splitlines()))
            plus, minus = sum(x.startswith("+ ") for x in d), sum(x.startswith("- ") for x in d)
            change = f"바뀜 +{plus} −{minus}"
        qfile = build.QUIZ_DIR / f"{doc_id}.json"
        qcount = len(json.loads(qfile.read_text(encoding="utf-8")).get("questions", [])) if qfile.exists() else 0
        rows.append({
            "id": doc_id, "title": rule.get("title", doc_id), "status": s["status"], "hits": s["hits"],
            "change": change, "updated": datetime.date.fromtimestamp(src.stat().st_mtime).isoformat(),
            "approved_at": (appr or {}).get("approved_at", "—"), "sections": len(rule.get("sections", [])),
            "kinds": Counter(x["kind"] for x in rule.get("sections", [])), "projects": rule.get("projects", []),
            "quiz": qcount, "quiz_status": quizzes.get(doc_id, {}).get("status"), "text": text, "old": old,
        })
    return rows


class HubApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.rows: list[dict] = []
        self.checked: set[str] = set()
        self.last_build = "—"
        root.title("강좌 허브")
        self.k = max(1.0, root.winfo_fpixels("1i") / 96)  # 화면 배율(125%·150% 등)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(int(1440 * self.k), int(sw * 0.94))}x{min(int(880 * self.k), int(sh * 0.9))}")
        root.minsize(int(1100 * self.k), int(640 * self.k))
        root.configure(bg=C["bg"])
        self._style()
        self._header()
        self._stats()
        self._log()
        self._body()
        self.reload()

    # ---------- 모양 ----------
    def _style(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", font=(FONT, 10), background=C["bg"], foreground=C["ink"])
        st.configure("Treeview", rowheight=int(30 * self.k), background=C["panel"], fieldbackground=C["panel"], bordercolor=C["line"])
        st.configure("Treeview.Heading", font=(FONT, 10, "bold"), background=C["bg"], foreground=C["sub"], relief="flat")
        st.map("Treeview", background=[("selected", "#e8eefe")], foreground=[("selected", C["ink"])])
        st.configure("Accent.TButton", font=(FONT, 10, "bold"), background=C["accent"], foreground="#fff", padding=(14, 7), borderwidth=0)
        st.map("Accent.TButton", background=[("active", "#2f5ad0")])
        st.configure("Ghost.TButton", font=(FONT, 10), background="#2c3245", foreground="#fff", padding=(12, 7), borderwidth=0)
        st.map("Ghost.TButton", background=[("active", "#3a4158")])
        st.configure("TCombobox", padding=4)

    def _header(self):
        h = tk.Frame(self.root, bg=C["head"], padx=20, pady=14)
        h.pack(fill="x")
        left = tk.Frame(h, bg=C["head"])
        left.pack(side="left")
        tk.Label(left, text="강좌 허브", font=(FONT, 16, "bold"), fg=C["head_ink"], bg=C["head"]).pack(anchor="w")
        tk.Label(left, text=f"원본  {build.SOURCE_DIR}", font=(FONT, 9), fg="#9aa3b8", bg=C["head"]).pack(anchor="w")
        right = tk.Frame(h, bg=C["head"])
        right.pack(side="right")
        ttk.Button(right, text="새로고침", style="Ghost.TButton", command=self.reload).pack(side="left", padx=4)
        ttk.Button(right, text="승인 대상 전체 선택", style="Ghost.TButton", command=self.check_all).pack(side="left", padx=4)
        ttk.Button(right, text="선택 승인", style="Ghost.TButton", command=self.approve).pack(side="left", padx=4)
        ttk.Button(right, text="▶ 빌드", style="Accent.TButton", command=self.run_build).pack(side="left", padx=(8, 0))

    def _stats(self):
        self.stat_frame = tk.Frame(self.root, bg=C["bg"], padx=16, pady=12)
        self.stat_frame.pack(fill="x")

    def _card(self, label, value, color=None):
        f = tk.Frame(self.stat_frame, bg=C["panel"], padx=16, pady=10, highlightthickness=1, highlightbackground=C["line"])
        f.pack(side="left", padx=4, fill="y")
        tk.Label(f, text=label, font=(FONT, 9), fg=C["sub"], bg=C["panel"]).pack(anchor="w")
        tk.Label(f, text=value, font=(FONT, 15, "bold"), fg=color or C["ink"], bg=C["panel"]).pack(anchor="w")

    def _body(self):
        pane = ttk.PanedWindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        left = tk.Frame(pane, bg=C["bg"])
        bar = tk.Frame(left, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 6))
        tk.Label(bar, text="검색", font=(FONT, 9), fg=C["sub"], bg=C["bg"]).pack(side="left", padx=(0, 6))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill_table())
        e = ttk.Entry(bar, textvariable=self.q, font=(FONT, 10))
        e.pack(side="left", fill="x", expand=True)
        self.filter = tk.StringVar(value="전체")
        cb = ttk.Combobox(bar, textvariable=self.filter, state="readonly", width=14,
                          values=["전체", "승인 대상", *STATUS_KO.values()])
        cb.pack(side="left", padx=(6, 0))
        cb.bind("<<ComboboxSelected>>", lambda _: self.fill_table())

        cols = ("chk", "doc", "status", "change", "updated", "approved", "sections", "quiz", "hits")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for col, text, w, anchor in [
            ("chk", "✓", 30, "center"), ("doc", "문서", 220, "w"), ("status", "공개 상태", 82, "center"),
            ("change", "승인 뒤 변경", 90, "center"), ("updated", "수정일", 82, "center"),
            ("approved", "승인일", 82, "center"), ("sections", "절", 34, "center"),
            ("quiz", "퀴즈", 40, "center"), ("hits", "금지어", 50, "center"),
        ]:
            w = int(w * self.k)
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, minwidth=w if col != "doc" else int(160 * self.k), anchor=anchor,
                             stretch=(col == "doc"))
        for key in STATUS_KO:
            self.tree.tag_configure(key, foreground=C[key])
        ysb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.show_detail())
        self.tree.bind("<Button-1>", self.on_click)
        pane.add(left, weight=3)

        right = tk.Frame(pane, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
        top = tk.Frame(right, bg=C["panel"], padx=16, pady=12)
        top.pack(fill="x")
        wrap = int(560 * self.k)
        self.d_title = tk.Label(top, text="문서를 고르세요", font=(FONT, 13, "bold"), fg=C["ink"], bg=C["panel"],
                                anchor="w", justify="left", wraplength=wrap)
        self.d_title.pack(fill="x")
        self.d_meta = tk.Label(top, text="", font=(FONT, 9), fg=C["sub"], bg=C["panel"], anchor="w", justify="left",
                               wraplength=wrap)
        self.d_meta.pack(fill="x", pady=(4, 0))
        self.d_legend = tk.Label(top, text="", font=(FONT, 9), fg=C["sub"], bg=C["panel"], anchor="w")
        self.d_legend.pack(fill="x", pady=(4, 0))
        self.text = tk.Text(right, wrap="word", font=(FONT, 10), bg=C["panel"], fg=C["ink"], relief="flat",
                            padx=16, pady=8, spacing1=2, spacing3=2, borderwidth=0)
        tsb = ttk.Scrollbar(right, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("h1", font=(FONT, 14, "bold"), spacing1=8)
        self.text.tag_configure("h2", font=(FONT, 12, "bold"), foreground=C["accent"], spacing1=10)
        self.text.tag_configure("code", font=(MONO, 9), background=C["code_bg"])
        self.text.tag_configure("add", background=C["add_bg"])
        self.text.tag_configure("del", background=C["del_bg"], overstrike=True, foreground="#8a4b4b")
        self.text.tag_configure("hit", background=C["hit_bg"])
        pane.add(right, weight=2)

    def _log(self):
        f = tk.Frame(self.root, bg=C["bg"], padx=20)
        f.pack(side="bottom", fill="x", pady=(0, 14))
        tk.Label(f, text="빌드 결과", font=(FONT, 9, "bold"), fg=C["sub"], bg=C["bg"]).pack(anchor="w")
        self.log = tk.Text(f, height=6, font=(MONO, 9), bg="#141821", fg="#cfd6e4", relief="flat", padx=10, pady=6)
        self.log.pack(fill="x")
        self.log.insert("end", "▶ 빌드를 누르면 여기에 변환 결과가 나옵니다.\n")
        self.log.configure(state="disabled")

    # ---------- 데이터 ----------
    def reload(self):
        self.rows = load_rows()
        self.checked &= {r["id"] for r in self.rows if r["status"] in ("pending", "stale")}
        self.fill_stats()
        self.fill_table()

    def fill_stats(self):
        for w in self.stat_frame.winfo_children():
            w.destroy()
        n = Counter(r["status"] for r in self.rows)
        kinds = sum((r["kinds"] for r in self.rows), Counter())
        self._card("규칙 문서", str(len(self.rows)))
        self._card("공개", str(n["approved"]), C["approved"])
        self._card("승인 대기", str(n["pending"]), C["pending"])
        self._card("바뀜·재승인", str(n["stale"]), C["stale"])
        self._card("금지어 막힘", str(n["blocked"]), C["blocked"])
        self._card("퀴즈", f"{sum(r['quiz'] for r in self.rows)}문제 / {sum(1 for r in self.rows if r['quiz'])}규칙")
        self._card("절 분류", f"other {kinds['other']} / 전체 {sum(kinds.values())}")
        self._card("마지막 빌드", self.last_build)

    def visible_rows(self):
        q, flt = self.q.get().strip(), self.filter.get()
        for r in self.rows:
            if q and q not in r["id"] and q not in r["title"]:
                continue
            if flt == "승인 대상" and r["status"] not in ("pending", "stale"):
                continue
            if flt in STATUS_KO.values() and STATUS_KO[r["status"]] != flt:
                continue
            yield r

    def fill_table(self):
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        order = {"stale": 0, "blocked": 1, "pending": 2, "approved": 3}
        for r in sorted(self.visible_rows(), key=lambda r: (order[r["status"]], r["id"])):
            selectable = r["status"] in ("pending", "stale")
            chk = ("☑" if r["id"] in self.checked else "☐") if selectable else ""
            self.tree.insert("", "end", iid=r["id"], tags=(r["status"],), values=(
                chk, r["id"], STATUS_KO[r["status"]], r["change"], r["updated"], r["approved_at"],
                r["sections"], r["quiz"] or "", len(r["hits"]) or ""))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])

    def on_click(self, event):
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        row = next((r for r in self.rows if r["id"] == iid), None)
        if not row or row["status"] not in ("pending", "stale"):
            return
        self.checked ^= {iid}
        self.tree.set(iid, "chk", "☑" if iid in self.checked else "☐")

    def check_all(self):
        self.checked = {r["id"] for r in self.visible_rows() if r["status"] in ("pending", "stale")}
        self.fill_table()

    def show_detail(self):
        sel = self.tree.selection()
        row = next((r for r in self.rows if sel and r["id"] == sel[0]), None)
        if not row:
            return
        self.d_title.configure(text=row["title"])
        meta = [f"공개 상태  {STATUS_KO[row['status']]}", f"승인 뒤 변경  {row['change']}", f"수정일  {row['updated']}",
                f"승인일  {row['approved_at']}", f"절 {row['sections']}개"]
        if row["projects"]:
            meta.append("프로젝트  " + ", ".join(row["projects"]))
        if row["quiz"]:
            meta.append(f"퀴즈 {row['quiz']}문제 ({'공개' if row['quiz_status'] == 'approved' else '규칙 승인 대기'})")
        self.d_meta.configure(text="   ·   ".join(meta), fg=C["sub"])
        hit_lines = {h["line"] for h in row["hits"]}
        if row["hits"]:
            self.d_legend.configure(text="금지어: " + ", ".join(f"{h['line']}줄 {h['label']} '{h['match']}'" for h in row["hits"]),
                                    fg=C["blocked"])
        elif row["old"] is not None and row["change"].startswith("바뀜"):
            self.d_legend.configure(text="초록 = 승인 뒤 추가된 줄   빨강 취소선 = 승인 뒤 지워진 줄", fg=C["stale"])
        else:
            self.d_legend.configure(text="")

        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if row["old"] is not None and row["change"].startswith("바뀜"):
            lines = [(d[:1], d[2:]) for d in difflib.ndiff(row["old"].splitlines(), row["text"].splitlines()) if d[:1] != "?"]
        else:
            lines = [(" ", ln) for ln in row["text"].splitlines()]
        in_code, cur_no = False, 0
        for mark, ln in lines:
            if mark != "-":
                cur_no += 1
            if mark == " " and ln.startswith("# ") and ln[2:].strip() == row["title"]:
                continue  # 제목은 위에 이미 크게 나온다
            if ln.lstrip().startswith("```"):
                in_code = not in_code
            tags = []
            if in_code or ln.lstrip().startswith("```"):
                tags.append("code")
            elif ln.startswith("# "):
                tags.append("h1")
            elif ln.startswith("## "):
                tags.append("h2")
            if mark == "+":
                tags.append("add")
            elif mark == "-":
                tags.append("del")
            if mark != "-" and cur_no in hit_lines:
                tags.append("hit")
            t.insert("end", ln + "\n", tuple(tags))
        t.configure(state="disabled")
        t.yview_moveto(0)

    # ---------- 행동 ----------
    def run_build(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = build.main()
        self.last_build = datetime.datetime.now().strftime("%H:%M:%S") + (" 실패" if code else "")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", buf.getvalue() or "(출력 없음)")
        self.log.configure(state="disabled")
        self.reload()
        if code:
            messagebox.showerror("빌드 실패", "스키마 위반이 있어 아무 파일도 쓰지 않았습니다. 아래 빌드 결과를 확인하세요.")

    def approve(self):
        ids = sorted(self.checked)
        if not ids:
            messagebox.showinfo("선택 승인", "체크한 문서가 없습니다. ✓ 칸을 눌러 고르세요.")
            return
        preview = "\n".join(ids[:12]) + (f"\n… 외 {len(ids) - 12}개" if len(ids) > 12 else "")
        if not messagebox.askyesno("선택 승인", f"{len(ids)}개 문서를 지금 내용 그대로 공개 승인합니다.\n\n{preview}"):
            return
        status = build.publish_status()
        done = approve_ids(ids, status)
        self.checked.clear()
        self.reload()
        messagebox.showinfo("선택 승인", f"{len(done)}개 승인했습니다.")


if __name__ == "__main__":
    try:  # 고해상도 화면에서 글자가 흐려지지 않게
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    HubApp(root)
    root.mainloop()
