"""
build_final.py -- Synthesize the final Overleaf-ready thesis.

Produces a single self-contained 4.Thesis_Final/main.tex by taking the template
in 1.Thesis_Tempelate/main.tex and replacing its placeholder bodies with the
drafted content in 3.Thesis_Text/. The template's preamble, title page,
declaration, certificate, TOC machinery, formatting, and chapter/section order
are preserved EXACTLY -- only the lipsum/dummy content is swapped out.

It also copies every figure (the 10 PNGs in 2.Thesis_Image + the college logo)
into 4.Thesis_Final/images/ so the folder can be zipped and uploaded to Overleaf
as-is (compiler: pdfLaTeX).

RUN:  python Thesis_MP/build_final.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../Thesis_MP
TEMPLATE = HERE / "1.Thesis_Tempelate" / "main.tex"
TEXT = HERE / "3.Thesis_Text"
IMG_SRC = HERE / "2.Thesis_Image"
LOGO_SRC = HERE / "1.Thesis_Tempelate" / "images" / "iiitr_logo.png"
OUT_DIR = HERE / "4.Thesis_Final"
OUT_TEX = OUT_DIR / "main.tex"
OUT_IMG = OUT_DIR / "images"

# ---- USER INPUTS: edit these three before final submission -----------------
STUDENT_NAME = r"<< YOUR FULL NAME >>"
ROLL_NUMBER = r"<< YOUR ROLL NO >>"
SUPERVISOR = r"Dr.~<< SUPERVISOR NAME >>"
SUBMISSION = r"May 2026"

TITLE = ("FinITR-AI: An Agentic Multi-Document Reconciliation System "
         "for Indian Income Tax Return Filing")
TITLE_DISPLAY = (r"FinITR-AI \\ AN AGENTIC MULTI-DOCUMENT RECONCILIATION SYSTEM "
                 r"\\ FOR INDIAN INCOME TAX RETURN FILING")

# exact original lines in the template -> replacements
SUBSTITUTIONS = {
    r"\newcommand{\thesisTitle}{Title of Your Project as a Single Line}":
        r"\newcommand{\thesisTitle}{" + TITLE + r"}",
    r"\newcommand{\thesisTitleDisplay}{TITLE OF YOUR PROJECT \\ IN TWO OR THREE LINES \\ AS NEEDED}":
        r"\newcommand{\thesisTitleDisplay}{" + TITLE_DISPLAY + r"}",
    r"\newcommand{\studentName}{Your Full Name}":
        r"\newcommand{\studentName}{" + STUDENT_NAME + r"}",
    r"\newcommand{\rollNumber}{CS21B10XX}":
        r"\newcommand{\rollNumber}{" + ROLL_NUMBER + r"}",
    r"\newcommand{\supervisorName}{Dr.~Supervisor Name}":
        r"\newcommand{\supervisorName}{" + SUPERVISOR + r"}",
    r"\newcommand{\submissionMonthYear}{May 2025}":
        r"\newcommand{\submissionMonthYear}{" + SUBMISSION + r"}",
}

# content files in document order
ABSTRACT = TEXT / "01_abstract.tex"
CHAPTERS = [
    "02_introduction.tex",
    "03_literature_survey.tex",
    "04_methodology.tex",
    "05_challenges_and_solutions.tex",
    "06_results_and_discussion.tex",
    "07_tools_technologies_parameters.tex",
    "08_conclusion_future_scope.tex",
]
BIB = TEXT / "09_bibliography.tex"

# anchors in the template
A_ABSTRACT_END = r"\addcontentsline{toc}{chapter}{Abstract}"
A_TOC = r"\tableofcontents"
A_CH1 = r"\chapter{Introduction}"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def main() -> None:
    if not TEMPLATE.exists():
        sys.exit(f"Template not found: {TEMPLATE}")
    tpl = read(TEMPLATE)

    # 1. apply USER INPUT substitutions
    for old, new in SUBSTITUTIONS.items():
        if old not in tpl:
            print(f"  WARNING: template line not found, skipped:\n    {old}")
        tpl = tpl.replace(old, new)

    # 2. slice the template at stable anchors
    for anc in (A_ABSTRACT_END, A_TOC, A_CH1):
        if anc not in tpl:
            sys.exit(f"Anchor not found in template: {anc}")

    header = tpl[: tpl.index(A_ABSTRACT_END) + len(A_ABSTRACT_END)]
    toc_block = "\\clearpage\n" + tpl[tpl.index(A_TOC): tpl.index(A_CH1)]

    # 3. assemble body from the drafted content
    abstract = read(ABSTRACT)
    chapters = "\n\n".join(read(TEXT / c) for c in CHAPTERS)
    bibitems = read(BIB)

    bibliography = (
        "% ===========================================================\n"
        "% BIBLIOGRAPHY\n"
        "% ===========================================================\n"
        r"\addcontentsline{toc}{chapter}{Bibliography}" + "\n\n"
        r"\begin{thebibliography}{99}" + "\n\n"
        + bibitems + "\n\n"
        r"\end{thebibliography}" + "\n"
    )

    doc = (
        header + "\n\n"
        + "% ---- ABSTRACT CONTENT ----\n" + abstract + "\n\n"
        + toc_block + "\n"
        + chapters + "\n\n"
        + bibliography + "\n"
        + r"\end{document}" + "\n"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_TEX.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT_TEX}  ({len(doc.splitlines())} lines)")

    # 4. copy images + logo
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    pngs = sorted(IMG_SRC.glob("*.png"))
    for p in pngs:
        shutil.copy2(p, OUT_IMG / p.name)
    if LOGO_SRC.exists():
        shutil.copy2(LOGO_SRC, OUT_IMG / LOGO_SRC.name)
        print(f"copied logo -> images/{LOGO_SRC.name}")
    else:
        print(f"  WARNING: logo not found at {LOGO_SRC}")
    print(f"copied {len(pngs)} figures -> {OUT_IMG}")

    # 5. quick sanity checks
    print("\n--- sanity ---")
    print(f"  \\begin{{document}}: {doc.count(chr(92)+'begin{document}')}, "
          f"\\end{{document}}: {doc.count(chr(92)+'end{document}')}")
    print(f"  \\chapter count: {doc.count(chr(92)+'chapter{')}")
    if "₹" in doc:
        print("  WARNING: rupee glyph (Rs symbol) present -- may not render with lmodern")
    else:
        print("  OK: no raw rupee glyph (uses 'Rs.')")
    if "\\lipsum" in doc:
        print("  WARNING: stray \\lipsum still present")
    else:
        print("  OK: no \\lipsum placeholders remain")
    # verify every \includegraphics target exists
    import re
    missing = []
    for m in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", doc):
        name = Path(m).name
        if not (OUT_IMG / name).exists():
            missing.append(name)
    if missing:
        print(f"  WARNING: missing image files: {sorted(set(missing))}")
    else:
        print("  OK: every \\includegraphics target is present in images/")


if __name__ == "__main__":
    main()
