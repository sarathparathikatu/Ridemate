"""Admin tasks from the command line. Run from the backend folder (or inside the container):

    python -m app.cli make-admin you@example.com
    python -m app.cli revoke-admin you@example.com
    python -m app.cli list-admins

Admin rights are handed out here, by someone who can already reach the server, and never
through the API: no bug in an endpoint can then promote a stranger.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models import User
from app.services import admin_service
from app.services.errors import DomainError


async def run(args: argparse.Namespace) -> int:
    try:
        async with SessionLocal() as db:
            if args.command == "list-admins":
                admins = list(await db.scalars(select(User).where(User.is_admin).order_by(User.email)))
                for user in admins:
                    print(f"{user.email}  ({user.display_name})")
                if not admins:
                    print("No admins yet. Add one with: python -m app.cli make-admin EMAIL")
                return 0
            user = await admin_service.set_admin(db, args.email, args.command == "make-admin")
            state = "is now an admin" if user.is_admin else "is no longer an admin"
            print(f"{user.email} {state}.")
            return 0
    except DomainError as exc:
        print(exc.detail, file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="RideMate admin tasks")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("make-admin", "let this account review reports"),
        ("revoke-admin", "take admin rights away"),
    ):
        commands.add_parser(name, help=text).add_argument("email")
    commands.add_parser("list-admins", help="show who has admin rights")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
