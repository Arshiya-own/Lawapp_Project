# 02 — Frontend Specification

**Document:** Frontend / UI Specification
**Version:** 1.0
**Audience:** Engineers implementing the Mini-JuriNex user interface

---

## 1. Purpose

This document defines the pages, components, states, routing, and UX flows for the Mini-JuriNex frontend. Visual design (exact colors, fonts, spacing) is not prescribed — use Tailwind defaults sensibly. Structure and behavior are binding.

---

## 2. Tech Stack (Binding)

| Concern | Choice |
|---|---|
| Framework | React 18 |
| Language | TypeScript (strict mode on) |
| Build tool | Vite |
| Styling | Tailwind CSS v3 |
| Routing | React Router v6 |
| Server state | @tanstack/react-query v5 |
| Auth state | React Context |
| HTTP client | fetch or axios (implementer's choice) |
| Forms | react-hook-form (if forms beyond upload are needed) |

---

## 3. Project Structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                  ← router + providers
│   ├── api/
│   │   ├── client.ts            ← fetch wrapper with auth header
│   │   ├── cases.ts             ← case-related API calls
│   │   └── auth.ts              ← auth-related API calls
│   ├── auth/
│   │   ├── AuthContext.tsx
│   │   └── useAuth.ts
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── UploadPage.tsx
│   │   └── ResultsPage.tsx
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── CaseMetadataCard.tsx
│   │   ├── DimensionCard.tsx
│   │   ├── JudgmentItem.tsx
│   │   └── JudgmentSnippetModal.tsx
│   └── types/
│       └── api.ts               ← TypeScript types matching API contracts
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

Deviations from this structure should be minor and justified in `DEVIATIONS.md`.

---

## 4. Routing

| Path | Page | Auth required |
|---|---|---|
| `/login` | LoginPage | No |
| `/` | UploadPage | Yes |
| `/cases/:caseId` | ResultsPage | Yes |

Unauthenticated access to protected routes redirects to `/login`.
After successful login, redirect to `/` (or `/cases/:caseId` if `returnTo` query param was set).

---

## 5. Pages

### 5.1 Login Page (`/login`)

**Purpose:** Let the user sign in with Google.

**Layout:**
- Centered card on neutral background
- JuriNex logo/wordmark (text is fine)
- Tagline: "Find precedents, faster."
- "Sign in with Google" button — Google brand guidelines allowed but not required
- Small footer: "By signing in, you agree to our terms."

**Behavior:**
- Clicking the button initiates the OAuth flow (redirect or popup — implementer's choice)
- On successful auth, redirect to `/`
- On auth failure, show inline error: `"Sign-in failed. Please try again."`

**States:**
- `idle` — button enabled
- `authenticating` — button shows spinner, disabled
- `error` — button re-enabled, error message shown above button

---

### 5.2 Upload Page (`/`)

**Purpose:** Let the user upload a case PDF and see the extracted metadata.

**Layout:**
- Header (see § 6.1) at top
- Main area: large drop zone + file picker button
- Hint text: "Drop a case PDF or click to browse. Max 20 MB."
- Below the drop zone: list of the user's previously uploaded cases (most recent first), each linking to `/cases/:caseId`. If the user has no cases yet, show: *"No cases yet. Upload your first case above."*

**Behavior — upload flow:**

```
  idle  ─────(drop/select)────►  validating
                                      │
                                      ▼ (valid)
                                  uploading
                                      │
                                      ▼ (200 from API)
                                  processing  ◄── poll GET /cases/:id
                                      │              until status = "processed"
                                      ▼
                                  success → navigate to /cases/:caseId
```

**States:**
- `idle` — drop zone active
- `validating` — file being type-checked client-side; show spinner on drop zone
- `uploading` — show progress bar (if supported) or indeterminate spinner
- `processing` — show "Extracting text and metadata… (this takes 10–30 seconds)" with animated dots
- `error` — show error message, reset to `idle` after user dismisses

**Validation rules (client-side):**
- File type: `application/pdf` only. Error: `"Only PDF files are accepted."`
- File size: ≤ 20 MB. Error: `"File too large. Maximum 20 MB."`

**Errors to handle:**
- 401 → redirect to `/login`
- 413 → show size error
- 415 → show type error
- 422 → show `"We couldn't extract text from this PDF. It may be corrupted or image-only with illegible scans."`
- 5xx → show `"Something went wrong on our side. Please try again."`

---

### 5.3 Results Page (`/cases/:caseId`)

**Purpose:** Show case metadata + dimensional queries + ranked precedents.

**Layout:**

```
 ┌──────────────────────────────────────────────────────────────┐
 │  Header                                                       │
 ├──────────────────────────────────────────────────────────────┤
 │                                                              │
 │   ┌─── CaseMetadataCard ──────────────────────────────────┐  │
 │   │  Parties: Rahul Kasat vs. State of Maharashtra       │  │
 │   │  Court: Supreme Court                                │  │
 │   │  Sections: IPC 120B, IPC 302                         │  │
 │   │  Synopsis: SLP (Criminal) filed challenging …        │  │
 │   └──────────────────────────────────────────────────────┘  │
 │                                                              │
 │   [ Find Precedents ] ← button if not yet retrieved         │
 │                                                              │
 │   ┌─── DimensionCard 1 ───────────────────────────────────┐  │
 │   │  Dimension 1                                          │  │
 │   │  Query: "Non-compliance with Section 65B certificate" │  │
 │   │  Rationale: …                                         │  │
 │   │  Precedents:                                          │  │
 │   │    • JudgmentItem 1 (SC, 2019)  [View snippet]       │  │
 │   │    • JudgmentItem 2 (Bombay HC, 2021)  [View]        │  │
 │   │    • …                                                │  │
 │   └──────────────────────────────────────────────────────┘  │
 │                                                              │
 │   [ DimensionCard 2 … ]                                      │
 │   [ DimensionCard 3 … ]                                      │
 │                                                              │
 └──────────────────────────────────────────────────────────────┘
```

**Behavior:**
- On page mount: fetch case metadata via `GET /cases/:caseId`.
- If case has no dimensions/retrieval yet → show `[ Find Precedents ]` button.
- Click → call `POST /cases/:caseId/dimensions`, then `POST /cases/:caseId/retrieve`.
- Results stream in per-dimension if possible; otherwise show aggregate loading state.

**States per DimensionCard:**
- `loading` — "Searching…" with spinner
- `success` — shows up to 5 ranked `JudgmentItem`s
- `empty` — **verbatim text: `"No precedents found for this dimension."`**
- `error` — "Couldn't retrieve results for this dimension. [Retry]"

**JudgmentItem click:**
Opens `JudgmentSnippetModal` showing:
- Full citation
- Court, date
- The exact retrieved chunk text
- Similarity score (rounded to 3 decimals, e.g., `0.842`)
- "Close" button

---

## 6. Components

### 6.1 Header

- Left: JuriNex wordmark linking to `/`
- Right: user avatar (from OAuth) + user email + "Sign out" button
- Height: 64 px
- Sticky top

### 6.2 CaseMetadataCard

Props:
```ts
interface CaseMetadataCardProps {
  parties: string;
  court: string;
  sections: string[];
  synopsis: string;
  jurisdiction: string;  // e.g. "Criminal", "Civil"
}
```

Renders:
- Title: `{parties}`
- Row: `Court: {court}`
- Row: `Sections: {sections.join(", ")}`
- Row: `Jurisdiction: {jurisdiction}`
- Row: `Synopsis: {synopsis}` (truncate to 3 lines with "Show more" expander)

### 6.3 DimensionCard

Props:
```ts
interface DimensionCardProps {
  dimension: number;       // 1, 2, or 3
  query: string;
  rationale: string;
  judgments: RankedJudgment[];  // type from backend spec
  status: 'loading' | 'success' | 'empty' | 'error';
  onRetry?: () => void;
}
```

### 6.4 JudgmentItem

Props:
```ts
interface JudgmentItemProps {
  judgmentId: string;
  citation: string;
  court: string;
  date: string;            // ISO date
  similarityScore: number;
  snippet: string;
  onViewSnippet: () => void;
}
```

Visual:
- Row layout
- Left: citation (bold) + court + date (small, muted)
- Middle: first 140 chars of snippet (ellipsis)
- Right: similarity score pill + "View snippet" button

### 6.5 JudgmentSnippetModal

Full-screen on mobile, centered modal on desktop.
Closes on ESC key, backdrop click, or Close button.

---

## 7. Accessibility

- All interactive elements keyboard-navigable.
- Focus rings visible (do not suppress with `outline: none`).
- Form controls have associated labels.
- Modal traps focus when open.
- Color contrast ≥ WCAG AA (4.5:1 for text).

---

## 8. Responsive Behavior

- Breakpoints: Tailwind defaults (`sm`, `md`, `lg`, `xl`).
- Mobile (`< sm`): single-column layout, DimensionCard stacks, modal is full-screen.
- Desktop (`≥ md`): max content width 1024 px, centered.

---

## 9. Empty / Error / Loading — Required Across All Pages

Every data-fetching component must handle all four states explicitly:

| State | Requirement |
|---|---|
| `loading` | Show a spinner or skeleton. Do not show stale data. |
| `empty` | Show a message explaining no data is available. Use verbatim text where specified. |
| `error` | Show a clear error message with a retry action if retry is safe. |
| `success` | Render the data. |

No silent "nothing happens" states are acceptable.

---

## 10. Forbidden Patterns

- Putting API keys in frontend code
- Storing auth tokens in `localStorage` (use HTTP-only cookies or in-memory)
- Calling Gemini directly from the frontend
- Uploading PDFs to anything other than the backend API
- Using `dangerouslySetInnerHTML` with API-returned content

---

## 11. Summary of Binding Behaviors

| Item | Rule |
|---|---|
| Routes | Exactly 3: `/login`, `/`, `/cases/:caseId` |
| OAuth | Redirect to `/login` on 401 |
| File validation | Client checks MIME + size before upload |
| Empty state text | Exactly `"No precedents found for this dimension."` |
| Similarity score display | 3 decimal places |
| Modal close | ESC, backdrop, or explicit Close |
| Max dimensions | 3 cards |
| Max judgments per dimension | 5 items |
