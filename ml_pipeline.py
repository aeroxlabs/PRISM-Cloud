import os
import re
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBClassifier


MODEL_DIR = Path(os.getenv("PRISM_MODEL_DIR", "models"))


def extract_features(texts):
    """Must remain in sync with the feature engineering used during training."""
    rows = []
    for text in texts:
        lower = text.lower()
        urls = re.findall(r"https?://\S+|www\.\S+", lower)
        emails = re.findall(r"\b[\w.+-]+@[\w.-]+\.\w+\b", lower)
        rows.append([
            len(text),
            len(text.split()),
            len(urls),
            len(emails),
            sum(c.isupper() for c in text),
            sum(c.isdigit() for c in text),
            text.count("!"),
            text.count("$"),
            int(bool(re.search(r"\b(urgent|immediately|suspended|locked)\b", lower))),
            int(bool(re.search(r"\b(password|verify|login|credential)\b", lower))),
            int(bool(re.search(r"\b(otp|one.time|verification code|2fa)\b", lower))),
            int(bool(re.search(r"\b(pay|payment|fee|transfer|wire)\b", lower))),
            int(bool(re.search(r"\b(click|tap|open|download)\b", lower))),
            int(bool(re.search(r"\b(won|winner|prize|claim|reward)\b", lower))),
            int(bool(re.search(r"\b(bank|account|billing|refund)\b", lower))),
            int(bool(re.search(r"\b(usps|ups|fedex|dhl|ez.pass)\b", lower))),
            int(bool(re.search(r"\b(crypto|bitcoin|investment|guaranteed)\b", lower))),
        ])
    return csr_matrix(np.asarray(rows, dtype=np.float32))


def load_pipeline():
    required = [
        "prism_word_vectorizer.joblib",
        "prism_char_vectorizer.joblib",
        "prism_threat_model.json",
        "prism_category_model.json",
        "prism_metadata.joblib",
    ]
    missing = [name for name in required if not (MODEL_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing PRISM model artifacts in {MODEL_DIR}: {', '.join(missing)}"
        )

    word_vectorizer = joblib.load(MODEL_DIR / "prism_word_vectorizer.joblib")
    char_vectorizer = joblib.load(MODEL_DIR / "prism_char_vectorizer.joblib")
    metadata = joblib.load(MODEL_DIR / "prism_metadata.joblib")

    threat_model = XGBClassifier()
    threat_model.load_model(str(MODEL_DIR / "prism_threat_model.json"))

    category_model = XGBClassifier()
    category_model.load_model(str(MODEL_DIR / "prism_category_model.json"))

    return {
        "word_vectorizer": word_vectorizer,
        "char_vectorizer": char_vectorizer,
        "threat_model": threat_model,
        "category_model": category_model,
        "categories": metadata["categories"],
    }


def build_features(text, pipeline):
    texts = [text]
    return hstack(
        [
            pipeline["word_vectorizer"].transform(texts),
            pipeline["char_vectorizer"].transform(texts),
            extract_features(texts),
        ],
        format="csr",
        dtype=np.float32,
    )


def get_indicators(text):
    lower = text.lower()
    checks = [
        (r"https?://\S+|www\.\S+", "URL_PRESENT"),
        (r"\b(password|credential|login)\b", "CREDENTIAL_LANGUAGE"),
        (r"\b(otp|one.time|verification code|2fa)\b", "OTP_OR_MFA_LANGUAGE"),
        (r"\b(urgent|immediately|suspended|locked)\b", "URGENCY_OR_ACCOUNT_PRESSURE"),
        (r"\b(pay|payment|fee|transfer|wire)\b", "PAYMENT_LANGUAGE"),
        (r"\b(won|winner|prize|claim|reward)\b", "PRIZE_OR_REWARD_LURE"),
        (r"\b(usps|ups|fedex|dhl|ez.pass)\b", "DELIVERY_OR_TOLL_BRAND"),
        (r"\b(bank|account|billing|refund)\b", "FINANCIAL_ACCOUNT_LANGUAGE"),
        (r"\b(crypto|bitcoin|investment|guaranteed)\b", "CRYPTO_OR_INVESTMENT_LANGUAGE"),
    ]
    return [code for pattern, code in checks if re.search(pattern, lower)]


def risk_level(is_scam, confidence_score):
    if not is_scam:
        return "low"
    if confidence_score >= 0.85:
        return "high"
    if confidence_score >= 0.65:
        return "medium"
    return "low"


def detect(text, pipeline):
    features = build_features(text, pipeline)
    model = pipeline["threat_model"]
    probabilities = model.predict_proba(features)[0]
    positive_index = list(model.classes_).index(1)
    scam_score = float(probabilities[positive_index])
    is_scam = scam_score >= 0.5

    reason_codes = []
    if is_scam:
        reason_codes = get_indicators(text)
        category_probs = pipeline["category_model"].predict_proba(features)[0]
        category_idx = int(np.argmax(category_probs))
        category = pipeline["categories"][category_idx]
        reason_codes.append("PREDICTED_CATEGORY:" + str(category).upper())

    return {
        "is_scam": is_scam,
        "confidence_score": round(scam_score, 6),
        "risk_level": risk_level(is_scam, scam_score),
        "reason_codes": reason_codes,
    }
