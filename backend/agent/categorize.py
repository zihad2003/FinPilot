"""Merchant normalization and hybrid categorization."""

import re

from sqlalchemy.orm import Session

from app.models import MerchantCorrection, Transaction

CATEGORIES = [
    "income",
    "housing",
    "groceries",
    "transport",
    "subscriptions",
    "utilities",
    "education",
    "dining",
    "shopping",
    "savings",
    "other",
]

_STOP = {"COM", "STORE", "MKT", "TRIP", "BILL", "POS", "SQ", "USA", "PAYMENT"}

# Earlier rules win. Keep specific phrases ahead of shorter tokens.
RULES: list[tuple[tuple[str, ...], str, float]] = [
    (("UBER EATS",), "dining", 0.93),
    (("NETFLIX",), "subscriptions", 0.98),
    (("SPOTIFY",), "subscriptions", 0.97),
    (("HULU",), "subscriptions", 0.96),
    (("DISNEY",), "subscriptions", 0.95),
    (("BLUE BOTTLE",), "dining", 0.9),
    (("STARBUCKS",), "dining", 0.94),
    (("MCDONALD",), "dining", 0.94),
    (("CAFE",), "dining", 0.86),
    (("COFFEE",), "dining", 0.84),
    (("RESTAURANT",), "dining", 0.86),
    (("UBER",), "transport", 0.93),
    (("LYFT",), "transport", 0.93),
    (("METRO",), "transport", 0.9),
    (("TRANSIT",), "transport", 0.88),
    (("WHOLEFD",), "groceries", 0.92),
    (("TRADER JOE",), "groceries", 0.94),
    (("WALMART",), "groceries", 0.8),
    (("KROGER",), "groceries", 0.92),
    (("GROCERY",), "groceries", 0.9),
    (("MAPLE COURT",), "housing", 0.97),
    (("LANDLORD",), "housing", 0.95),
    (("RENT",), "housing", 0.9),
    (("TUITION",), "education", 0.97),
    (("BURSAR",), "education", 0.97),
    (("UNIVERSITY",), "education", 0.9),
    (("T MOBILE", "MOBILE"), "utilities", 0.96),
    (("VERIZON",), "utilities", 0.95),
    (("PHONE",), "utilities", 0.84),
    (("AMZN",), "shopping", 0.9),
    (("AMAZON",), "shopping", 0.9),
    (("ALLOWANCE",), "income", 0.97),
    (("STIPEND",), "income", 0.95),
    (("PAYROLL",), "income", 0.95),
    (("GOAL",), "savings", 0.9),
]


def merchant_key(merchant: str) -> str:
    text = (merchant or "").upper()
    text = re.sub(r"[0-9]+", " ", text)
    text = re.sub(r"[^A-Z]+", " ", text)
    parts = [part for part in text.split() if part not in _STOP and len(part) > 1]
    return " ".join(parts)


def categorize_text(merchant: str) -> tuple[str, float, str]:
    key = merchant_key(merchant)
    for keywords, category, confidence in RULES:
        if any(keyword in key for keyword in keywords):
            return category, confidence, "rule"
    return "other", 0.2, "rule"


def _correction_category(db: Session, user_id: int, merchant: str) -> str | None:
    key = merchant_key(merchant)
    if not key:
        return None
    row = (
        db.query(MerchantCorrection)
        .filter(MerchantCorrection.user_id == user_id, MerchantCorrection.merchant_key == key)
        .one_or_none()
    )
    return row.category if row else None


def categorize_merchant(
    db: Session,
    user_id: int,
    merchant: str,
    llm=None,
) -> tuple[str, float, str]:
    corrected = _correction_category(db, user_id, merchant)
    if corrected:
        return corrected, 1.0, "user"
    category, confidence, source = categorize_text(merchant)
    if category != "other" or llm is None:
        return category, confidence, source
    guessed = llm.categorize_merchant(merchant_key(merchant))
    if guessed in CATEGORIES and guessed != "other":
        return guessed, 0.62, "llm"
    return "other", 0.2, "rule"


def categorize_transactions(db: Session, user_id: int, transaction_ids: list[int], llm=None) -> list[dict]:
    account_ids = [row.id for row in _accounts(db, user_id)]
    results = []
    for txn_id in transaction_ids:
        txn = db.get(Transaction, txn_id)
        if txn is None or txn.account_id not in account_ids:
            results.append({"transaction_id": txn_id, "error": "not_found"})
            continue
        category, confidence, source = categorize_merchant(db, user_id, txn.merchant, llm=llm)
        txn.category = category
        txn.confidence = confidence
        txn.source = source
        results.append(
            {
                "transaction_id": txn.id,
                "category": category,
                "confidence": confidence,
                "source": source,
            }
        )
    db.commit()
    return results


def remember_correction(db: Session, user_id: int, merchant: str, category: str) -> str:
    if category not in CATEGORIES:
        raise ValueError("Unknown category")
    key = merchant_key(merchant)
    row = (
        db.query(MerchantCorrection)
        .filter(MerchantCorrection.user_id == user_id, MerchantCorrection.merchant_key == key)
        .one_or_none()
    )
    if row is None:
        row = MerchantCorrection(user_id=user_id, merchant_key=key, category=category)
        db.add(row)
    else:
        row.category = category
    account_ids = [account.id for account in _accounts(db, user_id)]
    if account_ids:
        for txn in db.query(Transaction).filter(Transaction.account_id.in_(account_ids)).all():
            if merchant_key(txn.merchant) == key:
                txn.category = category
                txn.confidence = 1.0
                txn.source = "user"
    db.commit()
    return key


def _accounts(db: Session, user_id: int):
    from app.models import Account

    return db.query(Account).filter(Account.user_id == user_id).all()
