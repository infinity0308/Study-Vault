# UI / UX Specification

## Design direction
Build a calm, polished study workspace, not a generic admin template. Use warm off-white backgrounds, white surfaces, dark readable text, restrained indigo/violet accents, soft borders, generous spacing, and clear status colors. Avoid heavy glassmorphism, huge gradients, and unnecessary animation.

## Global layout
**Desktop:** 240–260 px sidebar, compact top bar, clear page title, and a readable content width.

**Mobile:** collapsible drawer or bottom navigation; upload, question composer, answer, and source cards must fit narrow screens without horizontal scrolling.

Navigation: Overview, My Library, Ask a Question, Settings.

## Pages
### Overview
- Greeting and concise product explanation.
- Primary CTA: Ask a question.
- Secondary CTA: Upload notes.
- Recent documents and actual processing statuses.
- Useful empty state for new accounts.

### My Library
- Search, subject filter, upload button.
- Drag/drop zone plus browse button.
- Document cards with PDF icon, title, subject, size, upload date, status, and actions.
- Failed state with safe error and Retry action.
- Delete confirmation explaining that indexed chunks are removed too.

### Ask a Question
- Large, accessible question input and example questions.
- Optional document scope selector.
- Loading, timeout, provider-error, and retry states.
- Answer panel with readable typography.
- Source cards showing document title, page, and excerpt.
- Honest insufficient-context state; no fake citations.
- Preserve the question after an error.

### Authentication and settings
Use labeled fields, validation, password visibility, loading states, profile basics, privacy explanation, and sign out.

## Components
`AppShell`, `SidebarNavigation`, `TopBar`, `PageHeader`, `DocumentCard`, `StatusBadge`, `UploadDropzone`, `SearchInput`, `EmptyState`, `ErrorState`, `LoadingSkeleton`, `QuestionComposer`, `AnswerPanel`, `SourceCard`, `ConfirmDialog`, `Toast`.

## Starting design tokens
```css
:root {
  --color-bg: #f7f7fb;
  --color-surface: #ffffff;
  --color-text: #1c1c2b;
  --color-muted: #6c6c80;
  --color-border: #e7e7f0;
  --color-primary: #5b50d6;
  --color-primary-hover: #493fbd;
  --color-success: #1c8054;
  --color-warning: #9a6700;
  --color-danger: #b42318;
  --radius-card: 16px;
  --radius-control: 10px;
}
```

Check contrast and focus visibility. Use semantic HTML, keyboard-accessible controls, reduced-motion support, and real loading/error states. Do not display fake ingestion percentages.
