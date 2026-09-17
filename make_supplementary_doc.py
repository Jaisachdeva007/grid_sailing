#!/usr/bin/env python3
"""
Generate Grid Sailing supplementary document as .docx
Run: /Users/jaisachdeva/PycharmProjects/Intune/.venv/bin/python3 make_supplementary_doc.py
"""

import io
import os
from PIL import Image, ImageDraw
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = "/Users/jaisachdeva/Desktop/GridSailing_Juliet"
os.makedirs(OUT, exist_ok=True)

KEY_MAP = {1: (-1, 0), 2: (1, 1), 3: (1, -1)}

# ── PIL grid drawing ──────────────────────────────────────────────────────────

def draw_grid_img(start, goal, trail=None, cell=52, gap=5, n=6, pad=9):
    trail_s = {tuple(t) for t in (trail or [])}
    W = n * (cell + gap) - gap + 2 * pad
    img = Image.new("RGB", (W, W), (8, 8, 15))
    d = ImageDraw.Draw(img)

    for r in range(n):
        for c in range(n):
            x = pad + c * (cell + gap)
            y = pad + r * (cell + gap)
            pos = (r, c)
            if pos == tuple(start):
                fill, bord = (20, 80, 180), (74, 128, 232)
            elif pos == tuple(goal):
                fill, bord = (180, 130, 15), (220, 162, 28)
            elif pos in trail_s:
                fill, bord = (30, 60, 140), (48, 90, 192)
            else:
                fill, bord = (22, 22, 44), (38, 38, 66)
            d.rounded_rectangle([x, y, x + cell, y + cell],
                                 radius=7, fill=fill, outline=bord, width=1)

    s = cell / 56.0

    # Mouse at start
    cx = pad + start[1] * (cell + gap) + cell // 2
    cy = pad + start[0] * (cell + gap) + cell // 2
    for ex in [int(cx - 13 * s), int(cx + 13 * s)]:
        d.ellipse([ex - int(9*s), cy - int(22*s), ex + int(9*s), cy - int(4*s)], fill=(195, 200, 220))
        d.ellipse([ex - int(5*s), cy - int(19*s), ex + int(5*s), cy - int(7*s)], fill=(220, 145, 158))
    hr = int(17 * s)
    d.ellipse([cx - hr, cy - hr - int(2*s), cx + hr, cy + hr - int(2*s)], fill=(195, 200, 220))
    for ex in [int(cx - 6*s), int(cx + 6*s)]:
        d.ellipse([ex - int(3*s), cy - int(7*s), ex + int(3*s), cy - int(1*s)], fill=(18, 18, 36))
    d.ellipse([int(cx - 3*s), int(cy + 2*s), int(cx + 3*s), int(cy + 8*s)], fill=(220, 145, 158))

    # Cheese at goal
    gx = pad + goal[1] * (cell + gap) + cell // 2
    gy = pad + goal[0] * (cell + gap) + cell // 2
    pts = [(gx, int(gy - 20*s)), (int(gx - 22*s), int(gy + 16*s)), (int(gx + 22*s), int(gy + 16*s))]
    d.polygon(pts, fill=(255, 216, 42), outline=(190, 148, 14))
    for hx, hy, hr2 in [(gx, int(gy + 4*s), int(5*s)),
                        (int(gx - 11*s), int(gy + 12*s), int(4*s)),
                        (int(gx + 11*s), int(gy + 12*s), int(3*s))]:
        d.ellipse([hx - hr2, hy - hr2, hx + hr2, hy + hr2], fill=(148, 100, 8))

    return img


def img_buf(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def build_path(start, seq):
    pos = list(start)
    path = [pos[:]]
    for k in seq:
        dr, dc = KEY_MAP[k]
        nr, nc = pos[0] + dr, pos[1] + dc
        if 0 <= nr < 6 and 0 <= nc < 6:
            pos = [nr, nc]
        path.append(pos[:])
    return path


# ── python-docx helpers ───────────────────────────────────────────────────────

def shade_cell(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    tcPr.append(shd)


def hdr_row(table, labels, bg="E8EBF8"):
    row = table.rows[0]
    for i, lbl in enumerate(labels):
        c = row.cells[i]
        c.text = lbl
        shade_cell(c, bg)
        run = c.paragraphs[0].runs[0]
        run.bold = True
        run.font.size = Pt(10)


def body_row(table, row_idx, values):
    row = table.rows[row_idx]
    for i, val in enumerate(values):
        row.cells[i].text = val
        for run in row.cells[i].paragraphs[0].runs:
            run.font.size = Pt(10)


def add_para(doc, text, bold=False, italic=False, size=None, color=None, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor(*bytes.fromhex(color.lstrip("#")))
    return p


def add_callout(doc, text):
    """Orange left-border callout using paragraph shading + border (no table sizing issues)."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Cm(0.4)
    p.paragraph_format.right_indent = Cm(0.4)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(10)

    # Background shading
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "FFF4EC")
    pPr.append(shd)

    # Left border bar
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "24")   # 3 pt thick
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), "E07040")
    pBdr.append(left)
    pPr.append(pBdr)

    run = p.add_run(text)
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(120, 38, 0)


# ══════════════════════════════════════════════════════════════════════════════
# Build the document
# ══════════════════════════════════════════════════════════════════════════════
doc = Document()

# Page margins
sec = doc.sections[0]
sec.top_margin = sec.bottom_margin = Cm(2.5)
sec.left_margin = sec.right_margin = Cm(2.8)

# Title block
eyebrow = doc.add_paragraph()
eyebrow.paragraph_format.space_after = Pt(4)
er = eyebrow.add_run("SUPPLEMENTARY DOCUMENTATION")
er.bold = True
er.font.size = Pt(9)
er.font.color.rgb = RGBColor(74, 125, 232)

title = doc.add_heading("Grid Sailing Task — Repeated vs Random Grid Design", level=0)
title.paragraph_format.space_after = Pt(6)

sub = doc.add_paragraph()
sub.paragraph_format.space_after = Pt(18)
sr = sub.add_run(
    "For peer reviewers · Grid structure, puzzle validity, repeated/random distinction, "
    "and trial distribution across block types."
)
sr.italic = True
sr.font.size = Pt(10)
sr.font.color.rgb = RGBColor(90, 90, 128)


# ── 1. Task Overview ──────────────────────────────────────────────────────────
doc.add_heading("1.  Task Overview", level=1)

add_para(
    doc,
    "Participants navigate a virtual mouse from a start cell to a goal cell (marked with cheese) "
    "on a 6×6 grid using a three-button numeric keypad. Each keypress moves the cursor in a "
    "fixed direction; the task requires planning and executing a multi-step key sequence "
    "entirely from memory. The same interface runs across all three experimental groups — "
    "Physical Practice (PP), Motor Imagery (MI), and Control (CTRL) — with only the "
    "post-input action phase differing between groups.",
)

doc.add_heading("Key Mappings", level=2)

km = doc.add_table(rows=4, cols=3)
km.style = "Table Grid"
hdr_row(km, ["Key", "Direction", "Grid Movement"])
body_row(km, 1, ["1", "↑  UP", "Row −1, Col 0  (index finger)"])
body_row(km, 2, ["2", "↘  DOWN-RIGHT", "Row +1, Col +1  (middle finger)"])
body_row(km, 3, ["3", "↙  DOWN-LEFT", "Row +1, Col −1  (ring finger)"])
for i in range(1, 4):
    km.rows[i].cells[0].paragraphs[0].runs[0].bold = True

doc.add_paragraph()
add_para(
    doc,
    "A trial is marked correct only if the participant reaches the goal cell and all three "
    "keys (1, 2, and 3) appear in the executed sequence. This ensures all three fingers are "
    "engaged on every valid trial.",
)


# ── 2. Valid Puzzle Pool ──────────────────────────────────────────────────────
doc.add_heading("2.  Valid Puzzle Pool", level=1)

add_para(
    doc,
    "Puzzles are generated at session start using Breadth-First Search (BFS) from every "
    "possible start cell on the 6×6 grid. Because BFS explores cells in order of increasing "
    "distance, the first time any goal cell is reached, that distance is the guaranteed "
    "minimum — no shorter route to the same goal can exist. A puzzle is only added to the "
    "pool if its BFS minimum path length falls between 5 and 7 steps (inclusive), ensuring "
    "both challenge and tractability.",
)

pt = doc.add_table(rows=5, cols=2)
pt.style = "Table Grid"
hdr_row(pt, ["Metric", "Value"])
pool_data = [
    ("Total valid puzzles", "182"),
    ("5-step puzzles (minimum complexity)", "82"),
    ("6-step puzzles", "64"),
    ("7-step puzzles (maximum complexity)", "36"),
]
for i, (k, v) in enumerate(pool_data):
    body_row(pt, i + 1, [k, v])
    pt.rows[i + 1].cells[1].paragraphs[0].runs[0].bold = True

doc.add_paragraph()
add_para(
    doc,
    "Note: Of the 182 valid puzzles, 34 have an optimal BFS path that naturally uses all "
    "three keys. The remaining 148 use two keys optimally (1+2 or 1+3). In either case, "
    "participants must include all three keys in their executed sequence to receive any "
    "correctness score — they may take a slightly longer route than the BFS minimum to "
    "satisfy this requirement.",
)


# ── 3. The Repeated Grid ──────────────────────────────────────────────────────
doc.add_heading("3.  The Repeated Grid", level=1)

add_para(
    doc,
    "One puzzle is designated as the repeated puzzle and used across the majority of practice "
    "and test trials for every participant. Its purpose is to measure within-participant "
    "learning on a fixed motor sequence over the course of the study. The repeated puzzle is "
    "selected by the researcher before data collection begins via the Researcher Setup screen.",
)

doc.add_heading("The Repeated Puzzle", level=2)
add_para(
    doc,
    "The repeated puzzle used in this study is: start (row 1, col 1) → goal (row 4, col 3), "
    "optimal sequence [1, 2, 2, 2, 3], length 5 steps. This puzzle was selected from the "
    "valid pool and confirmed by BFS — no shorter route to the goal exists.",
)

REP_START = [1, 1]
REP_GOAL  = [4, 3]
REP_SEQ   = [1, 2, 2, 2, 3]
rep_path  = build_path(REP_START, REP_SEQ)
rep_trail = [p for p in rep_path[1:-1]]
rep_img   = draw_grid_img(REP_START, REP_GOAL, trail=rep_trail, cell=54)
rep_p = doc.add_paragraph()
rep_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
rep_p.add_run().add_picture(img_buf(rep_img), width=Inches(2.7))

# Step trace
trace_p = doc.add_paragraph()
trace_p.paragraph_format.space_before = Pt(4)
trace_p.add_run("Step trace:  ").bold = True
cells_trace = [(1,1), (0,1), (1,2), (2,3), (3,4), (4,3)]
keys_trace  = [1, 2, 2, 2, 3]
for i, cp in enumerate(cells_trace):
    label = f"({cp[0]},{cp[1]})"
    r = trace_p.add_run(label)
    r.font.size = Pt(10)
    if cp == tuple(REP_START):
        r.bold = True
        r.font.color.rgb = RGBColor(74, 128, 232)
    elif cp == tuple(REP_GOAL):
        r.bold = True
        r.font.color.rgb = RGBColor(200, 144, 10)
    if i < len(keys_trace):
        arr = trace_p.add_run(f"  →[{keys_trace[i]}]→  ")
        arr.font.size = Pt(10)
        arr.font.color.rgb = RGBColor(140, 140, 180)

add_para(
    doc,
    "Keys used: Key 1 × 1,  Key 2 × 3,  Key 3 × 1 — all three fingers required.",
    color="5A5A80", size=9.5,
)


# ── 4. Random Grids ───────────────────────────────────────────────────────────
doc.add_heading("4.  Random Grids", level=1)

add_para(
    doc,
    "Every trial that is not the repeated puzzle draws from the random pool — the remaining "
    "valid puzzles after the repeated puzzle is fixed. Random puzzles expose participants to "
    "a variety of start and goal positions and are never shown more than once within a "
    "session. They serve as contextual interference and provide a measure of general motor "
    "skill transfer. The diagrams below illustrate the spatial variety present in the pool.",
)

RAND_EXAMPLES = [
    ([0, 0], [4, 3]),
    ([0, 4], [4, 1]),
    ([2, 0], [0, 3]),
    ([1, 2], [4, 4]),
    ([3, 4], [0, 2]),
    ([4, 1], [1, 4]),
]

rand_tbl = doc.add_table(rows=3, cols=2)
rand_tbl.style = "Table Grid"
for ri in range(3):
    for ci in range(2):
        idx = ri * 2 + ci
        s, g = RAND_EXAMPLES[idx]
        cell_img = draw_grid_img(s, g, cell=46)
        cell = rand_tbl.cell(ri, ci)
        imgp = cell.paragraphs[0]
        imgp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        imgp.add_run().add_picture(img_buf(cell_img), width=Inches(1.65))
        lbl = cell.add_paragraph(f"start ({s[0]},{s[1]})  →  goal ({g[0]},{g[1]})")
        lbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in lbl.runs:
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(90, 90, 128)

doc.add_paragraph()


# ── 5. Sequence Exclusion ─────────────────────────────────────────────────────
doc.add_heading("5.  Sequence-Based Exclusion of Random Puzzles", level=1)

add_para(
    doc,
    "To prevent memory of the repeated puzzle's key sequence from directly contaminating "
    "random trials, any random puzzle whose BFS-optimal sequence matches the repeated "
    "puzzle's optimal sequence is excluded from the random pool at session startup.",
)
add_para(
    doc,
    "Two grids can share an identical key sequence while having different start and goal "
    "positions — the same pattern of Up/Down-Right/Down-Left presses traverses different "
    "cells depending on where you start. Presenting such a puzzle as a 'random' trial would "
    "give participants additional practice on the repeated motor programme, confounding the "
    "repeated vs random manipulation.",
)
add_para(
    doc,
    "In practice, for a typical repeated puzzle choice, this exclusion removes 0–3 puzzles "
    "from the random pool, leaving at least 179 valid random options.",
)


# ── 6. Trial Distribution ─────────────────────────────────────────────────────
doc.add_heading("6.  Trial Distribution by Block Type", level=1)

add_para(
    doc,
    "Each block contains 20 trials. The ratio of repeated to random trials varies by block "
    "type to balance learning exposure with unbiased measurement.",
)

dt = doc.add_table(rows=4, cols=4)
dt.style = "Table Grid"
hdr_row(dt, ["Block Type", "Repeated", "Random", "Per 20-Trial Block"])
dist_data = [
    ("Familiarisation", "0%", "100%", "0 repeated · 20 random"),
    ("Practice", "72%", "28%", "~14 repeated · ~6 random"),
    ("Pre-test / Post-test", "60%", "40%", "12 repeated · 8 random"),
]
for i, row_d in enumerate(dist_data):
    body_row(dt, i + 1, row_d)

doc.add_paragraph()
add_para(
    doc,
    "Familiarisation blocks are 100% random by design — participants are learning the key "
    "mappings and interface during this phase, so exposure to the repeated sequence would "
    "confound baseline measurement.",
)


# ── 7. Session Structure ──────────────────────────────────────────────────────
doc.add_heading("7.  Session Structure Summary", level=1)

st = doc.add_table(rows=4, cols=4)
st.style = "Table Grid"
hdr_row(st, ["Session", "Block Order", "Total Blocks", "Total Trials"])
sess_data = [
    ("Session 1", "Fam · Fam · Pre-test · Practice · Practice", "5", "100"),
    ("Session 2", "Practice · Practice", "2", "40"),
    ("Session 3", "Practice · Practice · Post-test", "3", "60"),
]
for i, row_d in enumerate(sess_data):
    body_row(st, i + 1, row_d)

doc.add_paragraph()
add_para(
    doc,
    "Pre-test and post-test blocks use the same 60/40 ratio so that performance comparisons "
    "between them are not confounded by differing proportions of the repeated puzzle.",
    color="5A5A80", size=9.5,
)


# ── Save ──────────────────────────────────────────────────────────────────────
out_path = os.path.join(OUT, "supplementary_grid_design.docx")
doc.save(out_path)
print(f"Saved → {out_path}")
