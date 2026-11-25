import argparse
import getpass
import re
import sqlite3

from .database.connection import init_db
from .database.queries import add_user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision a faculty account without exposing a public faculty signup."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--department", default="")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        parser.error("--email must be a valid email address")

    password = getpass.getpass("Faculty password (8-128 characters): ")
    if not 8 <= len(password) <= 128:
        parser.error("Password must be between 8 and 128 characters")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match")

    init_db()
    try:
        add_user(
            email=email,
            password=password,
            role="faculty",
            name=args.name.strip(),
            department=args.department.strip(),
        )
    except sqlite3.IntegrityError as error:
        parser.error(f"An account already exists for {email}: {error}")
    print(f"Faculty account provisioned for {email}")


if __name__ == "__main__":
    main()
