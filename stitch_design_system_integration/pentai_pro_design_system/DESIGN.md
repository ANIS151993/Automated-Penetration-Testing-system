---
name: PentAI Pro Design System
colors:
  surface: '#11131a'
  surface-dim: '#11131a'
  surface-bright: '#373940'
  surface-container-lowest: '#0b0e14'
  surface-container-low: '#191c22'
  surface-container: '#1d2026'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2eb'
  on-surface-variant: '#c2c6d5'
  inverse-surface: '#e1e2eb'
  inverse-on-surface: '#2e3037'
  outline: '#8c909e'
  outline-variant: '#424753'
  surface-tint: '#acc7ff'
  primary: '#acc7ff'
  on-primary: '#002f68'
  primary-container: '#508ff8'
  on-primary-container: '#00285b'
  inverse-primary: '#005bbf'
  secondary: '#44f5bd'
  on-secondary: '#003828'
  secondary-container: '#00d8a2'
  on-secondary-container: '#005840'
  tertiary: '#ffb873'
  on-tertiary: '#4b2800'
  tertiary-container: '#d37b02'
  on-tertiary-container: '#412200'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#acc7ff'
  on-primary-fixed: '#001a40'
  on-primary-fixed-variant: '#004492'
  secondary-fixed: '#50fec5'
  secondary-fixed-dim: '#1fe0aa'
  on-secondary-fixed: '#002116'
  on-secondary-fixed-variant: '#00513b'
  tertiary-fixed: '#ffdcbf'
  tertiary-fixed-dim: '#ffb873'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#6a3b00'
  background: '#11131a'
  on-background: '#e1e2eb'
  surface-variant: '#32353c'
  bg-primary: '#0A0B0F'
  surface-secondary: '#141620'
  surface-tertiary: '#1C1F2E'
  border-subtle: '#252836'
  border-accent: '#2F3447'
  text-primary: '#E8EAED'
  text-secondary: '#9AA0B4'
  text-tertiary: '#5C6378'
  severity-critical: '#FF3366'
  severity-high: '#FF8C42'
  severity-medium: '#FFB800'
  severity-low: '#4F8EF7'
  severity-info: '#5C6378'
typography:
  h1:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  h2:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  h3:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
  mono-code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.6'
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  gutter: 24px
  sidebar-expanded: 240px
  sidebar-collapsed: 64px
  nav-height: 56px
  padding-card: 24px
  row-dense: 40px
  row-regular: 48px
---

Design a UI design system for a professional cybersecurity product called PentAI Pro.
This is an enterprise-grade automated penetration testing platform used by security
operations teams, red team analysts, and CISOs. The user base is technically
sophisticated and expects the product to look like a serious security tool, not a
consumer app.

AESTHETIC DIRECTION: Tactical command center meets refined enterprise software.
Think Bloomberg Terminal's information density crossed with Linear's clarity,
with the operational seriousness of a SOC dashboard. This is NOT a generic SaaS
dashboard. This is NOT startup-playful. This is NOT purple-gradient-on-white.

COLOR SYSTEM:
- Primary background: deep charcoal #0A0B0F (near-black, slight blue cast)
- Secondary surface: #141620 (panels, cards)
- Tertiary surface: #1C1F2E (elevated elements, modals)
- Border color: #252836 (subtle, 1px)
- Border accent: #2F3447 (hover, focus rings)
- Primary text: #E8EAED (off-white, not pure white)
- Secondary text: #9AA0B4 (muted labels, metadata)
- Tertiary text: #5C6378 (timestamps, hints)
- Accent primary: #4F8EF7 (electric blue — interactive elements, links)
- Accent secondary: #00D9A3 (mint green — successful scans, confirmed findings)

SEVERITY COLORS (threat levels — these are semantic, not decorative):
- Critical: #FF3366 (saturated red, used sparingly)
- High: #FF8C42 (burnt orange)
- Medium: #FFB800 (amber)
- Low: #4F8EF7 (same as accent — de-emphasized)
- Info: #5C6378 (gray)

TYPOGRAPHY:
- Display and headings: "Space Grotesk" (700 weight for H1, 600 for H2-H3)
- Body and UI: "Inter" (400 regular, 500 medium, 600 semibold)
- Monospace (terminal output, code, IP addresses, CVE IDs, hashes): "JetBrains Mono"
- Do NOT use: Roboto, Arial, system-ui, or any generic sans-serif

SPACING AND GRID:
- Base unit: 4px. All spacing is a multiple of 4.
- Page grid: 12-column with 24px gutters
- Sidebar width: 240px collapsed to 64px
- Top nav height: 56px
- Card padding: 24px
- Dense table rows: 40px. Regular rows: 48px.

COMPONENTS (establish these as reusable):
- Buttons: 8px border-radius, 40px height for primary, 32px for secondary.
  Primary uses accent blue with subtle gradient sheen.
  Secondary is ghost-style with 1px border.
- Inputs: 40px height, 6px border-radius, dark fill, border lights up on focus.
- Cards: 12px border-radius, 1px border, subtle inner shadow for depth.
- Badges: 20px height, 4px border-radius, uppercase 11px letter-spaced text.
- Tooltips: Dark surface, small arrow, 12px padding, appear after 500ms hover.

MOTION PRINCIPLES:
- Transitions: 150ms ease-out for hovers, 300ms ease-in-out for layout changes.
- Loading states: Skeleton shimmer in #1C1F2E to #252836.
- Data updates: Subtle fade-in, no bounce or spring.
- Critical alerts: Single pulse animation on appearance, then static.

ICONOGRAPHY:
- Use Lucide icons exclusively. 16px in buttons/inline, 20px in nav, 24px in headers.
- Never use emoji in the UI chrome (except for severity indicators in reports).
- Status dots are solid 8px circles with a 2px ring in the matching color at 30% opacity.

ACCESSIBILITY:
- Minimum contrast ratio: 4.5:1 for body text, 3:1 for large text.
- All interactive elements have visible focus rings (#4F8EF7 at 2px, 2px offset).
- Do not rely on color alone to convey severity — pair with icons and text labels.

BRAND VOICE (microcopy):
- Confident, precise, minimal. "3 findings require your review." Not "You have 3 new findings!"
- Never exclamation marks except in error states.
- Use technical terms accurately. This audience knows the difference between a
  vulnerability and an exploit.

Generate a design system page showing: color swatches with hex codes, typography
scale with live examples, button states (default/hover/active/disabled), input
states, card variants, badge examples for each severity level, and a small
icon gallery. Label everything clearly.