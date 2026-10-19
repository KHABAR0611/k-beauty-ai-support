from pathlib import Path
import runpy


def test_docker_failure_diagnostics_remove_keys_credentials_and_signed_url_queries():
    root = Path(__file__).resolve().parents[2]
    sanitize = runpy.run_path(str(root / "infrastructure/verify_qdrant.py"))["safe_diagnostic"]
    message = 'Get "https://user:password@cdn.example/data?Signature=secret&Expires=123": EOF; key=local-test-key'
    result = sanitize(message, "local-test-key")
    assert result == 'Get "https://cdn.example/data?[redacted]": EOF; key=[redacted]'
    assert not any(s in result for s in ["password", "Signature", "local-test-key"])
