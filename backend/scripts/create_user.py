"""Create or reset a user. Usage: uv run python scripts/create_user.py <email> <password> [display_name] [role]."""
from __future__ import annotations

import sys

from app.core.auth import UserService, hash_password
from app.core.database import session_factory_from_settings


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3] if len(sys.argv) > 3 else email.split("@")[0]
    role = sys.argv[4] if len(sys.argv) > 4 else "operator"

    service = UserService(session_factory_from_settings())
    existing = service.get_by_email(email)
    if existing is None:
        user = service.create_user(
            email=email, password=password, display_name=display_name, role=role
        )
        print(f"created user {user.id} {user.email} role={user.role}")
        return 0

    with service._session_factory() as session:  # noqa: SLF001
        existing.password_hash = hash_password(password)
        existing.display_name = display_name
        existing.role = role
        existing.is_active = True
        session.add(existing)
        session.commit()
    print(f"updated user {existing.id} {existing.email} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
