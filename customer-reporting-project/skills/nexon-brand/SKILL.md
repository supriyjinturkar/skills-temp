---
name: nexon-brand
description: Use when creating or styling any Nexon-branded output - HTML pages,
  Word documents, PowerPoint presentations, emails, dashboards, or reports.
  Apply this skill whenever branding, design consistency, colours, logos, fonts,
  or layout are relevant to the task.
---

# Nexon Brand Skill

This skill ensures every artefact you produce is on-brand for Nexon. Always apply it when generating HTML, PPTX, or DOCX output.

## Logo

The official logo is a **white wordmark on a black background** PNG. It lives at:
```
/skills/nexon-brand/assets/nexon-logo-black-bg.png
```

> Note: 
- For HTML reports, html template already have image element with src as logo's base64. So, use it directly.
- For PPT reports, use the nexon-logo-black-bg.png. Before using it, make sure the png image file is not corrupted, doesnt have incorrect headers, etc.

**Rules (strict):**
- Place the logo on every page/slide - no exceptions.
- Never recreate, type, or approximate the wordmark. Never stretch, rotate, or add effects.
- Minimum size: 100px wide. Clear space = height of the "x" on all sides.
- Never place on secondary palette colours (Bluetooth blue, Encrypt red, Gateway yellow, Wildcard green).
- HTML: embed as a Base64 data URI in the fixed black header, and repeat at `opacity: 0.35` in the footer.
- PPTX: top-left corner of every slide.
- DOCX: left-aligned in the page header above a thin black rule.

## Colour Palette

### Primary (unlimited use)
| Name | HEX | CSS Token |
|------|-----|-----------|
| Retina | `#000000` | `--nexon-retina` |
| Cloud | `#ffffff` | `--nexon-cloud` |
| Satellite | `#f7f2f2` | `--nexon-satellite` |
| Overlay | `#343842` | `--nexon-overlay` |

### Secondary (max 20% per module, one at a time)
| Name | HEX | CSS Token |
|------|-----|-----------|
| Wildcard | `#00c982` | `--nexon-wildcard` |
| Bluetooth | `#2e8af5` | `--nexon-bluetooth` |
| Encrypt | `#e34749` | `--nexon-encrypt` |
| Gateway | `#ffbf00` | `--nexon-gateway` |

**Key rules:**
- CTA buttons are always Wildcard green (`#00c982`).
- One secondary colour per design module - never mix two secondaries.
- Secondary colours only appear alongside primary colours.
- Never use Gateway yellow as a logo background.

### Status / RAG
- Green (healthy): `#00c982` - Amber (warning): `#ffbf00` - Red (critical): `#e34749` - Blue (info): `#2e8af5`

## Typography

| Context | Font | Fallbacks |
|---------|------|-----------|
| Web (all) | Inter (Google Fonts) | Helvetica Neue, Arial |
| PPTX / DOCX headings | Arial Bold | Helvetica Neue Bold |
| PPTX / DOCX body | Arial | Helvetica Neue |

- Italics for quotations only.
- Text colour from primary palette - never secondary colours for body text.

## Iconography

- **No emoji** in any Nexon artefact - ever.
- Use monotone inline SVG, Lucide-style.
- Stroke: `stroke-width="1.75"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, `currentColor`.
- Minimum size: 14px web / 34px print.

## HTML Output

1. Import Inter from Google Fonts.
2. Set CSS custom properties from the palette.
3. Fixed black header (64px) with logo left-aligned, embedded as Base64 data URI.
4. Body background: `var(--nexon-satellite)`.
5. Footer: logo at `opacity: 0.35`, black background.
6. For report-style HTML, start from `assets/html-template.html` instead of a blank page.
7. Treat `assets/html-template.html` as the shared report shell:
   - keep the header, hero, sticky tab bar, page width, footer treatment, and component classes
   - replace tabs, panels, metrics, charts, tables, commentary, and appendix notes to match the active report
   - preserve the typography, spacing rhythm, and colour system even when section names or data sources change
8. If a report does not need a module shown in the template, remove the whole module cleanly rather than restyling the page into a different visual language.

Full HTML boilerplate -> see `assets/html-template.html`.

## PPTX Output

| Slide type | Background | Logo position | Heading colour |
|------------|------------|---------------|----------------|
| Cover | `#000000` | Top-left | White |
| Content | `#f7f2f2` or white | Top-left | Black |
| Section divider | `#000000` | Top-left | White |

- Accent line on cover/divider slides: Wildcard green.
- Photos: apply Overlay (`#343842`) at multiply 60% opacity.
- Max one secondary colour per slide.

Python-pptx colour constants -> see `assets/pptx-guide.md`.

## DOCX Output

| Style | Font | Size | Colour |
|-------|------|------|--------|
| Heading 1 | Arial Bold | 32pt | `#000000` |
| Heading 2 | Arial Bold | 24pt | `#000000` |
| Heading 3 | Arial Bold | 18pt | `#000000` |
| Body Text | Arial | 11pt | `#343842` |
| CTA | Arial Bold | 11pt | `#00c982` |

- Page margins: 2.54 cm (1 inch) all sides.
- Cover page: black background, white logo top-left, Wildcard divider line.

Full style reference -> see `assets/word-guide.md`.

## Pre-Delivery Checklist

Before finalising any branded output verify:
- [ ] Official PNG logo used and placed on every page/slide
- [ ] Colours match official palette - no off-brand values
- [ ] CTA buttons are Wildcard green (`#00c982`)
- [ ] Only one secondary colour per module, <=20% area
- [ ] Font is Inter (web) or Arial (Word/PPT)
- [ ] No emoji - all icons are monotone inline SVG
- [ ] Active voice, short sentences, second-person "you"
- [ ] HTML reports keep the shared template shell unless there is an explicit reason to diverge

## Reference Files

- `assets/html-template.html` - Ready-to-use branded HTML report template
- `assets/pptx-guide.md` - PPTX theme slots, python-pptx colour constants, slide layout rules
- `assets/word-guide.md` - DOCX style map, header/footer setup, cover page spec
- `references/brand-guide.md` - Full brand guide (voice & tone, solution pillars, co-branding rules)
