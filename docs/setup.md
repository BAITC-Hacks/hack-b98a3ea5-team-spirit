# Setup

Install the locked environment:

```bash
bash scripts/bootstrap.sh
```

Run a short local pipeline check:

```bash
uv run python -m ml.cli train --config config/training.json --smoke
```

The full run is CPU-oriented. On Brev, use all available CPU workers unless the
machine becomes memory constrained:

```bash
uv run python -m ml.cli train --config config/training.json --n-jobs -1
```

The scikit-learn estimators in this project do not use the NVIDIA GPU.
Full-run artifacts are saved under `storage/models/production/`; smoke artifacts
are isolated under `storage/models/production/smoke/`.

Install frontend dependencies and start both development processes:

```bash
npm ci --prefix frontend
uv run uvicorn backend.app.main:app --reload --port 8000
npm run dev --prefix frontend
```

The Vite server proxies `/api` to port 8000. Times entered in the UI are UTC.
Copy `.env.example` to `.env` only when overriding defaults; no API key is needed.

Production is one container on port 8000:

```bash
docker build -t wind-app .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env wind-app
```

If a volume is mounted at `/app/storage`, it must contain the two production model
directories and be writable by UID 10001 so the weather cache can be created.
