#!/usr/bin/env python3
"""
Standalone script to generate encryption keys for the application.

This script can be run directly without any dependencies other than cryptography.

Usage:
    python generate_encryption_key.py
    python generate_encryption_key.py --save .env.key
    python generate_encryption_key.py --save .env.key --overwrite
"""

if __name__ == "__main__":
    from utilities.encryption import (
        generate_encryption_key,
        generate_and_save_key,
        print_key_setup_instructions,
    )
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate encryption keys for database password encryption",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate and display a key
  python generate_encryption_key.py
  
  # Generate and save to file
  python generate_encryption_key.py --save .env.key
  
  # Overwrite existing key file
  python generate_encryption_key.py --save .env.key --overwrite
        """,
    )
    parser.add_argument(
        "--save", type=str, metavar="FILE", help="Save the generated key to a file"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing key file"
    )
    parser.add_argument(
        "--env-var",
        type=str,
        default="DB_PASSWORD_ENCRYPTION_KEY",
        metavar="NAME",
        help="Environment variable name (default: DB_PASSWORD_ENCRYPTION_KEY)",
    )

    args = parser.parse_args()

    try:
        if args.save:
            key = generate_and_save_key(args.save, overwrite=args.overwrite)
            print_key_setup_instructions(key, args.env_var)
        else:
            key = generate_encryption_key()
            print_key_setup_instructions(key, args.env_var)
    except FileExistsError as e:
        print(f"\nError: {e}\n")
        print("Use --overwrite flag to replace the existing key file.")
        exit(1)
    except Exception as e:
        print(f"\nError: {e}\n")
        exit(1)
