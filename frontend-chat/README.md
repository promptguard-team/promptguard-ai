# frontend-chat

End-user chat UI for PromptGuard. Vue 3 + TypeScript + Quasar, built with Vite.

## Requirements

Node 22.22.2+ or 24.15+ (`nvm install 22`). Older 22.x releases fail on the test dependencies.

## Commands

| Command          | What it does                                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| `npm install`    | install dependencies                                                                                                 |
| `npm run dev`    | dev server on <http://localhost:5173>; `/api` is proxied to `http://localhost:8000` (override with `DEV_API_TARGET`) |
| `npm run build`  | production build into `dist/`                                                                                        |
| `npm run lint`   | ESLint + `vue-tsc` type check                                                                                        |
| `npm run format` | Prettier check (`format:write` to fix)                                                                               |
| `npm test`       | Vitest unit tests                                                                                                    |

## How it works

- `src/api/` is the only place that calls `fetch`; errors become `ApiError` with a `kind`.
- `src/stores/auth.ts` keeps the JWT in `localStorage` and resolves the user on start.
- `src/stores/conversations.ts` keeps conversations in `localStorage` per user, under
  `promptguard.chat.v1.<userId>`. There is no server-side history, and two open tabs of the
  same account overwrite each other (the last write wins).
- UI copy lives in `src/i18n/pl.ts`.

## Dev proxy

By default the dev server proxies `/api` to `http://localhost:8000`. To use another
gateway, set `DEV_API_TARGET`, for example:

```bash
DEV_API_TARGET=http://localhost:9000 npm run dev
```

Behind the compose nginx, set `HMR_CLIENT_PORT=8080` (done in `docker-compose.yml`) so the
HMR websocket connects through the proxy port.

## Docker Compose

The first `docker compose up` after switching from the old mock frontend must recreate the
anonymous `node_modules` volume, otherwise the container still sees the empty one:

```bash
docker compose up -d --build -V chat
```
