"""Authentication and authorization services."""

import time
from typing import Dict, List
from collections import defaultdict, deque


class RateLimiter:
    """Simple in-memory rate limiter using sliding window algorithm."""

    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per user
        """
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, user_id: str) -> bool:
        """Check if a request is allowed for the given user.

        Args:
            user_id: Unique identifier for the user

        Returns:
            True if request is allowed, False otherwise
        """
        current_time = time.time()
        user_requests = self._requests[user_id]

        # Remove requests older than 1 minute
        one_minute_ago = current_time - 60
        while user_requests and user_requests[0] < one_minute_ago:
            user_requests.popleft()

        # Check if under limit
        if len(user_requests) < self.requests_per_minute:
            user_requests.append(current_time)
            return True

        return False

    def get_remaining(self, user_id: str) -> int:
        """Get remaining requests for a user.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Number of remaining requests in the current window
        """
        current_time = time.time()
        user_requests = self._requests[user_id]

        # Remove requests older than 1 minute
        one_minute_ago = current_time - 60
        while user_requests and user_requests[0] < one_minute_ago:
            user_requests.popleft()

        return max(0, self.requests_per_minute - len(user_requests))
