from __future__ import annotations

import pytest
from fastapi import HTTPException

from cookdex.webui_server.rate_limit import ActionRateLimiter, LoginRateLimiter


class TestLoginRateLimiter:
    def test_allows_under_limit(self):
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
        limiter.check("10.0.0.1", "user1")
        limiter.record_failure("10.0.0.1", "user1")
        limiter.record_failure("10.0.0.1", "user1")
        limiter.check("10.0.0.1", "user1")  # Should still pass (2 failures, limit is 3)

    def test_blocks_at_limit(self):
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)
        limiter.record_failure("10.0.0.1", "user1")
        limiter.record_failure("10.0.0.1", "user1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("10.0.0.1", "user1")
        assert exc_info.value.status_code == 429

    def test_clear_resets_count(self):
        limiter = LoginRateLimiter(max_attempts=1, window_seconds=60)
        limiter.record_failure("10.0.0.1", "user1")
        limiter.clear("10.0.0.1", "user1")
        limiter.check("10.0.0.1", "user1")  # Should pass after clear

    def test_separate_keys_are_independent(self):
        limiter = LoginRateLimiter(max_attempts=1, window_seconds=60)
        limiter.record_failure("10.0.0.1", "user1")
        limiter.check("10.0.0.2", "user2")  # Different key, should pass

    def test_ip_bucket_still_caps_credential_stuffing(self):
        """Spraying many usernames from one IP is capped by the IP bucket."""
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60, ip_max_attempts=5)
        for i in range(5):
            limiter.record_failure("10.0.0.1", f"user{i}")
        with pytest.raises(HTTPException):
            limiter.check("10.0.0.1", "user99")

    def test_shared_proxy_ip_does_not_lock_out_other_users(self):
        """Behind a reverse proxy every request shares one client IP."""
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)
        limiter.record_failure("10.0.0.1", "victim")
        limiter.record_failure("10.0.0.1", "victim")

        with pytest.raises(HTTPException):
            limiter.check("10.0.0.1", "victim")

        # A different account from the same proxy IP is still allowed in.
        limiter.check("10.0.0.1", "bystander")

    def test_username_bucket_survives_rotating_ips(self):
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)
        limiter.record_failure("10.0.0.1", "victim")
        limiter.record_failure("10.0.0.2", "victim")

        with pytest.raises(HTTPException):
            limiter.check("10.0.0.3", "victim")

    def test_username_matching_is_case_insensitive(self):
        limiter = LoginRateLimiter(max_attempts=1, window_seconds=60)
        limiter.record_failure("10.0.0.1", "Victim")
        with pytest.raises(HTTPException):
            limiter.check("10.0.0.2", "victim")

    def test_expired_buckets_are_swept(self):
        limiter = LoginRateLimiter(max_attempts=5, window_seconds=0)
        limiter.record_failure("10.0.0.1", "someone")
        assert limiter._attempts
        limiter.check("10.0.0.2", "another")
        # Only the buckets touched by the latest check remain.
        assert "ip:10.0.0.1" not in limiter._attempts
        assert "user:someone" not in limiter._attempts


class TestActionRateLimiter:
    def test_allows_under_limit(self):
        limiter = ActionRateLimiter(max_per_minute=5)
        for _ in range(5):
            limiter.check("user1")

    def test_blocks_over_limit(self):
        limiter = ActionRateLimiter(max_per_minute=3)
        limiter.check("user1")
        limiter.check("user1")
        limiter.check("user1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user1")
        assert exc_info.value.status_code == 429

    def test_separate_keys_are_independent(self):
        limiter = ActionRateLimiter(max_per_minute=1)
        limiter.check("user1")
        limiter.check("user2")  # Different key, should pass
