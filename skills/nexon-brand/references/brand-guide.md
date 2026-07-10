# Nexon Brand Guide — Full Reference

Source of truth for the Nexon brand system. The SKILL.md summarises the essentials; read this file for edge cases, extended rules, and voice/tone guidelines.

---

## Colour Palette (Extended)

### Badge Tints (web only)
```css
.badge-green  { background: rgba(0, 201, 130, 0.15); color: #00875a; }
.badge-yellow { background: rgba(255, 191, 0, 0.15);  color: #946c00; }
.badge-red    { background: rgba(227, 71, 74, 0.15);  color: #c41e3a; }
.badge-blue   { background: rgba(46, 138, 245, 0.15); color: #0066cc; }
.badge-gray   { background: rgba(0, 0, 0, 0.08);      color: #666;    }
```

### Icon Container (web)
```css
.icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  background: rgba(0, 201, 130, 0.12);
  display: flex; align-items: center; justify-content: center;
  color: var(--nexon-overlay);
}
```

---

## Web CSS Patterns

### Full Base Reset + Variables
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --nexon-retina:    #000000;
  --nexon-cloud:     #ffffff;
  --nexon-satellite: #f7f2f2;
  --nexon-overlay:   #343842;
  --nexon-wildcard:  #00c982;
  --nexon-bluetooth: #2e8af5;
  --nexon-encrypt:   #e34749;
  --nexon-gateway:   #ffbf00;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  background: var(--nexon-satellite);
  color: var(--nexon-retina);
}
```

### Header
```css
.header {
  background: var(--nexon-retina);
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
}
```

### Card
```css
.card {
  background: var(--nexon-cloud);
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 20px;
}
.card:hover {
  border-color: var(--nexon-retina);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
```

### Hero Section
```css
.hero {
  background: var(--nexon-retina);
  border-radius: 16px;
  padding: 32px;
  color: var(--nexon-cloud);
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  top: -50%; right: -10%;
  width: 300px; height: 300px;
  background: linear-gradient(135deg, var(--nexon-wildcard) 0%, transparent 60%);
  border-radius: 50%;
  opacity: 0.1;
}
```

### Tables
```css
th {
  text-align: left; padding: 12px 16px;
  font-size: 12px; font-weight: 600;
  color: var(--nexon-overlay);
  text-transform: uppercase; letter-spacing: 0.5px;
  background: var(--nexon-satellite);
  border-bottom: 1px solid #e5e5e5;
}
td { padding: 14px 16px; font-size: 14px; border-bottom: 1px solid #f0f0f0; }
tr:hover { background: var(--nexon-satellite); }
```

### CTA Button
```css
.btn-primary {
  padding: 12px 24px;
  background: var(--nexon-wildcard);
  color: var(--nexon-cloud);
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
}
```

---

## Brand Voice & Tone

### Brand Pillars
| Pillar | We are… | Tone |
|--------|---------|------|
| Expert | Knowledgeable | Confident, clear, declarative |
| Trusted | Proven partner | Reassuring, action-oriented |
| Collaborative | Partner/people-first | Direct, approachable, "you/we" |
| Optimistic | Forward-looking | Inspiring, positive |

### Writing Style — Do
- Short, declarative sentences. "Your tech should be the great enabler."
- Second-person "you" and inclusive "we/our."
- Active voice. Em dashes for rhythm.
- Specific, benefit-led statements with proof points.

### Writing Style — Don't
- Jargon dumps or passive voice.
- Caveats / qualifiers ("may", "could potentially").
- Alliteration-heavy enthusiasm.
- Cheesy superlatives.
- Mention solution pillar internal names externally.

### Positioning Statement
> Nexon is a digital consulting and managed services partner that helps mid-market and government organisations to drive business productivity, continuity and change.

### Solution Pillars (external-facing only)
- **Nexon Amplify** — unlocking the full power of Microsoft
- **Nexon Xperience** — uniting CX, EX and ESM
- **Nexon Guardian** — safeguarding security and compliance
- **Nexon Accelerate** — turning cloud power into business momentum

---

## Logo — Extended Rules

- **Co-branding:** Separate partner logos from Nexon logo with a 2pt vertical line divider.
- **Forbidden backgrounds:** Gateway yellow, any secondary colour.
- **Approved backgrounds:** Retina black, Cloud white, Satellite off-white.
- Minimum digital width: 100px. Clear space = height of the "x" glyph on all four sides.

---

## PPTX Theme Colour Slots

| Slot | Value |
|------|-------|
| Dark 1 / Text | `#000000` (Retina) |
| Light 1 / Background | `#ffffff` (Cloud) |
| Accent 1 | `#00c982` (Wildcard) |
| Accent 2 | `#2e8af5` (Bluetooth) |
| Accent 3 | `#ffbf00` (Gateway) |
| Accent 4 | `#e34749` (Encrypt) |
