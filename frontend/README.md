# NetVault Frontend

React + TypeScript SPA, built with [Vite](https://vitejs.dev/). Talks to the Django backend
over a relative `/api/v1` path — in production nginx reverse-proxies both frontend and API
under one origin (see `install.sh`); in dev, Vite's dev server runs standalone against the
backend on `:8000`.

## Available Scripts

### `npm run dev`

Starts the Vite dev server on **http://localhost:3000** (see `vite.config.ts`) with HMR.

### `npm run build`

Builds the production bundle into `build/` (used by `install.sh`, copied to
`/opt/netvault/frontend_build` and served by nginx).

### `npm run preview`

Serves the production build locally for a final check before deploying.

### `npm run lint`

Runs ESLint. **Currently broken** — `eslint.config.js` doesn't exist in this directory even
though `eslint`/`typescript-eslint`/`eslint-plugin-react-hooks` are installed as devDependencies.
Add a flat config before relying on this script.

### `npm run test:e2e`

Runs the Playwright end-to-end suite (`e2e/*.spec.ts`). Defaults to `http://localhost:5173`
(Playwright's stock default) unless `E2E_BASE_URL` is set — but `npm run dev` serves on
`:3000`, not `:5173`. Set `E2E_BASE_URL=http://localhost:3000` (or run `npm run preview`,
which does default to 4173/5173 depending on Vite version) before running e2e locally.

## Environment

Copy `.env.example` to `.env`:

```
REACT_APP_API_URL=/api/v1   # relative path in production; point at :8000 for standalone dev
HOST=0.0.0.0                 # dev server bind address
```

## Structure

```
src/
├── components/   # Shared UI components (flat, no subfolders)
├── contexts/     # AuthContext, ThemeContext
├── i18n/         # ru/en/kk locales
├── pages/        # Route-level components
├── services/     # api.service.ts — single API client for the whole backend surface
├── styles/       # Theme CSS (5 themes via CSS custom properties) + per-page stylesheets
├── types/        # Shared TypeScript interfaces (see audit note below)
└── utils/
```

> Several pages/components locally redeclare types that already exist in `types/index.ts`
> instead of importing them, and in at least one case (`BackupSchedule`) the local copy
> describes a different shape than the canonical type. See the architecture audit for the
> full list before adding new features that touch these entities.

## Learn More

- [Vite documentation](https://vitejs.dev/guide/)
- [React documentation](https://react.dev/)
