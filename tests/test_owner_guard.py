import pytest

from app.security.owner import OwnerGuard


def test_owner_guard() -> None:
    guard = OwnerGuard(123)
    assert guard.is_owner(123)
    assert not guard.is_owner(321)
    with pytest.raises(PermissionError):
        guard.require_owner(321)
