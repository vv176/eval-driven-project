"""
Chunk data_v2/runbooks/*.md by H2 section.

Each runbook gets split into:
  - one preamble chunk (everything before the first ##), section_title=""
  - one chunk per ## section, with the section content

If a single H2 section exceeds MAX_CHARS, it is further split on H3
(### headings) so chunks stay bounded.

The chunk text includes the runbook title and section header inline, so an
embedding captures the topical context (e.g. a "Section 3: Recovery" chunk
that doesn't mention Redis still gets the Redis context via the title prefix).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 2500  # ~600 tokens; safe under embedding limits and keeps recall focused


@dataclass
class Chunk:
    runbook_file: str
    runbook_title: str
    section_title: str
    chunk_index: int
    text: str


def _split_on_pattern(content: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    """Return list of (header_line_or_empty, body) pairs split on the pattern."""
    matches = list(pattern.finditer(content))
    if not matches:
        return [("", content.strip())]

    out: list[tuple[str, str]] = []
    # Preamble: from start up to first match
    if matches[0].start() > 0:
        preamble = content[:matches[0].start()].strip()
        if preamble:
            out.append(("", preamble))

    for i, m in enumerate(matches):
        header = m.group(0).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        out.append((header, body))
    return out


def chunk_runbook(path: Path) -> list[Chunk]:
    content = path.read_text()
    lines = content.split("\n")
    first_line = lines[0].strip() if lines else ""
    runbook_title = first_line.lstrip("# ").strip() or path.stem
    # Strip the H1 so it doesn't get duplicated in chunks
    body = "\n".join(lines[1:]) if first_line.startswith("# ") else content

    h2 = re.compile(r"^## .+$", re.MULTILINE)
    h3 = re.compile(r"^### .+$", re.MULTILINE)

    chunks: list[Chunk] = []
    idx = 0
    for header, section_body in _split_on_pattern(body, h2):
        section_title = header.lstrip("# ").strip() if header else ""
        full_text = (header + "\n\n" + section_body).strip() if header else section_body

        # If this H2 section is too big, sub-split on H3
        if len(full_text) > MAX_CHARS and h3.search(section_body):
            for sub_header, sub_body in _split_on_pattern(section_body, h3):
                sub_section = sub_header.lstrip("# ").strip() if sub_header else section_title
                combined = section_title + " — " + sub_section if sub_section else section_title
                sub_full = (sub_header + "\n\n" + sub_body).strip() if sub_header else sub_body
                # Inline the runbook title for retrieval signal
                prefixed = f"[Runbook: {runbook_title}] [Section: {combined}]\n\n{sub_full}"
                chunks.append(Chunk(
                    runbook_file=path.name,
                    runbook_title=runbook_title,
                    section_title=combined,
                    chunk_index=idx,
                    text=prefixed.strip(),
                ))
                idx += 1
        else:
            prefixed = f"[Runbook: {runbook_title}] [Section: {section_title or 'Overview'}]\n\n{full_text}"
            chunks.append(Chunk(
                runbook_file=path.name,
                runbook_title=runbook_title,
                section_title=section_title,
                chunk_index=idx,
                text=prefixed.strip(),
            ))
            idx += 1

    return chunks


def chunk_directory(runbook_dir: Path) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for p in sorted(runbook_dir.glob("*.md")):
        all_chunks.extend(chunk_runbook(p))
    return all_chunks
