# Nexon Word (DOCX) Guide

Reference for building on-brand Word documents — manually or via python-docx.

---

## Page Setup

| Setting | Value |
|---------|-------|
| Page size | A4 (210 × 297 mm) |
| Margins — all sides | 2.54 cm (1 inch) |
| Header | Logo left-aligned + thin black rule beneath |
| Footer | Page number, right-aligned, Overlay grey |

---

## Paragraph Styles Map

| Word Style Name | Font | Size | Weight | Colour |
|----------------|------|------|--------|--------|
| Heading 1 | Arial | 32pt | Bold | `#000000` (Retina) |
| Heading 2 | Arial | 24pt | Bold | `#000000` (Retina) |
| Heading 3 | Arial | 18pt | Bold | `#000000` (Retina) |
| Normal / Body Text | Arial | 11pt | Regular | `#343842` (Overlay) |
| CTA | Arial | 11pt | Bold | `#00c982` (Wildcard) |
| Caption | Arial | 9pt | Regular | `#343842` |
| Quote | Arial | 11pt | Italic | `#343842` |

- Use italics **only** for quotations.
- Never use secondary colours for large body text blocks.

---

## Header Setup

1. Left-align the official PNG logo (white wordmark on black). Minimum 100px wide.
2. Add a thin black horizontal rule (`#000000`, 1pt) beneath the logo, spanning the full text width.
3. Do not add any other content to the header.

---

## Cover Page Spec

| Element | Spec |
|---------|------|
| Page background | Black (`#000000`) |
| Logo | Top-left, white wordmark, ≥100px wide |
| Divider line | Wildcard green (`#00c982`), 2pt, full width, ~30% down page |
| Title (H1) | White, Arial Bold, 40pt |
| Subtitle | White, Arial, 16pt, 70% opacity |
| Client/date block | White, Arial, 11pt, bottom-left |

---

## python-docx Pattern

```python
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

# ── Page margins ──────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin    = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin   = Cm(2.54)
    section.right_margin  = Cm(2.54)

# ── Header: logo + rule ───────────────────────────────────────────────
header = doc.sections[0].header
header_para = header.paragraphs[0]
header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
run = header_para.add_run()
run.add_picture('nexon-logo-black-bg.png', width=Cm(3.5))  # ~100px equivalent

# Add bottom border (thin black rule) to header paragraph
pPr = header_para._p.get_or_add_pPr()
pBdr = OxmlElement('w:pBdr')
bottom = OxmlElement('w:bottom')
bottom.set(qn('w:val'), 'single')
bottom.set(qn('w:sz'), '6')       # 0.75pt line
bottom.set(qn('w:color'), '000000')
pBdr.append(bottom)
pPr.append(pBdr)

# ── Heading 1 ─────────────────────────────────────────────────────────
h1 = doc.add_heading('Document Title', level=1)
h1.runs[0].font.color.rgb = RGBColor(0x00, 0x00, 0x00)
h1.runs[0].font.name = 'Arial'
h1.runs[0].font.size = Pt(32)

# ── Body paragraph ────────────────────────────────────────────────────
p = doc.add_paragraph('Body text goes here. Active voice. Second-person "you".')
p.runs[0].font.name  = 'Arial'
p.runs[0].font.size  = Pt(11)
p.runs[0].font.color.rgb = RGBColor(0x34, 0x38, 0x42)  # Overlay

# ── CTA run ───────────────────────────────────────────────────────────
cta_para = doc.add_paragraph()
cta_run = cta_para.add_run('Learn more →')
cta_run.bold = True
cta_run.font.name  = 'Arial'
cta_run.font.size  = Pt(11)
cta_run.font.color.rgb = RGBColor(0x00, 0xC9, 0x82)  # Wildcard

doc.save('output.docx')
```

---

## Colour Constants (python-docx)

```python
from docx.shared import RGBColor

RETINA    = RGBColor(0x00, 0x00, 0x00)
CLOUD     = RGBColor(0xFF, 0xFF, 0xFF)
SATELLITE = RGBColor(0xF7, 0xF2, 0xF2)
OVERLAY   = RGBColor(0x34, 0x38, 0x42)
WILDCARD  = RGBColor(0x00, 0xC9, 0x82)
BLUETOOTH = RGBColor(0x2E, 0x8A, 0xF5)
ENCRYPT   = RGBColor(0xE3, 0x47, 0x49)
GATEWAY   = RGBColor(0xFF, 0xBF, 0x00)
```

---

## Gotchas

- python-docx does not support true "page background colour" — for a black cover page, use a full-width, full-height table cell with black shading as the first page, or generate the cover as a separate document and merge.
- Word's built-in heading styles carry default colours and spacing; always explicitly set `font.color.rgb` and `font.name` on each run — don't rely on style inheritance to pick up Nexon values.
- Logo in the header will repeat on every page automatically once added to the `header` section — you do not need to add it page by page.
- The thin rule beneath the header logo is applied via paragraph border XML (`w:pBdr`), not via a drawn shape — the python-docx snippet above shows the correct approach.
- Never use a text placeholder or auto-shape to "draw" the logo — only the official PNG.
