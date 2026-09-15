"""
scripts/train_logistic_regression.py
-------------------------------------
Entrena el modelo de Regresión Logística V1 utilizando ÚNICAMENTE el dataset
histórico independiente `archivosreales/historico_cierres.csv` (casos HX-00001..HX-02200).

Features de entrenamiento:
  - log_horas: np.log1p(horas_al_primer_contacto)
  - horas_na: 1 si horas_al_primer_contacto es NULL/NaN else 0
  - pidio_cita: 1 si pidio_cita == 'SI' else 0
  - manifesto_cuota_inicial: 1 si manifesto_cuota_inicial == 'SI' else 0
  - pago_credito: 1 si forma_pago_declarada == 'credito' else 0

El artefacto serializado se guarda en `models/logistic_regression_v1.joblib`
e incluye la metadata, coeficientes, intercepto y lista de features para
garantizar reproducibilidad e inferencia ligera sin desviaciones por orden de columnas.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_DIR, "archivosreales", "historico_cierres.csv")
MODEL_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "logistic_regression_v1.joblib")


def entrenar_modelo():
    print("=" * 70)
    print("ENTRENAMIENTO LOGISTIC REGRESSION V1")
    print("=" * 70)
    print(f"Cargando dataset histórico desde: {DATA_PATH}")

    df_hist = pd.read_csv(DATA_PATH)
    print(f"Filas totales en histórico: {len(df_hist)}")

    # Filtrar solo casos conocidos (Cerrado vs Perdido)
    df_kn = df_hist[df_hist['desenlace'].isin(['Cerrado', 'Perdido'])].copy()
    print(f"Casos con desenlace conocido: {len(df_kn)} ({len(df_kn[df_kn.desenlace=='Cerrado'])} Cerrado, {len(df_kn[df_kn.desenlace=='Perdido'])} Perdido)")

    # Target
    y = (df_kn['desenlace'] == 'Cerrado').astype(int).values

    # Feature engineering
    horas = df_kn['horas_al_primer_contacto']
    horas_median = horas.median()

    X = pd.DataFrame()
    X['log_horas'] = np.log1p(horas.fillna(horas_median))
    X['horas_na'] = horas.isna().astype(int)
    X['pidio_cita'] = (df_kn['pidio_cita'] == 'SI').astype(int)
    X['manifesto_cuota_inicial'] = (df_kn['manifesto_cuota_inicial'] == 'SI').astype(int)
    X['pago_credito'] = (df_kn['forma_pago_declarada'] == 'credito').astype(int)

    feature_names = list(X.columns)
    print(f"Features utilizadas ({len(feature_names)}): {feature_names}")

    # Entrenar Regresión Logística con pesos balanceados
    clf = LogisticRegression(
        class_weight='balanced',
        C=1.0,
        solver='lbfgs',
        max_iter=1000,
        random_state=42
    )
    clf.fit(X, y)

    # Evaluación en entrenamiento
    probs = clf.predict_proba(X)[:, 1]
    auc = roc_auc_score(y, probs)
    prauc = average_precision_score(y, probs)

    print(f"\nMétricas en entrenamiento:")
    print(f"  ROC-AUC: {auc:.4f}")
    print(f"  PR-AUC:  {prauc:.4f}")

    coef_dict = dict(zip(feature_names, clf.coef_[0].tolist()))
    print(f"\nCoeficientes del modelo:")
    for feat, coef in coef_dict.items():
        print(f"  {feat:<25}: {coef:+.4f}")
    print(f"  {'intercept':<25}: {clf.intercept_[0]:+.4f}")

    # Preparar paquete de modelo
    os.makedirs(MODEL_DIR, exist_ok=True)

    package = {
        "model": clf,
        "feature_names": feature_names,
        "horas_median_impute": float(horas_median),
        "coeficients": coef_dict,
        "intercept": float(clf.intercept_[0]),
        "model_scoring": "logistic_regression",
        "version_scoring": "v1.0",
        "training_dataset": "archivosreales/historico_cierres.csv",
        "n_samples": len(df_kn),
        "n_positives": int(y.sum()),
        "roc_auc_train": round(float(auc), 4),
        "pr_auc_train": round(float(prauc), 4)
    }

    joblib.dump(package, MODEL_PATH)
    print(f"\n[OK] Modelo serializado exitosamente en: {MODEL_PATH}")
    print("=" * 70)
    return package


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    entrenar_modelo()
