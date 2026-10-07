# Free static deploy (ADR-F36)

The static build serves recorded results from `frontend/public/demo-data/` — no backend, no cold start, no hosting cost.
Review sign-off, Review Queue, History and Copilot work as in the live build (browser storage). Upload and segmentation are replaced by an explanatory card.

## Refresh the recorded data (only when detection results or fixtures change)

```bash
PYTHONPATH=. python scripts/export_static_demo.py   # writes frontend/public/demo-data/ (≈ 12 MB, gate 30 MB)
python -m pytest tests/test_static_export.py -q
```

The exported files are committed, so a static host never needs Python (`data/images/` is git-ignored and only exists locally).

## Build and check locally

```bash
cd frontend
npm run build:static        # → frontend/dist-static/  (uses .env.static: VITE_STATIC_DEMO=1)
npm run preview:static      # http://localhost:4173 — works with the API stopped
```

Optional: `VITE_WALKTHROUGH_URL=https://…` (set in `.env.static`) adds a "Watch the walkthrough" button on the upload card.

## Host it (all free)

Any static host, with a rewrite of `/*` → `/index.html` (SPA routing):
Render Static Site (Blueprint file `render-static.yaml`, or build `npm ci && npm run build:static`, publish `dist-static`), Cloudflare Pages, GitHub Pages, Netlify.

**Login background:** `public/login-bg.mp4` (≈ 6 MB, 720p, no audio) and its poster are small enough for every free static host. The original 121 MB source video is git-ignored and not used by the app.

Nothing here is pushed or deployed automatically; publishing to a public repo or host needs the owner's explicit OK.
