"""
Encryption Utilities

This module provides utilities for encryption key management:
- Generate secure encryption keys
- Save keys to files
- Load keys from files
"""

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        str: A base64-encoded encryption key

    Example:
        >>> key = generate_encryption_key()
        >>> print(f"Generated key: {key}")
    """
    key = Fernet.generate_key()
    return key.decode()


def generate_and_save_key(filepath: str, overwrite: bool = False) -> str:
    """
    Generate a new encryption key and save it to a file.

    Args:
        filepath: Path where the key file should be saved
        overwrite: If True, overwrite existing key file. If False, raise error if file exists.

    Returns:
        str: The generated encryption key

    Raises:
        FileExistsError: If file exists and overwrite is False

    Example:
        >>> key = generate_and_save_key('.env.key')
        >>> print(f"Key saved to .env.key")
    """
    filepath = Path(filepath)

    if filepath.exists() and not overwrite:
        raise FileExistsError(
            f"Key file already exists at {filepath}. "
            "Use overwrite=True to replace it."
        )

    key = generate_encryption_key()

    # Create parent directories if they don't exist
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write key to file with restricted permissions
    with open(filepath, "w") as f:
        f.write(key)

    # Set file permissions to read/write for owner only (Unix-like systems)
    try:
        os.chmod(filepath, 0o600)
    except Exception:
        # Windows or other systems that don't support chmod
        pass

    print(f"Encryption key generated and saved to: {filepath}")
    return key


def load_key_from_file(filepath: str) -> str:
    """
    Load an encryption key from a file.

    Args:
        filepath: Path to the key file

    Returns:
        str: The encryption key

    Raises:
        FileNotFoundError: If the key file doesn't exist
        ValueError: If the key file is empty or invalid

    Example:
        >>> key = load_key_from_file('.env.key')
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"Key file not found at {filepath}")

    with open(filepath, "r") as f:
        key = f.read().strip()

    if not key:
        raise ValueError(f"Key file at {filepath} is empty")

    # Validate that it's a valid Fernet key
    try:
        Fernet(key.encode())
    except Exception as e:
        raise ValueError(f"Invalid encryption key in {filepath}: {str(e)}")

    return key


def get_or_generate_key(
    env_var: str = "DB_PASSWORD_ENCRYPTION_KEY",
    key_file: Optional[str] = None,
    auto_generate: bool = False,
) -> str:
    """
    Get encryption key from environment variable, file, or generate new one.

    Priority order:
    1. Environment variable (if set)
    2. Key file (if provided and exists)
    3. Auto-generate (if enabled)

    Args:
        env_var: Environment variable name to check
        key_file: Optional path to key file
        auto_generate: If True, generate a new key if not found elsewhere

    Returns:
        str: The encryption key

    Raises:
        ValueError: If no key is found and auto_generate is False

    Example:
        >>> # Try env var first, then .env.key file, then auto-generate
        >>> key = get_or_generate_key(
        ...     env_var="DB_PASSWORD_ENCRYPTION_KEY",
        ...     key_file=".env.key",
        ...     auto_generate=True
        ... )
    """
    # Try environment variable first
    key = os.getenv(env_var)
    if key:
        print(f"Using encryption key from environment variable: {env_var}")
        return key

    # Try key file if provided
    if key_file:
        try:
            key = load_key_from_file(key_file)
            print(f"Using encryption key from file: {key_file}")
            return key
        except FileNotFoundError:
            pass

    # Auto-generate if enabled
    if auto_generate:
        key = generate_encryption_key()
        print("WARNING: Using auto-generated encryption key.")
        print("This should only be used in development!")
        print("Set the key in environment variable or key file for production.")
        return key

    raise ValueError(
        f"No encryption key found. Please set {env_var} environment variable "
        f"or provide a key file."
    )


def print_key_setup_instructions(key: str, env_var: str = "DB_PASSWORD_ENCRYPTION_KEY"):
    """
    Print instructions for setting up the encryption key in production.

    Args:
        key: The encryption key to use
        env_var: Environment variable name
    """
    print("\n" + "=" * 70)
    print("ENCRYPTION KEY SETUP INSTRUCTIONS")
    print("=" * 70)
    print("\nYour encryption key:")
    print(f"  {key}")
    print("\nTo use this key in production, add it to your environment:")
    print(f"\n  export {env_var}='{key}'")
    print("\nOr add to your .env file:")
    print(f"\n  {env_var}={key}")
    print("\nOr save to a secure key file:")
    print(f"\n  echo '{key}' > .env.key")
    print("  chmod 600 .env.key")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    """
    CLI tool for generating encryption keys.

    Usage:
        python -m utilities.encryption
        python -m utilities.encryption --save .env.key
        python -m utilities.encryption --save .env.key --overwrite
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate encryption keys for database password encryption"
    )
    parser.add_argument("--save", type=str, help="Save the generated key to a file")
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing key file"
    )
    parser.add_argument(
        "--env-var",
        type=str,
        default="DB_PASSWORD_ENCRYPTION_KEY",
        help="Environment variable name (default: DB_PASSWORD_ENCRYPTION_KEY)",
    )

    args = parser.parse_args()

    if args.save:
        try:
            key = generate_and_save_key(args.save, overwrite=args.overwrite)
            print_key_setup_instructions(key, args.env_var)
        except FileExistsError as e:
            print(f"Error: {e}")
            exit(1)
    else:
        key = generate_encryption_key()
        print_key_setup_instructions(key, args.env_var)
