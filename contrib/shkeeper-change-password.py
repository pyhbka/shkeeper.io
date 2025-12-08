#!/usr/bin/env python3
"""
SHKeeper Password Change Script

This script changes the admin password in the SHKeeper database.
It uses SQLAlchemy to connect to MySQL database with the same
environment variables as the main application.

Requirements:
    pip install bcrypt sqlalchemy pymysql

Environment Variables:
    MYSQL_HOST     - MySQL server host (default: localhost)
    MYSQL_PORT     - MySQL server port (default: 3306)
    MYSQL_USER     - MySQL username (default: shkeeper)
    MYSQL_PASSWORD - MySQL password (required)
    MYSQL_DATABASE - MySQL database name (default: shkeeper)

Usage:
    export MYSQL_HOST=localhost
    export MYSQL_USER=shkeeper
    export MYSQL_PASSWORD=your_password
    export MYSQL_DATABASE=shkeeper
    python3 shkeeper-change-password.py
"""

import bcrypt
import getpass
import os
import sys
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class User(Base):
    """User model matching the SHKeeper database schema"""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    passhash = Column(String(120))
    api_key = Column(String(255))


def get_password_hash(password):
    """
    Generate bcrypt hash for password.
    Returns string (not bytes) for MySQL compatibility.
    """
    hash_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
    return hash_bytes.decode('utf-8')


def get_database_uri():
    """Build MySQL connection URI from environment variables"""
    mysql_host = os.environ.get("MYSQL_HOST", "localhost")
    mysql_port = os.environ.get("MYSQL_PORT", "3306")
    mysql_user = os.environ.get("MYSQL_USER", "shkeeper")
    mysql_password = os.environ.get("MYSQL_PASSWORD", "")
    mysql_database = os.environ.get("MYSQL_DATABASE", "shkeeper")

    if not mysql_password:
        print("ERROR: MYSQL_PASSWORD environment variable is not set!")
        print("Please set it with: export MYSQL_PASSWORD=your_password")
        sys.exit(1)

    return f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"


def main():
    """Main function to change admin password"""
    print("=" * 60)
    print("SHKeeper Password Change Utility")
    print("=" * 60)
    print()

    # Get database connection
    try:
        database_uri = get_database_uri()
        engine = create_engine(database_uri, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        print(f"✓ Connected to MySQL database")
        print()
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        print()
        print("Please check your MySQL connection settings:")
        print(f"  MYSQL_HOST: {os.environ.get('MYSQL_HOST', 'localhost')}")
        print(f"  MYSQL_PORT: {os.environ.get('MYSQL_PORT', '3306')}")
        print(f"  MYSQL_USER: {os.environ.get('MYSQL_USER', 'shkeeper')}")
        print(f"  MYSQL_DATABASE: {os.environ.get('MYSQL_DATABASE', 'shkeeper')}")
        sys.exit(1)

    # Get admin user
    try:
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            print("✗ Admin user not found in database!")
            session.close()
            sys.exit(1)
        print(f"✓ Found admin user (ID: {admin.id})")
        print()
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        session.close()
        sys.exit(1)

    # Password change loop
    changed = False
    attempts = 0
    max_attempts = 3

    while not changed and attempts < max_attempts:
        attempts += 1
        try:
            print(f"Enter new password (attempt {attempts}/{max_attempts}):")
            pass1 = getpass.getpass(prompt='Password: ')
            pass2 = getpass.getpass(prompt='Confirm password: ')
        except KeyboardInterrupt:
            print()
            print("Password change cancelled by user.")
            session.close()
            sys.exit(0)

        # Validate passwords
        if not pass1 or not pass2:
            print("✗ Password cannot be empty!")
            print()
            continue

        if pass1 != pass2:
            print("✗ Passwords do not match!")
            print()
            continue

        if len(pass1) < 6:
            print("✗ Password must be at least 6 characters long!")
            print()
            continue

        # Update password
        try:
            print("Generating password hash...")
            admin.passhash = get_password_hash(pass1)
            session.commit()
            changed = True
            print()
            print("=" * 60)
            print("✓ Password successfully changed!")
            print("=" * 60)
        except Exception as e:
            print(f"✗ Failed to update password: {e}")
            session.rollback()

    # Cleanup
    session.close()

    if not changed:
        print()
        print("✗ Maximum attempts reached. Password not changed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
