# frontend-chat

End-user chat UI for PromptGuard. Vue 3 + TypeScript + Quasar, built with Vite.

## Requirements

Node >= 22.12 (`nvm install 22`).

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
  `promptguard.chat.v1.<userId>`. There is no server-side history.
- UI copy lives in `src/i18n/pl.ts`.

## Dev proxy

By default the dev server proxies `/api` to `http://localhost:8000`. To use another
gateway, set `DEV_API_TARGET`, for example:

```bash
DEV_API_TARGET=http://localhost:9000 npm run dev
```

Behind the compose nginx, set `HMR_CLIENT_PORT=8080` (done in `docker-compose.yml`) so the
HMR websocket connects through the proxy port.
