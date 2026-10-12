"""Render the three-page Markdown report with tables and explicit page breaks."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF, FontFace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "report.md"
TARGET = ROOT / "docs" / "report.pdf"


class ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100, 112, 126)
        self.cell(0, 5, f"Routeplan | Aiqon AI Internship                                    {self.page_no()} / {{nb}}")


def main() -> None:
    pdf = ReportPDF(format="A4")
    pdf.set_title("Shipment route selection under cost, time, and risk")
    pdf.set_author("vivekvar-dl")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 15, 18)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for kind, text in _blocks(SOURCE.read_text(encoding="utf-8")):
        pdf.set_text_color(30, 42, 54)
        if kind == "pagebreak":
            pdf.add_page()
        elif kind == "h1":
            pdf.set_font("Helvetica", "B", 17)
            pdf.multi_cell(width, 8, text)
            pdf.ln(2)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_text_color(18, 71, 89)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(width, 6, text)
            pdf.ln(1)
        elif kind == "code":
            pdf.set_font("Courier", size=8.5)
            pdf.set_fill_color(241, 245, 248)
            pdf.multi_cell(width, 4.5, text, fill=True)
            pdf.ln(2)
        elif kind == "table":
            rows = [line.split("|") for line in text.splitlines()]
            col_widths = [max(len(row[i]) for row in rows) + 5 for i in range(len(rows[0]))]
            pdf.set_font("Helvetica", size=9)
            with pdf.table(
                width=width, col_widths=col_widths, line_height=5,
                padding=2, borders_layout="HORIZONTAL_LINES",
                headings_style=FontFace(emphasis="BOLD", color=255, fill_color=(18, 71, 89)),
            ) as table:
                for cells in rows:
                    row = table.row()
                    for cell in cells:
                        row.cell(cell)
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(width, 4.8, text)
            pdf.ln(1.5)
    if pdf.pages_count != 3:
        raise ValueError(f"Report should have 3 pages, got {pdf.pages_count}; adjust the layout")
    pdf.output(str(TARGET))
    print(f"wrote {TARGET} ({pdf.pages_count} pages)")


def _blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []
    code: list[str] = []
    table: list[str] = []
    in_code = False

    def flush() -> None:
        text = " ".join(part.strip() for part in paragraph if part.strip())
        paragraph.clear()
        if text:
            blocks.append(("p", _clean(text)))
        if table:
            blocks.append(("table", "\n".join(table)))
            table.clear()

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
        if line == "<!-- pagebreak -->":
            flush()
            blocks.append(("pagebreak", ""))
            continue
        if line.startswith("# ") or line.startswith("## "):
            flush()
            kind, heading = ("h1", line[2:]) if line.startswith("# ") else ("h2", line[3:])
            blocks.append((kind, _clean(heading)))
            continue
        if line.startswith("|"):
            if paragraph:
                flush()
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(set(cell) <= {"-", ":", " "} for cell in cells):
                table.append("|".join(cells))
            continue
        if not line.strip():
            flush()
            continue
        if table:
            flush()
        paragraph.append(line)
    flush()
    return blocks


def _clean(text: str) -> str:
    return text.replace("`", "").replace("**", "")


if __name__ == "__main__":
    main()
