from apps.accounts.permissions import IsOwnStudent


class StudentProfileAccessPending(IsOwnStudent):
    """Compatibility name for the authenticated, owner-only profile policy."""
