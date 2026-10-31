# CLAUDE.md - <app-name> (React + TypeScript web app)

## Commands
```bash
npm install
npm start            # dev server
npm test             # unit tests
npm run lint && npm run typecheck
```

## Conventions
- TypeScript strict; no `any` without a comment explaining why.
- Use the design system's components first; custom styling via CSS Modules and design tokens (no inline styles, no hardcoded colours, relative units).
- Server state through one shared HTTP client with the auth interceptor; never create ad-hoc clients in components.
- Global state in a small store; local state stays in components.
- Every new component: loading, empty, error and populated states, plus keyboard and screen-reader behaviour.

## Testing
- Test behaviour through the DOM (Testing Library), not implementation details.
- Mock the network at the HTTP boundary.

## Guardrails for Claude
- Do not edit generated files or the shell/host application this app plugs into.
- Show before/after screenshots or describe the visible change when touching UI.
