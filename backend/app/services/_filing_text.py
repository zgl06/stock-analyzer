"""Utilities for converting SEC filing HTML to plain text."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


# Tags whose entire subtree we discard before extracting text.
_DROP_TAGS = {"script", "style", "nav", "header", "footer", "noscript"}

# Heuristic: table-of-contents sections usually contain many short lines
# with page numbers like "... 14".  We drop <div> blocks where more than
# 60% of lines end with digits preceded by dots/spaces (ToC lines).
_TOC_LINE_RE = re.compile(r"\.{2,}\s*\d+\s*$")


def html_to_text(html: str) -> str:
    """Strip HTML to clean plain text suitable for chunking.

    Steps:
    1. Parse with BeautifulSoup (lxml or html.parser).
    2. Remove script/style/nav/header/footer subtrees.
    3. Drop probable table-of-contents <div> blocks heuristically.
    4. Extract text, collapse whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()

    # Heuristic ToC removal: inspect top-level <div> blocks.
    for div in soup.find_all("div"):
        lines = [ln.strip() for ln in div.get_text("\n").splitlines() if ln.strip()]
        if len(lines) >= 6:
            toc_hits = sum(1 for ln in lines if _TOC_LINE_RE.search(ln))
            if toc_hits / len(lines) > 0.6:
                div.decompose()

    raw = soup.get_text(separator="\n")
    # Collapse runs of blank lines to at most two newlines.
    text = re.sub(r"\n{3,}", "\n\n", raw)
    # Collapse inline whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
