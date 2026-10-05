"""Section-aware chunking.

Most sections fit in one chunk. Long ones (definitions, jurisdiction clauses)
are split on clause/paragraph boundaries, never mid-sentence, with one
paragraph of overlap so a clause and its proviso stay retrievable together.
Every chunk carries a header naming its Act and section, which is embedded and
indexed with the text (a "contextual chunk header").
"""

from dataclasses import dataclass

MAX_CHARS = 1400
OVERLAP_PARAS = 1


@dataclass
class Chunk:
    id: str
    section_id: str
    act_id: str
    chunk_index: int
    header: str
    content: str


def header_for(sec: dict) -> str:
    label = sec["section"] if not sec["section"][0].isdigit() else f"Section {sec['section']}"
    return f"{sec['act_short']} — {label}: {sec['title']}"


def _split_long_para(p: str) -> list[str]:
    """Fallback for a single paragraph longer than MAX_CHARS: split on sentences."""
    out, cur = [], ""
    for sent in p.replace("; ", ";\x00").replace(". ", ".\x00").split("\x00"):
        if cur and len(cur) + len(sent) > MAX_CHARS:
            out.append(cur.strip())
            cur = ""
        cur += sent + " "
    if cur.strip():
        out.append(cur.strip())
    return out


def chunk_section(sec: dict) -> list[Chunk]:
    paras: list[str] = []
    for p in sec["text"].split("\n"):
        paras.extend(_split_long_para(p) if len(p) > MAX_CHARS else [p])

    groups: list[list[str]] = []
    cur: list[str] = []
    for p in paras:
        if cur and sum(len(x) for x in cur) + len(p) > MAX_CHARS:
            groups.append(cur)
            cur = cur[-OVERLAP_PARAS:] if len(cur) > OVERLAP_PARAS else []
            # Drop overlap if it would still overflow.
            if sum(len(x) for x in cur) + len(p) > MAX_CHARS:
                cur = []
        cur.append(p)
    if cur:
        groups.append(cur)

    header = header_for(sec)
    return [
        Chunk(
            id=f"{sec['id']}#{i}",
            section_id=sec["id"],
            act_id=sec["act_id"],
            chunk_index=i,
            header=header + (f" (part {i + 1} of {len(groups)})" if len(groups) > 1 else ""),
            content="\n".join(g),
        )
        for i, g in enumerate(groups)
    ]
