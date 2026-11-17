"""절 종류 판정, 관련 프로젝트·문서 링크 추출. 같은 입력이면 항상 같은 결과."""

import re

# 위에서부터 먼저 맞는 것을 쓴다. "실측 함정"은 case, "점검 grep"은 checklist.
KIND_TABLE = [
    ("related", ("함께 볼", "관련 문서")),
    ("case", ("실측", "사례", "적용")),
    ("checklist", ("체크리스트", "점검", "시험", "검증", "감사", "확인")),
    ("context", ("언제", "상황", "범위")),
    ("problem", ("문제", "증상", "함정", "원인", "왜 ", "주의", "하지 말", "놓치", "한계")),
    ("solution", ("해법", "해결", "원칙", "고치는 법", "완화", "지침", "패턴", "절차", "순서", "구조", "설계", "규칙")),
]
NUMBERED = re.compile(r"^\d+(-\d+)?\.\s")  # "3. …" 번호 항목은 규칙 본문
KINDS = {k for k, _ in KIND_TABLE} | {"other"}


def section_kind(heading: str) -> str:
    for kind, words in KIND_TABLE:
        if any(w in heading for w in words):
            return kind
    return "solution" if NUMBERED.match(heading) else "other"


def find_projects(text: str, project_names: list[str]) -> list[str]:
    # 프로젝트 이름을 하나의 정규식으로 묶어 본문을 한 번만 훑는다. 긴 이름 먼저(접두사 겹침 방지).
    if not project_names:
        return []
    names = "|".join(re.escape(p) for p in sorted(project_names, key=len, reverse=True))
    return sorted(set(re.findall(rf"(?<![\w])({names})(?![\w])", text)))


MD_REF = re.compile(r"([^\s`'\"()\[\]<>/\\|,*]+)\.md")


def find_links(text: str, known_ids: set[str], self_id: str) -> list[str]:
    # 본문에서 "○○.md"를 한 번만 뽑아 문서 목록과 대조한다(문서마다 전체 목록을 훑으면 n×n이 된다).
    return sorted(({m for m in MD_REF.findall(text)} & known_ids) - {self_id})
