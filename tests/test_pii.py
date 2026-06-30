from finsight_common.pii import Redactor, redact_text


def _r(text: str) -> str:
    # Force the deterministic regex fallback so tests don't depend on spaCy/presidio.
    return Redactor(use_presidio=False).redact(text)


def test_redacts_email():
    assert "<EMAIL>" in _r("pay ramesh@okhdfcbank now")
    assert "ramesh@okhdfcbank" not in _r("pay ramesh@okhdfcbank now")


def test_redacts_phone():
    assert "<PHONE>" in _r("call 9876543210")
    assert "<PHONE>" in _r("call +91 9876543210")


def test_redacts_pan():
    assert "<PAN>" in _r("PAN ABCDE1234F on file")


def test_redacts_aadhaar():
    assert "<AADHAAR>" in _r("uid 1234 5678 9012")


def test_redacts_card_number():
    assert "<CARD>" in _r("card 4111 1111 1111 1111 charged")


def test_default_redactor_callable():
    # The module-level helper should not raise regardless of presidio availability.
    assert isinstance(redact_text("hello 9876543210"), str)
