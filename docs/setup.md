# ML setup

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
