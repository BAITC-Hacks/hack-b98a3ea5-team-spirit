# HackAlem Team Spirit — wind ML

This repository currently contains the minimal ML training slice described in
`ml/ML.md`. It trains a separate power-curve model for each turbine.

## Quick start

```bash
bash scripts/bootstrap.sh
bash scripts/verify.sh
uv run python -m ml.cli train --config config/training.json --smoke
```

Run the complete two-stage search on the remote machine:

```bash
uv run python -m ml.cli train --config config/training.json --n-jobs -1
```

Artifacts are written to `storage/models/<turbine_id>/`. Selection uses
chronological cross-validation. January 2026 is reported only as an independent
power-curve evaluation and does not influence model or parameter selection.

These models are trained on measured weather. Their metrics must not be called
24/48-hour forecast accuracy until an issue-time-safe weather forecast dataset
is added.
