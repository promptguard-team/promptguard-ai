# frontend-ciso

CISO security dashboard for PromptGuard. Vue 3 + TypeScript + Quasar, built with Vite.
Only accounts with the `ciso` role can sign in (grant it with the gateway CLI).

## Requirements

Node 22.22.2+ or 24.15+ (`nvm install 22`).

## Commands

| Command          | What it does                                                            |
| ---------------- | ----------------------------------------------------------------------- |
| `npm install`    | install dependencies                                                    |
| `npm run dev`    | dev server on <http://localhost:5173/ciso/>; `/api` goes to the gateway |
| `npm run build`  | production build into `dist/`                                           |
| `npm run lint`   | ESLint + `vue-tsc` type check                                           |
| `npm run format` | Prettier check (`format:write` to fix)                                  |
| `npm test`       | Vitest unit tests                                                       |

## How it works

- `src/api/` is the only place that calls `fetch`. A 401 ends the session as expired, a 403
  (role revoked) as forbidden; both return to the login page with a message.
- The JWT is stored in `localStorage` under `promptguard.ciso.token`, separate from the chat app,
  which shares the origin.
- The dashboard uses `GET /audit/stats`, `/audit/timeseries` and `/audit/events`. The event list
  never shows prompt text. Filters and the page live in the URL.
- Times are shown in `Europe/Warsaw`, the zone the gateway uses for daily buckets.
- UI copy lives in `src/i18n/pl.ts`.

## Base path `/ciso/`

The app is built and served under `/ciso/` (`base` in `vite.config.ts`). Any proxy in front of
it, whether the compose `nginx` or a future k8s ingress, must forward `/ciso/` **without
stripping the prefix**.

## Dev proxy

`npm run dev` proxies `/api` to `http://localhost:8000`. Override it with `DEV_API_TARGET`:

```bash
DEV_API_TARGET=http://localhost:9000 npm run dev
```

Behind the compose nginx, `HMR_CLIENT_PORT=8080` (set in `docker-compose.yml`) lets HMR connect
through the proxy port.

## Docker Compose

The first `docker compose up` after replacing the old mock frontend must recreate the anonymous
`node_modules` volume:

```bash
docker compose up -d --build -V ciso nginx
```

The panel is then at <http://localhost:8080/ciso/>.
