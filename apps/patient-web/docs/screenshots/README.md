# Patient screen screenshots

Phone-sized (390 x 844 CSS px) shots of every patient screen, from a real run with synthetic data only (Walter, `pt_4b82d0c6`). `home-desktop.png` is the wide view with the phone frame. `summary.png`, `receipt.png` and `network-log.png` show the top of each screen; the `-full` versions show the whole page at 1x.

## Take them again

You need the Sentinel service on `127.0.0.1:8000` (seeded), Ollama with `llama3.2:3b`, `uv`, Node 22, Google Chrome and macOS (`say`). Run this from the repository root:

```bash
node apps/patient-web/docs/screenshots/capture.mjs
```

The script starts its own patient runtime on port 8011 with a temporary database, builds the screen into a temporary folder and serves it on port 4179. It then clicks through the real screens in headless Chrome. The answers are synthetic lines spoken by macOS `say`. Each check-in run shares one synthetic record with the service. When it finishes, the script stops everything it started and deletes the temporary folder, including the audio. It overwrites the PNGs in this folder.

You can change these settings: `CHROME` (the browser path), `SCRATCH`, `RUNTIME_PORT`, `WEB_PORT` and `CDP_PORT`.
