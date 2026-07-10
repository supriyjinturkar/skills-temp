# Nexon PPTX Guide

Reference for building on-brand PowerPoint presentations — manually or via python-pptx.

---

## Slide Types & Layouts

| Slide type | Background | Logo | H1/H2 colour | Accent |
|------------|-----------|------|--------------|--------|
| **Cover** | `#000000` (Retina) | Top-left, white | White `#ffffff` | Wildcard green line |
| **Content** | `#f7f2f2` (Satellite) or `#ffffff` | Top-left | Black `#000000` | — |
| **Section divider** | `#000000` (Retina) | Top-left | White `#ffffff` | Wildcard green |

### Layout Rules
- CTA text is always Wildcard green (`#00c982`).
- Max one secondary colour per slide.
- Photos: apply Overlay (`#343842`) at Multiply 60% opacity.
- Logo minimum 100px wide. Clear space = height of "x" glyph on all sides.
- Never place logo on a secondary-colour background.

---

## Theme Colour Slots

Set these in the PowerPoint Theme Editor (Design → Colors → Customize):

| Slot | Colour | HEX |
|------|--------|-----|
| Dark 1 / Text | Retina | `#000000` |
| Light 1 / Background | Cloud | `#ffffff` |
| Accent 1 | Wildcard | `#00c982` |
| Accent 2 | Bluetooth | `#2e8af5` |
| Accent 3 | Gateway | `#ffbf00` |
| Accent 4 | Encrypt | `#e34749` |

---

## python-pptx Colour Constants

```python
from pptx.dml.color import RGBColor

# Primary palette
RETINA    = RGBColor(0x00, 0x00, 0x00)   # #000000
CLOUD     = RGBColor(0xFF, 0xFF, 0xFF)   # #ffffff
SATELLITE = RGBColor(0xF7, 0xF2, 0xF2)  # #f7f2f2
OVERLAY   = RGBColor(0x34, 0x38, 0x42)  # #343842

# Secondary palette
WILDCARD  = RGBColor(0x00, 0xC9, 0x82)  # #00c982 — CTAs & accents
BLUETOOTH = RGBColor(0x2E, 0x8A, 0xF5)  # #2e8af5 — info
ENCRYPT   = RGBColor(0xE3, 0x47, 0x49)  # #e34749 — critical/error
GATEWAY   = RGBColor(0xFF, 0xBF, 0x00)  # #ffbf00 — warning
```

### Typical python-pptx Pattern

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()
slide_width  = prs.slide_width   # default 10 in
slide_height = prs.slide_height  # default 7.5 in

# ── Cover slide ──────────────────────────────────────────────────────
blank_layout = prs.slide_layouts[6]   # blank
slide = prs.slides.add_slide(blank_layout)

# Black background
background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RETINA

# Logo (top-left) — replace path with actual logo file
logo = slide.shapes.add_picture(
    'nexon-logo-black-bg.png',
    left=Inches(0.4), top=Inches(0.3),
    width=Inches(1.5)   # ~144px at 96dpi; ensures ≥100px
)

# Wildcard accent line beneath logo
line = slide.shapes.add_connector(
    1,   # straight connector
    left=Inches(0.4), top=Inches(0.75),
    x_end=Inches(9.6), y_end=Inches(0.75)
)
line.line.color.rgb = WILDCARD
line.line.width = Pt(2)

# H1 title
txBox = slide.shapes.add_textbox(Inches(0.4), Inches(2.5), Inches(9), Inches(2))
tf = txBox.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = 'Presentation Title'
p.font.bold  = True
p.font.size  = Pt(40)
p.font.color.rgb = CLOUD

# Save
prs.save('output.pptx')
```

---

## Adding Logo to Every Slide (Loop Pattern)

```python
for slide in prs.slides:
    slide.shapes.add_picture(
        'nexon-logo-black-bg.png',
        left=Inches(0.25), top=Inches(0.15),
        width=Inches(1.2)
    )
```

---

## Typography (PPTX)

| Element | Font | Size | Weight | Colour |
|---------|------|------|--------|--------|
| H1 (cover) | Arial | 40pt | Bold | Cloud white |
| H1 (content) | Arial | 32pt | Bold | Retina black |
| H2 | Arial | 24pt | Bold | Retina black |
| Body | Arial | 14pt | Regular | Overlay `#343842` |
| Caption | Arial | 10pt | Regular | Overlay |
| CTA label | Arial | 14pt | Bold | Wildcard `#00c982` |

---

## Gotchas

- python-pptx does not auto-embed the theme palette — set RGBColor values explicitly on each shape; don't rely on theme slot inheritance.
- Logo PNG must be the official white-on-black asset. Never approximate with a text shape or recoloured image.
- Gateway yellow (`#ffbf00`) looks fine on black but must never be the logo background — avoid using it as a full-bleed slide background.
- Multiply blend mode for photo overlays is not supported natively in python-pptx; add it manually in PowerPoint after generation, or use a semi-transparent filled rectangle (`OVERLAY` at 60% transparency) over the image as a close approximation.
