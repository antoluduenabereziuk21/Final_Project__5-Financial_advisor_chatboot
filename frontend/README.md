# Financial Advisor Chatbot — Frontend

React 19 + Vite web client for the financial advisor chatbot.

## Stack

- Vite
- React 19
- TypeScript
- Tailwind CSS v4 (CSS-first tokens in `src/index.css`)
- shadcn/ui primitives under `src/presentation/components`

Target architecture also includes React Router, Redux Toolkit, Inversify, and Vitest when those layers are introduced. See docs for current vs target status.

## Scripts

```bash
pnpm install
pnpm dev
pnpm build
pnpm lint
pnpm preview
```

## Documentation

Read these before changing architecture or generating features:

| Document | Purpose |
| -------- | ------- |
| [docs/CURSOR_PROJECT.md](./docs/CURSOR_PROJECT.md) | Product and stack overview |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Clean Architecture and folder layout |
| [docs/DESIGN_SYSTEM.md](./docs/DESIGN_SYSTEM.md) | Tailwind tokens and shadcn rules |
| [docs/DEPENDENCY_INJECTION.md](./docs/DEPENDENCY_INJECTION.md) | Inversify wiring rules |
| [docs/TEST_GUIDELINES.md](./docs/TEST_GUIDELINES.md) | Vitest / Testing Library conventions |

## Conventions (short)

- Every React component uses Container / Presentational / Config / `index.ts`.
- UI copies live in `*Config.ts`.
- Prefer existing shadcn primitives and semantic Tailwind tokens.
- Domain stays free of React, HTTP, and UI imports.
- UI and pages live under `src/presentation/` (`components/`, `pages/`).
- Static assets live under `public/`.
