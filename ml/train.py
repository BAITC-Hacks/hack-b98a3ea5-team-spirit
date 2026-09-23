"""Two-stage GridSearchCV training across fifteen regression algorithms."""

from __future__ import annotations

import json
import os
import tempfile
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    AdaBoostRegressor,
    BaggingRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, HuberRegressor, Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

from ml.data import DataError, load_training_data
from ml.features import FEATURE_COLUMNS, build_features
from ml.splits import make_time_splits

MODEL_NAMES = (
    "decision_tree",
    "random_forest",
    "extra_trees",
    "hist_gradient_boosting",
    "gradient_boosting",
    "ada_boost",
    "bagging",
    "linear_regression",
    "ridge",
    "lasso",
    "elastic_net",
    "huber",
    "knn",
    "svr_rbf",
    "mlp",
)


def _pipeline(model: Any, *, scale: bool) -> Pipeline:
    steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", model))
    return Pipeline(steps)


def build_models(random_state: int) -> dict[str, Pipeline]:
    """Return exactly the fifteen algorithms requested by ML.md."""

    return {
        "decision_tree": _pipeline(
            DecisionTreeRegressor(random_state=random_state), scale=False
        ),
        "random_forest": _pipeline(
            RandomForestRegressor(random_state=random_state, n_jobs=1), scale=False
        ),
        "extra_trees": _pipeline(
            ExtraTreesRegressor(random_state=random_state, n_jobs=1), scale=False
        ),
        "hist_gradient_boosting": _pipeline(
            HistGradientBoostingRegressor(
                random_state=random_state,
                early_stopping=False,
            ),
            scale=False,
        ),
        "gradient_boosting": _pipeline(
            GradientBoostingRegressor(random_state=random_state), scale=False
        ),
        "ada_boost": _pipeline(
            AdaBoostRegressor(random_state=random_state), scale=False
        ),
        "bagging": _pipeline(
            BaggingRegressor(random_state=random_state, n_jobs=1), scale=False
        ),
        "linear_regression": _pipeline(LinearRegression(), scale=True),
        "ridge": _pipeline(Ridge(), scale=True),
        "lasso": _pipeline(Lasso(max_iter=20_000), scale=True),
        "elastic_net": _pipeline(
            ElasticNet(max_iter=20_000, random_state=random_state), scale=True
        ),
        "huber": _pipeline(HuberRegressor(max_iter=2_000), scale=True),
        "knn": _pipeline(KNeighborsRegressor(n_jobs=1), scale=True),
        "svr_rbf": _pipeline(SVR(kernel="rbf", cache_size=2048), scale=True),
        "mlp": _pipeline(
            MLPRegressor(
                random_state=random_state,
                early_stopping=False,
                max_iter=1_000,
            ),
            scale=True,
        ),
    }


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "turbines",
        "output_dir",
        "test_start",
        "cv_splits",
        "shortlist_size",
        "n_jobs",
        "random_state",
        "models",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"training config is missing keys: {missing}")
    return config


def _first_grid_values(grid: dict[str, list[Any]]) -> dict[str, list[Any]]:
    return {key: [values[0]] for key, values in grid.items()}


def _grid_for(
    config: dict[str, Any],
    model_name: str,
    stage: str,
    *,
    smoke: bool,
) -> dict[str, list[Any]]:
    try:
        grid = deepcopy(config["models"][model_name][f"{stage}_grid"])
    except KeyError as exc:
        raise ValueError(f"missing {stage} grid for {model_name}") from exc
    if not grid:
        return {}
    if any(not isinstance(values, list) or not values for values in grid.values()):
        raise ValueError(f"all grid values must be non-empty lists for {model_name}")
    return _first_grid_values(grid) if smoke else grid


def _search(
    *,
    name: str,
    pipeline: Pipeline,
    grid: dict[str, list[Any]],
    features: pd.DataFrame,
    target: pd.Series,
    cv: list[tuple[np.ndarray, np.ndarray]],
    n_jobs: int,
    stage: str,
) -> tuple[dict[str, Any], Pipeline]:
    unknown = sorted(set(grid) - set(pipeline.get_params(deep=True)))
    if unknown:
        raise ValueError(f"unknown parameters for {name}: {unknown}")

    started = time.perf_counter()
    search = GridSearchCV(
        estimator=pipeline,
        param_grid=grid,
        scoring="neg_mean_absolute_error",
        cv=cv,
        refit=True,
        error_score="raise",
        n_jobs=n_jobs,
        return_train_score=False,
    )
    search.fit(features, target)
    index = int(search.best_index_)
    result = {
        "model": name,
        "stage": stage,
        "cv_mae": float(-search.best_score_),
        "cv_mae_std": float(search.cv_results_["std_test_score"][index]),
        "best_params": search.best_params_,
        "grid_candidates": len(search.cv_results_["params"]),
        "fit_seconds": round(time.perf_counter() - started, 3),
    }
    return result, search.best_estimator_


def _baseline(
    features: pd.DataFrame,
    target: pd.Series,
    cv: list[tuple[np.ndarray, np.ndarray]],
    n_jobs: int,
) -> dict[str, Any]:
    pipeline = _pipeline(DummyRegressor(strategy="median"), scale=False)
    result, _ = _search(
        name="dummy_median",
        pipeline=pipeline,
        grid={},
        features=features,
        target=target,
        cv=cv,
        n_jobs=n_jobs,
        stage="baseline",
    )
    return result


def _metrics(model: Pipeline, features: pd.DataFrame, target: pd.Series) -> dict[str, float]:
    prediction = model.predict(features)
    return {
        "mae": float(mean_absolute_error(target, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(target, prediction))),
        "r2": float(r2_score(target, prediction)),
    }


def _atomic_dump(model: Pipeline, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        joblib.dump(model, temporary, compress=("xz", 3))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _train_turbine(
    *,
    frame: pd.DataFrame,
    data_summary: Any,
    turbine_id: str,
    source_path: Path,
    config: dict[str, Any],
    model_names: list[str],
    output_root: Path,
    smoke: bool,
    n_jobs: int,
) -> dict[str, Any]:
    test_start = pd.Timestamp(config["test_start"])
    train_frame = frame.loc[frame["timestamp"] < test_start].reset_index(drop=True)
    test_frame = frame.loc[frame["timestamp"] >= test_start].reset_index(drop=True)
    if train_frame.empty or test_frame.empty:
        raise DataError(
            f"{turbine_id} needs rows on both sides of test_start={test_start}"
        )

    if smoke:
        maximum = int(config.get("smoke_max_rows", 4_000))
        train_frame = train_frame.tail(maximum).reset_index(drop=True)

    x_train = build_features(train_frame)
    y_train = train_frame["power_normalized"]
    x_test = build_features(test_frame)
    y_test = test_frame["power_normalized"]
    cv = make_time_splits(len(train_frame), n_splits=int(config["cv_splits"]))

    models = build_models(int(config["random_state"]))
    missing_models = sorted(set(model_names) - set(models))
    if missing_models:
        raise ValueError(f"unknown models: {missing_models}")

    baseline = _baseline(x_train, y_train, cv, n_jobs)
    coarse_results: list[dict[str, Any]] = []
    for name in model_names:
        print(f"[{turbine_id}] coarse GridSearchCV: {name}", flush=True)
        result, _ = _search(
            name=name,
            pipeline=models[name],
            grid=_grid_for(config, name, "coarse", smoke=smoke),
            features=x_train,
            target=y_train,
            cv=cv,
            n_jobs=n_jobs,
            stage="coarse",
        )
        coarse_results.append(result)

    shortlist_size = 1 if smoke else int(config["shortlist_size"])
    shortlisted = [
        result["model"]
        for result in sorted(coarse_results, key=lambda item: item["cv_mae"])[
            :shortlist_size
        ]
    ]

    fine_results: list[dict[str, Any]] = []
    best_model: Pipeline | None = None
    best_name = ""
    best_cv_mae = float("inf")
    for name in shortlisted:
        print(f"[{turbine_id}] fine GridSearchCV: {name}", flush=True)
        result, estimator = _search(
            name=name,
            pipeline=models[name],
            grid=_grid_for(config, name, "fine", smoke=smoke),
            features=x_train,
            target=y_train,
            cv=cv,
            n_jobs=n_jobs,
            stage="fine",
        )
        result["january_power_curve_metrics"] = _metrics(estimator, x_test, y_test)
        fine_results.append(result)
        if result["cv_mae"] < best_cv_mae:
            best_cv_mae = result["cv_mae"]
            best_name = name
            best_model = estimator

    if best_model is None:
        raise RuntimeError("no model completed fine search")

    # January is evaluated above, never used for model/parameter selection.
    final_frame = pd.concat([train_frame, test_frame], ignore_index=True)
    final_model = clone(best_model).fit(
        build_features(final_frame),
        final_frame["power_normalized"],
    )

    artifact_dir = output_root / turbine_id
    manifest = {
        "turbine_id": turbine_id,
        "smoke": smoke,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "source_path": str(source_path),
        "data_summary": data_summary.__dict__,
        "feature_columns": list(FEATURE_COLUMNS),
        "selected_model": best_name,
        "selection_metric": "mean cross-validation MAE",
        "test_period": {
            "start": test_frame["timestamp"].min().isoformat(),
            "end": test_frame["timestamp"].max().isoformat(),
            "role": "independent power-curve evaluation; not used for selection",
        },
        "baseline": baseline,
        "coarse_results": coarse_results,
        "shortlisted_models": shortlisted,
        "fine_results": fine_results,
        "final_fit_rows": len(final_frame),
        "random_state": int(config["random_state"]),
        "versions": {
            "python": os.sys.version.split()[0],
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "limitation": (
            "trained on measured weather; metrics are power-curve evaluation, "
            "not a demonstrated 24/48-hour weather forecast"
        ),
    }
    _atomic_dump(final_model, artifact_dir / "model.joblib")
    _atomic_json(manifest, artifact_dir / "manifest.json")
    return {
        "turbine_id": turbine_id,
        "artifact_dir": str(artifact_dir),
        "selected_model": best_name,
        "cv_mae": best_cv_mae,
    }


def train_all(
    config_path: str | Path,
    *,
    smoke: bool = False,
    n_jobs_override: int | None = None,
) -> dict[str, Any]:
    """Train and persist one selected pipeline per configured turbine."""

    path = Path(config_path).resolve()
    config = _load_config(path)
    project_root = path.parent.parent
    output_root = project_root / config["output_dir"]
    if smoke:
        output_root = output_root / "smoke"
    n_jobs = int(config["n_jobs"] if n_jobs_override is None else n_jobs_override)
    model_names = list(config.get("smoke_models", MODEL_NAMES) if smoke else MODEL_NAMES)

    results = []
    for turbine in config["turbines"]:
        source_path = project_root / turbine["path"]
        frame, summary = load_training_data(
            source_path,
            turbine_id=turbine["id"],
            samples_per_hour=int(config.get("samples_per_hour", 6)),
        )
        results.append(
            _train_turbine(
                frame=frame,
                data_summary=summary,
                turbine_id=turbine["id"],
                source_path=source_path,
                config=config,
                model_names=model_names,
                output_root=output_root,
                smoke=smoke,
                n_jobs=n_jobs,
            )
        )

    return {"smoke": smoke, "models_considered": model_names, "results": results}
