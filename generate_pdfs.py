"""
Generates synthetic but realistic-looking P&C insurance PDFs from extracted Foundry content.
Output: data/<claim_id>/<filename>.pdf
"""

import json
import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
JSON_PATH = os.path.join(DATA_DIR, "claims_data.json")

# ── colour palette (professional insurance look) ──────────────────────────────
NAVY     = colors.HexColor("#1B2A4A")
BLUE     = colors.HexColor("#2E5FA3")
LIGHT    = colors.HexColor("#EEF3FA")
BORDER   = colors.HexColor("#C5D0E0")
MID_GRAY = colors.HexColor("#555555")
DARK     = colors.HexColor("#222222")

# ── document-type → header colour ─────────────────────────────────────────────
DOC_COLORS = {
    "Policy":                 colors.HexColor("#1B4F72"),
    "FNOL":                   colors.HexColor("#1A5276"),
    "Claimant Statement":     colors.HexColor("#1F618D"),
    "Coverage Determination": colors.HexColor("#117A65"),
    "Proof Of Loss":          colors.HexColor("#117A65"),
    "Claim Proof Of Loss":    colors.HexColor("#117A65"),
    "Claim Fnol":             colors.HexColor("#1A5276"),
    "Adjuster Notes":         colors.HexColor("#6E2F1A"),
    "Investigation Report":   colors.HexColor("#6E2F1A"),
    "Reserve Analysis":       colors.HexColor("#4A235A"),
    "Settlement Agreement":   colors.HexColor("#784212"),
    "Payment Authorization":  colors.HexColor("#784212"),
    "Final Settlement":       colors.HexColor("#784212"),
    "Closure Summary":        colors.HexColor("#1D8348"),
    "Reopening Notice":       colors.HexColor("#B7770D"),
}

COMPANY = "Meridian Risk & Insurance Group"
ADDRESS = "One Financial Center, Suite 4200 • New York, NY 10041"
PHONE   = "(212) 555-0100 • claims@meridianrisk.com • www.meridianrisk.com"


def make_styles(header_color):
    base = getSampleStyleSheet()
    styles = {}

    styles["h1"] = ParagraphStyle(
        "h1", parent=base["Normal"],
        fontSize=16, fontName="Helvetica-Bold",
        textColor=colors.white, spaceAfter=2,
        leading=20,
    )
    styles["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"],
        fontSize=10, fontName="Helvetica-Bold",
        textColor=colors.white, spaceAfter=2,
    )
    styles["section"] = ParagraphStyle(
        "section", parent=base["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
        textColor=header_color, spaceBefore=10, spaceAfter=4,
        borderPadding=(0, 0, 2, 0),
    )
    styles["body"] = ParagraphStyle(
        "body", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=DARK, leading=13, spaceAfter=4,
    )
    styles["small"] = ParagraphStyle(
        "small", parent=base["Normal"],
        fontSize=7.5, fontName="Helvetica",
        textColor=MID_GRAY, leading=11,
    )
    styles["center"] = ParagraphStyle(
        "center", parent=base["Normal"],
        fontSize=8, fontName="Helvetica",
        textColor=colors.white, alignment=TA_CENTER,
    )
    styles["footer"] = ParagraphStyle(
        "footer", parent=base["Normal"],
        fontSize=7, fontName="Helvetica",
        textColor=MID_GRAY, alignment=TA_CENTER,
    )
    return styles


def header_block(story, doc_type, claim_id, styles, header_color):
    """Coloured letterhead banner."""
    # Company name + doc type table
    header_data = [
        [Paragraph(COMPANY, styles["h1"]),
         Paragraph(doc_type.upper(), styles["h2"])],
        [Paragraph(f"{ADDRESS}", styles["center"]),
         Paragraph(f"Claim ID: {claim_id}", styles["center"])],
    ]
    t = Table(header_data, colWidths=[4.5 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), header_color),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [header_color.clone(alpha=0.85)]),
    ]))
    story.append(t)
    story.append(Paragraph(PHONE, styles["footer"]))
    story.append(Spacer(1, 0.15 * inch))


def kv_table(data_pairs, col_w=(2.0 * inch, 4.5 * inch)):
    """Two-column key-value table."""
    rows = []
    for k, v in data_pairs:
        rows.append([
            Paragraph(f"<b>{k}</b>", ParagraphStyle(
                "kk", fontSize=8.5, fontName="Helvetica-Bold",
                textColor=MID_GRAY, leading=12,
            )),
            Paragraph(str(v), ParagraphStyle(
                "vv", fontSize=8.5, fontName="Helvetica",
                textColor=DARK, leading=12,
            )),
        ])
    t = Table(rows, colWidths=list(col_w))
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


def section_rule(story, label, styles, header_color):
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(label, styles["section"]))
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=header_color, spaceAfter=4))


def parse_kv_block(text):
    """Extract key: value pairs from a text block."""
    pairs = []
    for line in text.split("\n"):
        line = line.strip()
        if ":" in line and len(line) < 120:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if k and v and len(k) < 50:
                pairs.append((k, v))
    return pairs


def split_sections(text):
    """Return list of (section_title, body_text) tuples by detecting ALL-CAPS headers."""
    sections = []
    current_title = "DOCUMENT"
    current_body  = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and stripped == stripped.upper() and len(stripped) > 3 \
                and not re.match(r"^[\d\W]+$", stripped):
            if current_body:
                sections.append((current_title, "\n".join(current_body).strip()))
            current_title = stripped
            current_body  = []
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_title, "\n".join(current_body).strip()))
    return sections


def build_pdf(record, output_path):
    doc_type     = record.get("file_type", "Document")
    claim_id     = record.get("claim_id", "")
    extracted    = record.get("extracted_text", "")
    header_color = DOC_COLORS.get(doc_type, NAVY)
    styles       = make_styles(header_color)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.6 * inch,   bottomMargin=0.75 * inch,
    )

    story = []
    header_block(story, doc_type, claim_id, styles, header_color)

    sections = split_sections(extracted)

    for title, body in sections:
        if not body.strip():
            continue

        section_rule(story, title, styles, header_color)

        # Try to render as a KV table if lots of key:value pairs
        kv_pairs = parse_kv_block(body)
        kv_lines = sum(1 for ln in body.split("\n") if ":" in ln and len(ln.strip()) < 120)
        total_lines = max(1, len([l for l in body.split("\n") if l.strip()]))

        if kv_pairs and kv_lines / total_lines > 0.5 and len(kv_pairs) >= 3:
            story.append(KeepTogether([kv_table(kv_pairs)]))
        else:
            # Prose paragraph — escape special chars
            safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for para in safe.split("\n\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(para.replace("\n", " "), styles["body"]))

        story.append(Spacer(1, 0.05 * inch))

    # Footer confidentiality note
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "CONFIDENTIAL — This document contains proprietary claim information. "
        "Unauthorised disclosure is prohibited. © Meridian Risk &amp; Insurance Group.",
        styles["footer"],
    ))

    doc.build(story)


def main():
    with open(JSON_PATH) as f:
        records = json.load(f)

    print(f"Generating {len(records)} PDFs...\n")
    ok, failed = 0, []

    for i, rec in enumerate(records, 1):
        claim_id  = rec.get("claim_id", "unknown")
        filename  = rec.get("path", f"doc_{i}.pdf")
        claim_dir = os.path.join(DATA_DIR, claim_id)
        os.makedirs(claim_dir, exist_ok=True)
        out = os.path.join(claim_dir, filename)

        try:
            build_pdf(rec, out)
            size = os.path.getsize(out)
            print(f"[{i:3d}/{len(records)}] ✓  {claim_id}/{filename}  ({size:,} bytes)")
            ok += 1
        except Exception as e:
            print(f"[{i:3d}/{len(records)}] ✗  {claim_id}/{filename}  ERROR: {e}")
            failed.append(filename)

    print(f"\n{'─'*60}")
    print(f"Done. {ok}/{len(records)} PDFs generated in ./data/")
    if failed:
        print(f"Failed ({len(failed)}): {', '.join(failed)}")


if __name__ == "__main__":
    main()
