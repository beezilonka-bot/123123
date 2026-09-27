from radar.collector import canonicalize_url, raw_hash


def test_canonicalize_removes_tracking_params():
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&id=7#frag") == "https://example.com/a?id=7"


def test_hash_is_deterministic():
    assert raw_hash("Hello", "https://example.com/a") == raw_hash("Hello", "https://example.com/a")
