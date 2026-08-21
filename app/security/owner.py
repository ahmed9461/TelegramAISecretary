from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OwnerGuard:
    owner_telegram_id: int

    def is_owner(self, telegram_user_id: int | None) -> bool:
        return telegram_user_id is not None and telegram_user_id == self.owner_telegram_id

    def require_owner(self, telegram_user_id: int | None) -> None:
        if not self.is_owner(telegram_user_id):
            raise PermissionError("owner_only")
