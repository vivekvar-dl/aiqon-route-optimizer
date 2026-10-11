"""Render docs/report.md to docs/report.pdf. Helvetica, A4, no remote assets."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "report.md"
TARGET = ROOT / "docs" / "report.pdf"


def main() -> None:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for block in _blocks(SOURCE.read_text()):
        kind, text = block
        if kind == "h1":
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(width, 8, text)
            pdf.ln(2)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(width, 7, text)
            pdf.ln(1)
        elif kind == "code":
            pdf.set_font("Courier", size=8)
            pdf.multi_cell(width, 4, text)
            pdf.ln(1)
        else:
            pdf.set_font("Helvetica", size=10.5)
            pdf.multi_cell(width, 5.2, text)
            pdf.ln(1.4)
    pdf.output(str(TARGET))
    print(f"wrote {TARGET} ({pdf.pages_count} pages)")


def _blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False

    def flush() -> None:
        text = " ".join(part.strip() for part in paragraph if part.strip())
        paragraph.clear()
        if text:
            blocks.append(("p", _clean(text)))

    for line in markdown.splitlines():
        if line.startswith("```"):
            if in_code:
                blocks.append(("code", "\n".join(code)))
                code.clear()
                in_code = False
            else:
                flush()
                in_code = True
            continue
        if in_code:
            code.append(line)
            continue
        if line.startswith("# "):
            flush()
            blocks.append(("h1", _clean(line[2:])))
            continue
        if line.startswith("## "):
            flush()
            blocks.append(("h2", _clean(line[3:])))
            continue
        if line.startswith("|"):
            flush()
            if set(line.replace("|", "").replace(":", "").strip()) <= {"-", " "}:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            blocks.append(("code", "  ".join(cells)))
            continue
        if not line.strip():
            flush()
            continue
        paragraph.append(line)
    flush()
    return blocks


def _clean(text: str) -> str:
    return (
        text.replace("`", "")
        .replace("**", "")
        .replace("CVaR", "CVaR")
    )


if __name__ == "__main__":
    main()
