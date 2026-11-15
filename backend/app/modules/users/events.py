"""Events of the people administration (ids only in every payload)."""

from typing import Final

# A self-registered account waits for approval (plan M9 task 5b): payload `user_id`;
# `users/handlers.py` tells everyone who holds `user.manage`.
USER_SIGNUP_PENDING: Final = "user.signup_pending"
