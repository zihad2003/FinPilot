"""Hybrid categorization, including messy merchant strings."""

import pytest

from agent.categorize import categorize_merchant, categorize_text, merchant_key

CASES = [
    ("NETFLIX.COM", "subscriptions"),
    ("NETFLIX COM", "subscriptions"),
    ("SPOTIFY USA", "subscriptions"),
    ("SPOTIFY P1A2B3C4", "subscriptions"),
    ("HULU *SUBSCR", "subscriptions"),
    ("DISNEY PLUS", "subscriptions"),
    ("UBER *TRIP 8842", "transport"),
    ("UBER *EATS 19", "dining"),
    ("LYFT *RIDE 2201", "transport"),
    ("METRO TRANSIT", "transport"),
    ("MAPLE COURT APTS RENT", "housing"),
    ("LANDLORD RENT", "housing"),
    ("WHOLEFDS MKT #104", "groceries"),
    ("TRADER JOE'S #512", "groceries"),
    ("WALMART GROCERY", "groceries"),
    ("KROGER #889", "groceries"),
    ("STATE UNIVERSITY BURSAR", "education"),
    ("TUITION PAYMENT", "education"),
    ("T-MOBILE*BILL", "utilities"),
    ("VERIZON WIRELESS", "utilities"),
    ("PHONE BILL", "utilities"),
    ("STARBUCKS STORE 221", "dining"),
    ("MCDONALD'S F123", "dining"),
    ("CAMPUS CAFE", "dining"),
    ("SQ *BLUE BOTTLE 8831", "dining"),
    ("INTL STUDENT ALLOWANCE", "income"),
    ("PAYROLL ALLOWANCE", "income"),
    ("AMZN MARKETPLACE", "shopping"),
    ("GOAL Emergency fund", "savings"),
    ("QQX NIGHT MARKET", "other"),
]


@pytest.mark.parametrize("merchant,expected", CASES)
def test_messy_merchants(merchant, expected):
    category, confidence, source = categorize_text(merchant)
    assert category == expected
    assert source == "rule"
    assert 0 < confidence <= 1
    assert merchant_key(merchant)


def test_user_correction_overrides_rule(session):
    from agent.categorize import remember_correction

    remember_correction(session, 1, "NETFLIX.COM", "dining")
    category, confidence, source = categorize_merchant(session, 1, "NETFLIX.COM 9981")
    assert (category, confidence, source) == ("dining", 1.0, "user")


def test_llm_fallback_for_unknown_merchant(session):
    class Stub:
        def categorize_merchant(self, key):
            return "groceries"

    category, confidence, source = categorize_merchant(session, 1, "QQX NIGHT MARKET", llm=Stub())
    assert (category, source) == ("groceries", "llm")
    assert confidence == 0.62
