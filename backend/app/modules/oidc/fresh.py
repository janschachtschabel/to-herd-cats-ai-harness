"""A fresh sign-in at the provider as the proof before linking (ASVS 5.0 V7.5.1, J9,
review M9b Task 18 R18-10).

A person without a password proves herself before linking a new account by signing in
again through a provider she already uses. That sign-in asks the provider for a login
of its own (`prompt=login`) no older than `MAX_AGE` (`max_age`); when the ID token says
when the person authenticated (`auth_time`), only a time within `MAX_AGE` counts. Any
other provider sign-in opens a session that does not count as re-authenticated: a
silent sign-in on a live provider session proves nothing."""

from datetime import datetime

from app.modules.auth.reauth import WINDOW
from app.modules.oidc.id_token import IdClaims

MAX_AGE = WINDOW  # 10 minutes, the window the proof then holds
PARAMETERS = {"prompt": "login", "max_age": str(int(MAX_AGE.total_seconds()))}
STALE = "oidc.reauth_stale"


def recent(claims: IdClaims, now: datetime) -> bool:
    """The provider's login is within `MAX_AGE` of `now`, or it does not say when."""
    if claims.auth_time is None:
        return True
    age = now.timestamp() - claims.auth_time
    return age <= MAX_AGE.total_seconds()
