# Deploying SafeSignal (free tier)

The company side hosts the service and the company portal on Render's free tier from `render.yaml` (D-085). Doctor-web and patient-web host themselves on Render or Vercel. The patient runtime never leaves the demo laptop (Scoping Doc 26.12).

| Piece | Host | URL |
| --- | --- | --- |
| Service | Render web service `safesignal-service` | `https://safesignal-service.onrender.com` |
| Company portal | Render static site `safesignal-company` | `https://safesignal-company.onrender.com` |
| Doctor-web, patient-web | Their owners' choice | Sent to the company owner |
| Patient runtime | Demo laptop | `http://127.0.0.1:8001` |

If Render adds a suffix because a name is taken, use the URL Render shows, and update `VITE_COMPANY_SERVICE_URL` in `render.yaml` and the handoff doc to match.

## First-time setup (company owner, about 10 minutes)

1. Sign in at <https://dashboard.render.com> with GitHub. No card is needed for free services.
2. **New → Blueprint**, pick the SafeSignal repository, branch `main`. Render reads `render.yaml` and lists `safesignal-service` and `safesignal-company`.
3. Render asks for `SENTINEL_ALLOWED_ORIGINS` (marked `sync: false`). Enter `https://safesignal-company.onrender.com` for now.
4. **Apply.** The first build takes a few minutes; the service build seeds the synthetic demo data.
5. Check `https://safesignal-service.onrender.com/healthz` returns `{"status":"ok",...,"seeded":true}`, then open the portal URL.

## Adding a teammate's origin

1. Dashboard → `safesignal-service` → **Environment** → edit `SENTINEL_ALLOWED_ORIGINS`.
2. Append the origin, comma-separated, exactly as the browser shows it: scheme and host, no path, no trailing slash. Example: `https://safesignal-company.onrender.com,https://doctor-one.vercel.app`.
3. **Save, rebuild and deploy.** The service restarts, which also resets its data to the seeded state.
4. Check it: `curl -si -X OPTIONS https://safesignal-service.onrender.com/v1/terms -H "Origin: <origin>" -H "Access-Control-Request-Method: GET" | grep -i access-control-allow-origin`.

## How deploys behave

- A merge to `main` redeploys only what it touched (`buildFilter`): the service for `apps/service`, `packages/contract-py` or `schema`; the portal for `apps/company-web`, `packages/contract-ts` or `schema`.
- The free service sleeps after 15 minutes idle; the next request takes about 50 seconds. Open `/healthz` a minute before a demo.
- The free disk is not persistent. Every restart or deploy returns the databases to the seeded state from the build: live check-ins and the doctors' registered keys are lost, so doctors clear site data and reload.
- `VITE_*` values are baked in at build time. Changing one needs a redeploy, not a restart.
- No merges touching the service in the last hour before a demo.

## Teammates

The handoff for doctor-web and patient-web (settings, env vars, what to send back, checks and troubleshooting) is the shared doc "SafeSignal deployment: integration handoff". Short version:

- Doctor-web: `VITE_DOCTOR_SERVICE_URL=https://safesignal-service.onrender.com`; send the deployed origin. Each origin holds one doctor (DW-19).
- Patient runtime: `SENTINEL_BASE_URL=https://safesignal-service.onrender.com` on the laptop; `PATIENT_ALLOWED_ORIGINS` lists where patient-web is served from.
- Patient-web: run locally on the demo laptop (recommended), or host it with `VITE_PATIENT_RUNTIME_URL=http://127.0.0.1:8001` and allow Chrome's local-network prompt.
