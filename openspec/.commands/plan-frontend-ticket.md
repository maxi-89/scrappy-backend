# Role

You are an expert frontend architect with deep experience in Next.js App Router applications with TypeScript and Tailwind CSS, applying component-driven architecture and clean separation between data fetching and UI.

# Arguments

`$ARGUMENTS` — ticket identifier, ticket ID, or keywords. If it refers to a local file, read it directly without using MCP.

# Goal

Produce a step-by-step frontend implementation plan for a ticket that is detailed enough for a developer to work end-to-end autonomously.

# Process and rules

1. Adopt the role defined in `openspec/.agents/frontend-developer.md`
2. Fetch the ticket using the project management MCP. If `$ARGUMENTS` refers to a local file, read it directly
3. Propose a step-by-step plan for the frontend, applying the standards in `openspec/specs`
4. Ensure the plan is complete enough that the developer needs no further clarification
5. Do not write implementation code — provide the plan only
6. If asked to start implementing, first move to the feature branch (Step 0) and follow `/develop-frontend.md`

# Output format

Save the plan as a markdown document at `openspec/changes/[ticket-id]_frontend.md`.

Use the following template:

---

## Template

### 1. Header
- Title: `# Frontend Implementation Plan: [TICKET-ID] — [Feature Name]`

### 2. Overview
- Brief description of the feature
- Next.js App Router principles applied (Server vs Client Components)
- State management approach

### 3. Architecture Context
- Pages and routes involved (`app/` paths)
- Components to create or modify
- API service modules needed (`lib/api/`)
- Custom hooks needed (`hooks/`)
- TypeScript types to define (`types/`)

### 4. Implementation Steps

#### Step 0: Create Feature Branch
- **Action**: Create and switch to the feature branch
- **Branch name**: `feature/[ticket-id]-frontend`
- **Steps**:
  1. Ensure you are on the latest `main` or `develop`
  2. `git pull origin [base-branch]`
  3. `git checkout -b feature/[ticket-id]-frontend`
- **Note**: This must be the FIRST step before any code changes

#### Step 1: Define TypeScript Types
- **File**: `types/[feature].ts`
- **Action**: Define interfaces for the feature's data structures and API responses

#### Step 2: API Service Module
- **File**: `lib/api/[feature]Api.ts`
- **Action**: Implement service functions that call the backend API
- **Notes**: Use `NEXT_PUBLIC_API_URL` for client-side, `API_BASE_URL` for server-side. Always check `res.ok` and throw typed errors

#### Step 3: Page Component (Server Component)
- **File**: `app/[route]/page.tsx`
- **Action**: Async Server Component — fetch data directly, pass to child components
- **Notes**: No `'use client'`. Use `next: { revalidate }` or `cache: 'no-store'` as appropriate

#### Step 4: Feature Components
- **Files**: `components/[feature]/[ComponentName].tsx`
- **Action**: Build the UI components needed
- **Server vs Client split**: Identify which components need interactivity (`'use client'`) and which can stay as Server Components
- **Styling**: Tailwind utility classes only. Use `cn()` for conditional classes

#### Step 5: Custom Hook (if needed)
- **File**: `hooks/use[Feature].ts`
- **Action**: Encapsulate client-side state, data fetching, or effects
- **Notes**: Only for Client Component logic

#### Step 6: Loading and Error States
- **Files**: `app/[route]/loading.tsx`, `app/[route]/error.tsx`
- **Action**: Define loading skeleton and error boundary for the route

#### Step 7: Unit Tests
- **Files**: `__tests__/components/[ComponentName].test.tsx`, `__tests__/lib/api/[feature]Api.test.ts`
- **Cases to cover**:
  - Renders correctly with valid data
  - Handles loading state
  - Handles error state
  - User interactions (for Client Components)
  - API service: successful response, error response

#### Step 8: E2E Tests (Playwright)
- **File**: `e2e/[feature].spec.ts`
- **Cases to cover**:
  - Happy path (full user flow)
  - Validation errors (if forms involved)
  - Empty states

#### Step N: Update Documentation
- **Action**: Review all changes and update affected docs
  - API contract changes → `openspec/specs/api-spec.yml`
  - New patterns or conventions → `openspec/specs/frontend-standards.mdc`
- Follow `openspec/specs/documentation-standards.mdc`
- **This step is MANDATORY** — do not skip it

---

### 5. Implementation Order
Numbered list from Step 0 (branch) to documentation update (always last)

### 6. Server vs Client Component Decision
For each component in the plan, explicitly state:
- **Server Component**: reason (data fetching, no interactivity)
- **Client Component**: reason (event handlers, hooks, browser API)

### 7. Testing Checklist
- [ ] All components render correctly with valid data
- [ ] Loading and error states handled
- [ ] User interactions tested (Client Components)
- [ ] API service functions tested
- [ ] E2E happy path covered
- [ ] Accessibility: semantic HTML, correct roles

### 8. UI/UX Considerations
- Tailwind classes used (no inline styles)
- Responsive design breakpoints needed
- Loading skeletons or spinners
- Empty state UI

### 9. Dependencies
- New npm packages required (if any) with justification
- Do not add packages if existing Tailwind or Next.js capabilities suffice

### 10. Notes
- Business rules and constraints
- Assumptions made
- Environment variables required
- Anything the developer must know before starting

### 11. Implementation Verification
- [ ] Server/Client Component split is optimal
- [ ] All API calls go through `lib/api/` service modules
- [ ] TypeScript strict — no `any`
- [ ] Tailwind only — no inline styles
- [ ] All tests pass
- [ ] Documentation updated
