"""Regression + optional price-regime classification for analysis layer."""
from __future__ import annotations

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import LabelEncoder

FEATURE_CANDIDATES = [
    "hour",
    "dow",
    "is_weekend",
    "month",
    "TOTALDEMAND",
    "NETINTERCHANGE",
    "AVAILABLEGENERATION",
    "DISPATCHABLEGENERATION",
    "SEMISCHEDULE_CLEAREDMW",
    "UIGF",
    "SPARE_CAPACITY",
    "tight_system",
]


def _features(df: pd.DataFrame) -> list[str]:
    return [c for c in FEATURE_CANDIDATES if c in df.columns]


def run_regression(hourly: pd.DataFrame, target: str = "RRP", region: str | None = None) -> dict:
    d = hourly if region is None else hourly[hourly["REGIONID"] == region].copy()
    feats = _features(d)
    d = d.dropna(subset=feats + [target])
    if len(d) < 200:
        return {"error": "not enough rows", "n": len(d)}
    X = d[feats]
    y = d[target]
    # chronological split
    split = int(len(d) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    results = []
    for name, model in [
        ("Ridge", Ridge(alpha=1.0)),
        ("HistGB", HistGradientBoostingRegressor(max_depth=6, max_iter=150, random_state=42)),
    ]:
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        results.append(
            {
                "model": name,
                "region": region or "ALL",
                "target": target,
                "mae": float(mean_absolute_error(y_test, pred)),
                "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
                "r2": float(r2_score(y_test, pred)),
                "n_train": len(X_train),
                "n_test": len(X_test),
                "features": feats,
            }
        )
    return {"results": results, "features": feats}


def run_classification(hourly: pd.DataFrame, region: str | None = None) -> dict:
    d = hourly if region is None else hourly[hourly["REGIONID"] == region].copy()
    if "price_regime" not in d.columns:
        return {"error": "price_regime missing"}
    feats = [c for c in _features(d) if c != "RRP"]
    d = d.dropna(subset=feats + ["price_regime"])
    if len(d) < 200:
        return {"error": "not enough rows", "n": len(d)}
    le = LabelEncoder()
    y = le.fit_transform(d["price_regime"])
    X = d[feats]
    split = int(len(d) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y[:split], y[split:]
    out = []
    # multi_class removed in newer scikit-learn (multinomial is default for multinomial loss)
    for name, model in [
        ("Logistic", LogisticRegression(max_iter=1000)),
        ("HistGB_clf", HistGradientBoostingClassifier(max_depth=6, max_iter=100, random_state=42)),
    ]:
        try:
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            out.append(
                {
                    "model": name,
                    "region": region or "ALL",
                    "accuracy": float(accuracy_score(y_test, pred)),
                    "confusion": confusion_matrix(y_test, pred).tolist(),
                    "labels": list(le.classes_),
                    "report": classification_report(
                        y_test, pred, target_names=list(le.classes_), output_dict=True
                    ),
                    "n_test": len(y_test),
                }
            )
        except Exception as e:
            out.append({"model": name, "error": str(e)})
    return {"results": out, "features": feats}
