"""md 텍스트를 제목·머리말·## 절로 나눈다. 코드 블록 안의 # 줄은 제목으로 보지 않는다."""


def parse(text: str) -> dict:
    title = ""
    intro: list[str] = []
    sections: list[dict] = []
    in_code = False

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if not in_code and not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        if not in_code and line.startswith("## "):
            sections.append({"heading": line[3:].strip(), "body": []})
            continue
        (sections[-1]["body"] if sections else intro).append(line)

    for s in sections:
        s["body"] = "\n".join(s["body"]).strip()
    return {"title": title, "intro": "\n".join(intro).strip(), "sections": sections}
