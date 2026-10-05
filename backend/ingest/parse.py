"""Parse Act PDFs into one record per section.

Gazette PDFs interleave body text with margin notes (dropped by x-position), running headers, a Hindi
masthead and Act cross-references ("45 of 1860."). Section boundaries are found
by looking for the *next expected* section number at the start of a line, which
also skips footnotes ("1. Subs. by Act 24 of 2019 ...") and numbered lists.
"""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

from ingest.acts import ACTS, Act
from ingest.schedules import SCHEDULES

DATA = Path(__file__).resolve().parent.parent / "data"

# Text after which no more sections exist (schedules / signature block).
END_MARKERS = {
    "dpdp": re.compile(r"^Breach of provisions of\s+this Act"),
    "rti": re.compile(r"^THE FIRST SCHEDULE"),
    "cpa": re.compile(r"^————"),
}

BOILERPLATE = [
    re.compile(p)
    for p in (
        r"THE GAZETTE OF INDIA EXTRAORDINARY",
        r"^Internal$",
        r"^\d{1,3}$",  # page numbers
        r"^\d+ of \d{4}\.$",  # margin cross-references to other Acts
        r"^Sl\. No\.$",
    )
]
MASTHEAD_START = re.compile(r"(EXTRAORDINARY|MINISTRY OF LA ?W|REGISTERED NO|vlk/kkj)")
# Gazette body text spans x≈95–470pt on an A4 page; margin notes sit outside it.
MARGIN_LEFT, MARGIN_RIGHT = 90, 470
RTI_FOOTNOTE = re.compile(r"^\d+\.\s*(Subs|Ins|Omitted|Added|Rep|The words)\b")
CHAPTER = re.compile(r"^CHAPTER\s+([IVXL]+[A-Z]?)\s*$")

# Common OCR word errors in the RTI scan. Clause labels like "(/)" are left
# alone: the same glyph is "(1)" in one place and "(f)" in another.
OCR_FIXES = {
    "e-rnails": "e-mails", "Chainnan": "Chairman", "Comrnissioner": "Commissioner",
    "necessaiy": "necessary", "oftice": "office", "w.e.fl": "w.e.f.",
}


@dataclass
class Section:
    id: str
    act_id: str
    act_name: str
    act_short: str
    section: str
    title: str
    chapter: str
    page: int
    source_url: str
    text: str


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _page_lines(act: Act) -> list[tuple[int, str]]:
    reader = PdfReader(DATA / "raw" / act.pdf)
    out: list[tuple[int, str]] = []
    for pno, page in enumerate(reader.pages, start=1):
        margin: list[str] = []

        def visit(text, cm, tm, _font, _size):
            x = tm[4] * cm[0] + cm[4]
            if text.strip() and (x < MARGIN_LEFT or x > MARGIN_RIGHT):
                margin.append(text.strip())

        lines = [l.strip() for l in (page.extract_text(visitor_text=visit) or "").split("\n")]
        if act.id != "rti":  # gazette prints: drop margin notes by position
            lines = [l for l in lines if l not in margin]
        # Drop the gazette masthead on page 1 and footnotes at RTI page bottoms.
        if act.id != "rti" and pno == 1:
            enacted = next((i for i, l in enumerate(lines) if l.startswith("BE it enacted")), 0)
            cut = next((i for i, l in enumerate(lines) if i > enacted and MASTHEAD_START.search(l)), None)
            lines = lines[:cut]
        if act.id == "rti":
            cut = next((i for i, l in enumerate(lines) if RTI_FOOTNOTE.match(l)), None)
            lines = lines[:cut]
        out.extend((pno, l) for l in lines if l and not any(p.search(l) for p in BOILERPLATE))
    return out


def _join(lines: list[str]) -> str:
    """Re-flow wrapped lines into paragraphs, one per clause/proviso."""
    paras: list[str] = []
    for l in lines:
        new_para = re.match(r"^(\(\s*[0-9a-zA-Z]+\s*\)|Provided|Explanation|Illustration)", l)
        if paras and not new_para:
            sep = "" if paras[-1].endswith("-") else " "
            paras[-1] += sep + l
        else:
            paras.append(l)
    text = "\n".join(re.sub(r"\s{2,}", " ", p) for p in paras)
    return re.sub(r"\(\s+(\w+)\s*\)", r"(\1)", text)


def parse_act(act: Act) -> list[Section]:
    lines = _page_lines(act)
    start = next(i for i, (_, l) in enumerate(lines) if l.startswith("BE it enacted"))

    sections: list[Section] = []
    chapter, pending_chapter = "", None
    cur: dict | None = None
    expected = 1

    def close():
        if cur:
            text = _join(cur["lines"])
            if act.id == "rti":
                for bad, good in OCR_FIXES.items():
                    text = text.replace(bad, good)
                # Amendment markers from the consolidated print: '[ ... ] and 2[ ... ]
                text = re.sub(r"(?:\d|')\[", "", text).replace("]", "")
            sections.append(
                Section(
                    id=f"{act.id}-{cur['num']}",
                    act_id=act.id,
                    act_name=act.name,
                    act_short=act.short,
                    section=cur["num"],
                    title=cur["title"],
                    chapter=cur["chapter"],
                    page=cur["page"],
                    source_url=act.source_url,
                    text=text,
                )
            )

    for pno, line in lines[start + 1 :]:
        if END_MARKERS[act.id].match(line):
            break
        if m := CHAPTER.match(line):
            pending_chapter = f"Chapter {m.group(1)}"
            continue
        if pending_chapter and line.isupper():
            chapter = f"{pending_chapter} — {line.title()}"
            pending_chapter = None
            continue
        m = re.match(rf"^({expected}[A-Z]?)\.\s*(.*)$", line)
        if m and expected <= act.num_sections:
            close()
            num, rest = m.group(1), m.group(2)
            title = act.titles.get(num, "")
            if act.id == "rti":  # "6. Request for obtaining information. —(1) A person..."
                tm = re.match(r"^(.+?)\.\s*[—–-]+\s*(.*)$", rest)
                if tm:
                    title, rest = tm.group(1).strip(), tm.group(2)
                else:  # title wraps onto the next line
                    title, rest = rest.rstrip(" .—"), ""
            cur = {"num": num, "title": title, "chapter": chapter, "page": pno, "lines": [rest] if rest else []}
            expected += 1
            continue
        if cur is None:
            continue
        cur["lines"].append(line)
    close()

    for name, title, text in SCHEDULES[act.id]:
        sections.append(
            Section(
                id=f"{act.id}-{_norm(name).replace(' ', '-')}",
                act_id=act.id,
                act_name=act.name,
                act_short=act.short,
                section=name,
                title=title,
                chapter="Schedules",
                page=0,
                source_url=act.source_url,
                text=text,
            )
        )

    found = [s for s in sections if s.chapter != "Schedules"]
    if len(found) != act.num_sections:
        raise ValueError(f"{act.id}: expected {act.num_sections} sections, parsed {len(found)}")
    return sections


def main() -> None:
    out = DATA / "processed" / "sections.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out.open("w") as f:
        for act in ACTS:
            secs = parse_act(act)
            total += len(secs)
            for s in secs:
                f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")
            print(f"{act.short}: {len(secs)} sections/schedules")
    print(f"wrote {total} records -> {out.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
