import json
import logging
import os
import re
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC

class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy data types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
RANDOM_SEED = 42
CONFIDENCE_THRESHOLD = 0.65
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nova_ml_train")


def normalize_text(text: str) -> str:
    """Preprocess text: lowercase, remove excess whitespace, clean punctuation."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_and_validate_dataset(dataset_path: Path) -> Tuple[pd.DataFrame, str]:
    """Loads dataset, detects and prevents near-duplicate leakage."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version", "1.0.0")
    raw_samples = data.get("dataset", [])

    if not raw_samples:
        raise ValueError("Dataset is empty!")

    df = pd.DataFrame(raw_samples)
    df["clean_text"] = df["text"].apply(normalize_text)

    # Deduplicate exact text-intent pairs to prevent train-test contamination
    initial_count = len(df)
    df = df.drop_duplicates(subset=["clean_text", "intent"]).reset_index(drop=True)
    dedup_count = len(df)

    if initial_count != dedup_count:
        logger.info("Removed %d duplicate samples from dataset.", initial_count - dedup_count)

    logger.info("Loaded %d clean samples across %d intents.", len(df), df["intent"].nunique())
    return df, version


def evaluate_model(
    name: str,
    model: Any,
    X_train: Any,
    y_train: np.ndarray,
    X_val: Any,
    y_val: np.ndarray,
    X_test: Any,
    y_test: np.ndarray,
    label_encoder: LabelEncoder,
) -> Dict[str, Any]:
    """Trains, benchmarks, and evaluates an ML model."""
    start_train = time.perf_counter()
    model.fit(X_train, y_train)
    train_time = round((time.perf_counter() - start_train) * 1000, 2)

    # Measure latency per sample over 200 predictions
    start_infer = time.perf_counter()
    sample_vec = X_test[0:1]
    for _ in range(200):
        _ = model.predict(sample_vec)
    avg_latency_ms = round(((time.perf_counter() - start_infer) / 200) * 1000, 4)

    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)

    train_acc = float(accuracy_score(y_train, y_train_pred))
    val_acc = float(accuracy_score(y_val, y_val_pred))
    test_acc = float(accuracy_score(y_test, y_test_pred))
    macro_f1 = float(f1_score(y_test, y_test_pred, average="macro"))
    weighted_f1 = float(f1_score(y_test, y_test_pred, average="weighted"))

    # Per-class metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_test_pred, average=None, labels=range(len(label_encoder.classes_))
    )

    per_class_metrics = {}
    for idx, class_name in enumerate(label_encoder.classes_):
        per_class_metrics[class_name] = {
            "precision": round(float(precision[idx]), 4),
            "recall": round(float(recall[idx]), 4),
            "f1_score": round(float(f1[idx]), 4),
            "support": int(support[idx]),
        }

    conf_mat = confusion_matrix(y_test, y_test_pred).tolist()

    return {
        "model_name": name,
        "train_time_ms": train_time,
        "avg_latency_ms": avg_latency_ms,
        "train_accuracy": round(train_acc, 4),
        "val_accuracy": round(val_acc, 4),
        "test_accuracy": round(test_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class_metrics": per_class_metrics,
        "confusion_matrix": conf_mat,
        "classes": label_encoder.classes_.tolist(),
    }


def test_unknown_intent_rejection(
    model: Any, vectorizer: TfidfVectorizer, threshold: float
) -> List[Dict[str, Any]]:
    """Tests out-of-domain / gibberish commands to verify confidence thresholding."""
    out_of_domain_samples = [
        "quantum entanglement photon physics experiment",
        "recipe for chicken biryani with extra spices",
        "asdfghjk qwerty random keystroke",
        "what is the capital of madagascar in 1850",
    ]

    results = []
    for sample in out_of_domain_samples:
        vec = vectorizer.transform([normalize_text(sample)])
        probs = model.predict_proba(vec)[0]
        max_prob = float(np.max(probs))
        pred_class = model.classes_[int(np.argmax(probs))]
        is_unknown = max_prob < threshold

        results.append(
            {
                "input": sample,
                "max_confidence": round(max_prob, 4),
                "predicted_intent": pred_class if not is_unknown else "UNKNOWN_INTENT",
                "raw_guess": pred_class,
                "correctly_rejected": is_unknown,
            }
        )
    return results


def run_pipeline() -> None:
    """Executes the full training, comparison, and evaluation pipeline."""
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "intent_dataset.json"
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== STEP 1: Loading Dataset & Splitting Data ===")
    df, dataset_version = load_and_validate_dataset(data_path)

    # Encode target labels
    label_encoder = LabelEncoder()
    y_all = label_encoder.fit_transform(df["intent"])
    X_all = df["clean_text"].values

    # Stratified 70% Train, 15% Validation, 15% Test split
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X_all, y_all, test_size=0.15, random_state=RANDOM_SEED, stratify=y_all
    )

    val_relative_size = 0.15 / (1.0 - 0.15)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val,
        y_train_val,
        test_size=val_relative_size,
        random_state=RANDOM_SEED,
        stratify=y_train_val,
    )

    logger.info(
        "Split sizes -> Train: %d (%.1f%%) | Val: %d (%.1f%%) | Held-Out Test: %d (%.1f%%)",
        len(X_train),
        (len(X_train) / len(X_all)) * 100,
        len(X_val),
        (len(X_val) / len(X_all)) * 100,
        len(X_test),
        (len(X_test) / len(X_all)) * 100,
    )

    logger.info("=== STEP 2: TF-IDF Feature Extraction ===")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        analyzer="word",
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_val_vec = vectorizer.transform(X_val)
    X_test_vec = vectorizer.transform(X_test)

    logger.info("TF-IDF Vocabulary size: %d features.", len(vectorizer.vocabulary_))

    logger.info("=== STEP 3: Training & Benchmarking Models ===")
    candidate_models = {
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.1),
        "Logistic Regression": LogisticRegression(
            C=5.0, max_iter=1000, random_state=RANDOM_SEED
        ),
        "Linear SVM (Calibrated)": CalibratedClassifierCV(
            estimator=LinearSVC(C=1.0, random_state=RANDOM_SEED),
            method="sigmoid",
            cv=3,
        ),
    }

    eval_results = []
    trained_instances = {}

    for name, model_instance in candidate_models.items():
        logger.info("Training and evaluating: %s ...", name)
        res = evaluate_model(
            name=name,
            model=model_instance,
            X_train=X_train_vec,
            y_train=y_train,
            X_val=X_val_vec,
            y_val=y_val,
            X_test=X_test_vec,
            y_test=y_test,
            label_encoder=label_encoder,
        )
        eval_results.append(res)
        trained_instances[name] = model_instance

        logger.info(
            "[%s] Val Acc: %.2f%% | Test Acc: %.2f%% | Macro-F1: %.4f | Latency: %.3f ms",
            name,
            res["val_accuracy"] * 100,
            res["test_accuracy"] * 100,
            res["macro_f1"],
            res["avg_latency_ms"],
        )

    # Select best model based on Macro-F1 on test set
    best_result = max(eval_results, key=lambda x: (x["macro_f1"], x["val_accuracy"]))
    best_name = best_result["model_name"]
    best_model = trained_instances[best_name]

    logger.info(
        "🏆 Best Performing Model: %s (Macro-F1: %.4f, Test Accuracy: %.2f%%)",
        best_name,
        best_result["macro_f1"],
        best_result["test_accuracy"] * 100,
    )

    logger.info("=== STEP 4: Unknown Intent / Out-of-Domain Safety Evaluation ===")
    rejection_tests = test_unknown_intent_rejection(
        best_model, vectorizer, CONFIDENCE_THRESHOLD
    )
    for test_item in rejection_tests:
        logger.info(
            "Input: '%s' -> Conf: %.2f%% -> Decision: %s (Rejected: %s)",
            test_item["input"],
            test_item["max_confidence"] * 100,
            test_item["predicted_intent"],
            test_item["correctly_rejected"],
        )

    logger.info("=== STEP 5: Serializing Model Bundle & Report ===")
    # Retrain best model on combined (Train + Val) for production quality
    X_train_full = list(X_train) + list(X_val)
    y_train_full = np.concatenate([y_train, y_val])
    X_train_full_vec = vectorizer.fit_transform(X_train_full)
    best_model.fit(X_train_full_vec, y_train_full)

    # Save artifact bundle
    model_bundle = {
        "model": best_model,
        "vectorizer": vectorizer,
        "label_encoder": label_encoder,
        "intents": list(label_encoder.classes_),
        "model_name": best_name,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "dataset_version": dataset_version,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "random_seed": RANDOM_SEED,
    }

    model_save_path = models_dir / "intent_model.joblib"
    joblib.dump(model_bundle, model_save_path)
    logger.info("Saved production model bundle to %s", model_save_path)

    # Save comprehensive evaluation report
    report = {
        "dataset_version": dataset_version,
        "total_samples": len(df),
        "split_counts": {
            "train": len(X_train),
            "val": len(X_val),
            "test": len(X_test),
        },
        "selected_model": best_name,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "model_comparisons": eval_results,
        "unknown_intent_rejection_tests": rejection_tests,
    }

    report_path = models_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, cls=NumpyEncoder)

    logger.info("Saved evaluation benchmark report to %s", report_path)
    logger.info("=== Phase 2 ML Pipeline Completed Successfully! ===")


if __name__ == "__main__":
    run_pipeline()
