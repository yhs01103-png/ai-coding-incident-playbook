"""규칙·퀴즈 데이터를 HTML 템플릿의 /*__DATA__*/ 자리에 넣는다.
public_only=True면 승인된 규칙과 공개된 퀴즈만 넣는다(공개용 패키지)."""

import json


def render(template: str, rules: list[dict], quizzes: dict, status: dict, quiz_status: dict,
           public_only: bool, course_link: str, projects: list[dict] | None = None, method: str = "") -> str:
    out_rules = []
    for r in rules:
        public = status.get(r["id"], {}).get("status") == "approved"
        if public_only and not public:
            continue
        out_rules.append({**r, "public": public})
    kept = {r["id"] for r in out_rules}
    out_quizzes = {
        k: q for k, q in quizzes.items()
        if k in kept and (not public_only or quiz_status.get(k, {}).get("status") == "approved")
    }
    # 프로젝트 카드·기록 방식은 "project:<id>" 키로 승인된다. 공개 빌드에서는 공개된 규칙만 연결로 남긴다.
    def approved(key):
        return status.get(key, {}).get("status") == "approved"
    out_projects = []
    for p in projects or []:
        ok = approved(f"project:{p['id']}")
        if public_only and not ok:
            continue
        out_projects.append({
            **p, "public": ok,
            "rules_real": [r for r in p.get("rules_real", []) if r in kept],
            "rules_applicable": [r for r in p.get("rules_applicable", []) if r["id"] in kept],
            "milestones": [{**m, "rules": [r for r in m.get("rules", []) if r in kept]} for m in p.get("milestones", [])],
        })
    show_method = method if (not public_only or approved("project:_기록방식")) else ""
    data = {"rules": out_rules, "quizzes": out_quizzes, "course_link": course_link, "public_only": public_only,
            "projects": out_projects, "method": show_method}
    # 본문에 "</script>"가 있어도 스크립트 블록을 빠져나가지 못하게 "</"를 이스케이프한다.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace("/*__DATA__*/", payload)
