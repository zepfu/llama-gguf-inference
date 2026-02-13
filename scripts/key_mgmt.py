#!/usr/bin/env python3
"""
key_mgmt.py - API Key Management CLI for llama-gguf-inference

Standalone CLI tool for managing API keys used by the gateway's authentication
system. Keys are stored in a flat file with the format: key_id:api_key

Usage:
    # Generate a new key
    python3 scripts/key_mgmt.py generate --name alice-laptop
    python3 scripts/key_mgmt.py generate --name alice-laptop --file /path/to/keys.txt

    # List configured keys (never shows actual key values)
    python3 scripts/key_mgmt.py list
    python3 scripts/key_mgmt.py list --file /path/to/keys.txt

    # Remove a key
    python3 scripts/key_mgmt.py remove --name alice-laptop

    # Rotate (regenerate) a key
    python3 scripts/key_mgmt.py rotate --name alice-laptop

    # Quiet mode for scripting (outputs only the key value)
    KEY=$(python3 scripts/key_mgmt.py generate --name foo --quiet)

Environment Variables:
    AUTH_KEYS_FILE  - Path to keys file (default: $DATA_DIR/api_keys.txt)
    DATA_DIR        - Base data directory (default: /data)

Keys File Format:
    key_id:api_key
    # Lines starting with '#' are comments
    # Blank lines are ignored
"""

import argparse
import os
import re
import secrets
import stat
import sys
import tempfile

# --- Constants ---

KEY_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
KEY_PREFIX = "sk-"


# --- Core Functions ---


def get_default_keys_file() -> str:
    """Return the default keys file path from environment variables."""
    return os.environ.get(
        "AUTH_KEYS_FILE",
        os.environ.get("DATA_DIR", "/data") + "/api_keys.txt",
    )


def validate_key_id(key_id: str) -> bool:
    """
    Validate that a key_id matches the required format.

    Rules: alphanumeric, hyphens, underscores. Length 1-64 characters.
    """
    return bool(KEY_ID_PATTERN.match(key_id))


def generate_api_key() -> str:
    """
    Generate a cryptographically secure API key.

    Format: sk- prefix + 43 base64url characters = 46 characters total.
    Uses secrets.token_urlsafe (CSPRNG) for key generation.
    """
    return KEY_PREFIX + secrets.token_urlsafe(32)


def load_keys_file(file_path: str) -> list[tuple[str, str, str]]:
    """
    Load all lines from the keys file, preserving structure.

    Returns a list of tuples: (line_type, key_id_or_empty, full_line)
    - ("key", key_id, original_line) for valid key lines
    - ("other", "", original_line) for comments, blanks, and invalid lines
    """
    entries: list[tuple[str, str, str]] = []

    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            stripped = line.rstrip("\n")
            trimmed = stripped.strip()

            if not trimmed or trimmed.startswith("#"):
                entries.append(("other", "", stripped))
                continue

            if ":" not in trimmed:
                entries.append(("other", "", stripped))
                continue

            parts = trimmed.split(":", 1)
            key_id = parts[0].strip()
            entries.append(("key", key_id, stripped))

    return entries


def find_key_id(entries: list[tuple[str, str, str]], key_id: str) -> int:
    """
    Find the index of a key_id in the entries list.

    Returns the index if found, -1 if not found.
    """
    for i, (line_type, entry_key_id, _) in enumerate(entries):
        if line_type == "key" and entry_key_id == key_id:
            return i
    return -1


def atomic_write(file_path: str, lines: list[str]) -> None:
    """
    Write lines to file atomically using temp file + rename.

    Writes to a temporary file in the same directory, then renames it
    to the target path. This prevents corruption if the process is
    interrupted mid-write.

    Sets file permissions to 0o600 (owner read/write only).
    """
    dir_path = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".keys_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            for line in lines:
                f.write(line + "\n")
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        os.replace(tmp_path, file_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def ensure_file_exists(file_path: str) -> None:
    """Create the keys file if it doesn't exist, with proper permissions."""
    if not os.path.exists(file_path):
        dir_path = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w") as f:
            f.write("# API Keys - format: key_id:api_key\n")
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600


# --- Command Implementations ---


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a new API key and append it to the keys file."""
    key_id = args.name
    file_path = args.file
    quiet = args.quiet

    # Validate key_id format
    if not validate_key_id(key_id):
        print(
            f"Error: Invalid key name '{key_id}'. "
            "Must be 1-64 characters, alphanumeric, hyphens, or underscores.",
            file=sys.stderr,
        )
        return 1

    # Ensure file exists
    ensure_file_exists(file_path)

    # Check for duplicate key_id
    entries = load_keys_file(file_path)
    if find_key_id(entries, key_id) != -1:
        print(f"Error: Key '{key_id}' already exists. Use 'rotate' to regenerate.", file=sys.stderr)
        return 1

    # Generate the key
    api_key = generate_api_key()

    # Append the new key entry
    entries.append(("key", key_id, f"{key_id}:{api_key}"))

    # Write atomically
    lines = [entry[2] for entry in entries]
    atomic_write(file_path, lines)

    # Output
    if quiet:
        print(api_key)
    else:
        print(f"Generated key for '{key_id}': {api_key}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all configured API keys (shows key_ids only, never key values)."""
    file_path = args.file

    if not os.path.exists(file_path):
        if not args.quiet:
            print("No keys file found.")
            print(f"  Expected: {file_path}")
            print("  Use 'generate' to create the first key.")
        print("0 key(s) configured")
        return 0

    entries = load_keys_file(file_path)
    key_entries = [(key_id, line) for line_type, key_id, line in entries if line_type == "key"]

    if not args.quiet:
        print(f"{'KEY_ID':<20} {'CREATED':<12} {'STATUS'}")
        for key_id, _ in key_entries:
            print(f"{key_id:<20} {'-':<12} {'active'}")

    print(f"{len(key_entries)} key(s) configured")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a key by its key_id."""
    key_id = args.name
    file_path = args.file

    if not os.path.exists(file_path):
        print(f"Error: Keys file not found: {file_path}", file=sys.stderr)
        return 1

    entries = load_keys_file(file_path)
    idx = find_key_id(entries, key_id)

    if idx == -1:
        print(f"Error: Key '{key_id}' not found.", file=sys.stderr)
        return 1

    # Remove the entry
    entries.pop(idx)

    # Write atomically
    lines = [entry[2] for entry in entries]
    atomic_write(file_path, lines)

    if not args.quiet:
        print(f"Removed key '{key_id}'.")

    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """Rotate (regenerate) the API key for an existing key_id."""
    key_id = args.name
    file_path = args.file
    quiet = args.quiet

    if not os.path.exists(file_path):
        print(f"Error: Keys file not found: {file_path}", file=sys.stderr)
        return 1

    entries = load_keys_file(file_path)
    idx = find_key_id(entries, key_id)

    if idx == -1:
        print(f"Error: Key '{key_id}' not found.", file=sys.stderr)
        return 1

    # Generate new key
    new_api_key = generate_api_key()

    # Replace the entry
    entries[idx] = ("key", key_id, f"{key_id}:{new_api_key}")

    # Write atomically
    lines = [entry[2] for entry in entries]
    atomic_write(file_path, lines)

    # Output
    if quiet:
        print(new_api_key)
    else:
        print(f"Rotated key for '{key_id}': {new_api_key}")

    return 0


# --- CLI Setup ---


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the key management CLI."""
    parser = argparse.ArgumentParser(
        prog="key_mgmt",
        description="API Key Management CLI for llama-gguf-inference",
    )

    parser.add_argument(
        "--file",
        default=get_default_keys_file(),
        help="Path to API keys file (default: $AUTH_KEYS_FILE or $DATA_DIR/api_keys.txt)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output except generated/rotated key values (useful for scripting)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate a new API key")
    gen_parser.add_argument("--name", required=True, help="Key identifier (key_id)")

    # list
    subparsers.add_parser("list", help="List configured keys")

    # remove
    rm_parser = subparsers.add_parser("remove", help="Remove a key by key_id")
    rm_parser.add_argument("--name", required=True, help="Key identifier to remove")

    # rotate
    rot_parser = subparsers.add_parser("rotate", help="Rotate (regenerate) a key")
    rot_parser.add_argument("--name", required=True, help="Key identifier to rotate")

    return parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "generate": cmd_generate,
        "list": cmd_list,
        "remove": cmd_remove,
        "rotate": cmd_rotate,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
