# frontend — Rocky AI Chat Interface

React + Vite chat UI for the multimodal video agent, served via Nginx in
production. Handles the chat conversation, video/image upload, and clip
playback; talks to `multimodal_agent`'s HTTP API.

## Dependencies & Environment Variables

- Node.js 20+, npm
- Build-time only: `VITE_API_URL` — base URL of the `multimodal_agent` API.
  Defaults to `http://localhost:8080` locally; set to `""` in Docker (Nginx
  proxies API paths on the same origin instead — see `nginx.conf`).

## Local Run / Build

```bash
npm install
npm run dev        # dev server on :5173, proxies /chat, /upload-video,
                    # /process-video, /task-status, /reset-memory,
                    # /health, /media to http://localhost:8080

npm run build       # production build → dist/
npm run preview     # preview the production build locally
```

## Testing

No automated frontend test runner is currently configured. Use the TypeScript
production build as the available automated validation:

```bash
npm run build       # type-checks with tsc, then creates the Vite production build
```

For manual smoke testing, run `npm run dev` with `multimodal_agent` available
at the configured `VITE_API_URL`, then verify upload, video processing,
text-query clip search, image-query clip search, chat memory, and clip playback.

## API Usage

Consumes the `multimodal_agent` REST API — see
[`multimodal_agent/README.md`](../multimodal_agent/README.md) for endpoint
details. In production (Docker), Nginx proxies `/chat`, `/upload-video`,
`/process-video`, `/task-status/*`, `/reset-memory`, `/health`, and
`/media/*` to `http://multimodal-agent:8080`.