# TrueLine — Frontend

A React (Vite) frontend for the voice clone detection backend. Four pages —
Dashboard, Analyze, History, Settings — plus Login/Register for JWT auth.

## Local setup

```bash
cd frontend
npm install
cp .env.example .env      # point VITE_API_BASE_URL at your backend
npm run dev
```

Opens at `http://localhost:5173`. Make sure your Django backend is running
(e.g. `python3 manage.py runserver 8001`) and that its `CORS_ALLOWED_ORIGINS`
includes `http://localhost:5173` (already the default in `.env.example`).

## Project structure

```
src/
├── components/       Sidebar, Navbar, RiskScore, RiskFactors, AudioUploader,
│                     AnalysisResult, ProtectedRoute (route guard)
├── pages/             Dashboard, Analyze, History, Settings, Login, Register
├── services/api.js    all backend calls + JWT token handling
├── App.jsx            routes + layout
└── main.jsx           entry point
```

## Building for production

```bash
npm run build
```

Outputs static files to `dist/` — deployable to any static host (Vercel,
Netlify, Render Static Site, GitHub Pages, etc).

## Deploying (Vercel, free tier)

1. Push this whole repo (backend + `frontend/`) to GitHub if you haven't already.
2. Go to vercel.com → sign in with GitHub → **Add New** → **Project**.
3. Import your repo.
4. Set **Root Directory** to `frontend`.
5. Framework preset should auto-detect as **Vite**.
6. Add an environment variable: `VITE_API_BASE_URL` = your deployed backend's
   URL (e.g. `https://your-app.onrender.com`).
7. Click **Deploy**.

Once deployed, go back to your **backend's** environment variables (on
Render) and add your new Vercel URL to `CORS_ALLOWED_ORIGINS`, e.g.:
```
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```
Then redeploy the backend so the CORS change takes effect.

## Notes

- JWT tokens are stored in `localStorage` for simplicity. For a production
  system handling real fraud data, consider httpOnly cookies instead to
  reduce XSS exposure.
- The live-call tab needs the backend's WebSocket endpoint reachable over
  `wss://` once deployed — Render's free tier supports this, but the
  connection will drop if the free instance spins down from inactivity.
