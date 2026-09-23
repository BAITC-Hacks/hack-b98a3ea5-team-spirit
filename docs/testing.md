# ML tests

Run the offline checks with:

```bash
bash scripts/verify.sh
```

Tests cover CSV parsing, removal of ID/date from model inputs, month and season
features, chronological CV, the 15-model registry, artifact creation, and
save/load inference consistency.
