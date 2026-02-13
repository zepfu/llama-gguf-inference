"""Unit tests for scripts/key_mgmt.py - API Key Management CLI."""

import argparse
import os
import stat
import subprocess
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import key_mgmt  # noqa: E402


@pytest.fixture
def keys_file(tmp_path):
    """Create a temporary keys file with two test keys."""
    path = tmp_path / "api_keys.txt"
    path.write_text(
        "# Test keys\n"
        "alice-laptop:sk-test-AAAAAAAAAAAAAAAAAAAAAAAAAAAAaaaa\n"
        "production-key:sk-test-BBBBBBBBBBBBBBBBBBBBBBBBBBBBbbbb\n"
    )
    return str(path)


@pytest.fixture
def empty_keys_file(tmp_path):
    """Create an empty keys file."""
    path = tmp_path / "api_keys.txt"
    path.write_text("")
    return str(path)


class TestValidateKeyId:
    """Tests for key_id format validation."""

    def test_valid_alphanumeric(self):
        """Alphanumeric key_id is valid."""
        assert key_mgmt.validate_key_id("alice123") is True

    def test_valid_with_hyphens(self):
        """Key_id with hyphens is valid."""
        assert key_mgmt.validate_key_id("alice-laptop") is True

    def test_valid_with_underscores(self):
        """Key_id with underscores is valid."""
        assert key_mgmt.validate_key_id("alice_laptop") is True

    def test_valid_mixed(self):
        """Key_id with mixed characters is valid."""
        assert key_mgmt.validate_key_id("prod-key_01") is True

    def test_valid_single_char(self):
        """Single character key_id is valid."""
        assert key_mgmt.validate_key_id("a") is True

    def test_valid_max_length(self):
        """64-character key_id is valid (max length)."""
        assert key_mgmt.validate_key_id("a" * 64) is True

    def test_invalid_empty(self):
        """Empty string is not a valid key_id."""
        assert key_mgmt.validate_key_id("") is False

    def test_invalid_too_long(self):
        """65-character key_id exceeds max length."""
        assert key_mgmt.validate_key_id("a" * 65) is False

    def test_invalid_special_chars(self):
        """Special characters like @ are rejected."""
        assert key_mgmt.validate_key_id("alice@laptop") is False

    def test_invalid_spaces(self):
        """Spaces are rejected."""
        assert key_mgmt.validate_key_id("alice laptop") is False

    def test_invalid_dots(self):
        """Dots are rejected."""
        assert key_mgmt.validate_key_id("alice.laptop") is False

    def test_invalid_colon(self):
        """Colons are rejected."""
        assert key_mgmt.validate_key_id("alice:laptop") is False


class TestGenerateApiKey:
    """Tests for API key generation."""

    def test_starts_with_prefix(self):
        """Generated key starts with sk- prefix."""
        key = key_mgmt.generate_api_key()
        assert key.startswith("sk-")

    def test_correct_length(self):
        """Generated key is 46 characters (3 prefix + 43 base64url)."""
        key = key_mgmt.generate_api_key()
        assert len(key) == 46

    def test_unique_keys(self):
        """100 generated keys are all unique."""
        keys = {key_mgmt.generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_valid_characters(self):
        """Key suffix uses only base64url characters."""
        key = key_mgmt.generate_api_key()
        suffix = key[3:]
        assert all(c.isalnum() or c in "-_" for c in suffix)


class TestGenerate:
    """Tests for the generate command."""

    def test_generate_creates_key(self, tmp_path):
        """Generate creates a valid key and appends to file."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="test-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_generate(args)
        assert result == 0
        assert os.path.exists(file_path)
        content = open(file_path).read()
        assert "test-key:" in content
        assert "sk-" in content
        lines = [line for line in content.strip().split("\n") if line.strip()]
        key_lines = [line for line in lines if not line.startswith("#")]
        assert len(key_lines) == 1

    def test_generate_duplicate_name_fails(self, keys_file):
        """Generate rejects duplicate key_id."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_generate(args)
        assert result == 1

    def test_generate_invalid_name_fails(self, tmp_path):
        """Generate rejects key_id with special characters."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="bad@name!", file=file_path, quiet=False)
        result = key_mgmt.cmd_generate(args)
        assert result == 1
        assert not os.path.exists(file_path)

    def test_generate_quiet_mode(self, tmp_path, capsys):
        """Quiet mode outputs only the key value."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="quiet-key", file=file_path, quiet=True)
        result = key_mgmt.cmd_generate(args)
        assert result == 0
        captured = capsys.readouterr()
        output = captured.out.strip()
        assert output.startswith("sk-")
        assert "Generated" not in output

    def test_generate_preserves_comments(self, keys_file):
        """Generate preserves existing comments and keys."""
        args = argparse.Namespace(name="new-key", file=keys_file, quiet=False)
        key_mgmt.cmd_generate(args)
        content = open(keys_file).read()
        assert "# Test keys" in content
        assert "alice-laptop:" in content
        assert "production-key:" in content
        assert "new-key:" in content


class TestList:
    """Tests for the list command."""

    def test_list_empty_file(self, empty_keys_file, capsys):
        """Empty file shows 0 keys."""
        args = argparse.Namespace(file=empty_keys_file, quiet=False)
        result = key_mgmt.cmd_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "0 key(s) configured" in captured.out

    def test_list_with_keys(self, keys_file, capsys):
        """Shows correct key_ids and count."""
        args = argparse.Namespace(file=keys_file, quiet=False)
        result = key_mgmt.cmd_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "alice-laptop" in captured.out
        assert "production-key" in captured.out
        assert "2 key(s) configured" in captured.out
        assert "KEY_ID" in captured.out
        assert "active" in captured.out

    def test_list_never_shows_key_values(self, keys_file, capsys):
        """List never displays actual API key values."""
        args = argparse.Namespace(file=keys_file, quiet=False)
        key_mgmt.cmd_list(args)
        captured = capsys.readouterr()
        assert "sk-test-AAAA" not in captured.out
        assert "sk-test-BBBB" not in captured.out

    def test_list_missing_file(self, tmp_path, capsys):
        """Missing file shows 0 keys with helpful message."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(file=file_path, quiet=False)
        result = key_mgmt.cmd_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "0 key(s) configured" in captured.out


class TestRemove:
    """Tests for the remove command."""

    def test_remove_existing_key(self, keys_file):
        """Remove deletes the correct key line."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_remove(args)
        assert result == 0
        content = open(keys_file).read()
        assert "alice-laptop" not in content
        assert "production-key" in content

    def test_remove_nonexistent_fails(self, keys_file):
        """Remove fails for a key_id that does not exist."""
        args = argparse.Namespace(name="nonexistent", file=keys_file, quiet=False)
        result = key_mgmt.cmd_remove(args)
        assert result == 1

    def test_remove_preserves_comments(self, keys_file):
        """Remove preserves comments and other keys."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_remove(args)
        content = open(keys_file).read()
        assert "# Test keys" in content

    def test_remove_missing_file_fails(self, tmp_path):
        """Remove fails if keys file does not exist."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(name="any-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_remove(args)
        assert result == 1


class TestRotate:
    """Tests for the rotate command."""

    def test_rotate_existing_key(self, keys_file):
        """Rotate changes the api_key but keeps the key_id."""
        original_content = open(keys_file).read()
        original_line = [
            line for line in original_content.split("\n") if line.startswith("alice-laptop:")
        ][0]
        original_api_key = original_line.split(":", 1)[1]
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_rotate(args)
        assert result == 0
        new_content = open(keys_file).read()
        new_line = [line for line in new_content.split("\n") if line.startswith("alice-laptop:")][0]
        new_api_key = new_line.split(":", 1)[1]
        assert "alice-laptop:" in new_content
        assert new_api_key != original_api_key
        assert new_api_key.startswith("sk-")

    def test_rotate_nonexistent_fails(self, keys_file):
        """Rotate fails for a key_id that does not exist."""
        args = argparse.Namespace(name="nonexistent", file=keys_file, quiet=False)
        result = key_mgmt.cmd_rotate(args)
        assert result == 1

    def test_rotate_quiet_mode(self, keys_file, capsys):
        """Quiet mode outputs only the new key value."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=True)
        result = key_mgmt.cmd_rotate(args)
        assert result == 0
        captured = capsys.readouterr()
        output = captured.out.strip()
        assert output.startswith("sk-")
        assert "Rotated" not in output

    def test_rotate_preserves_other_keys(self, keys_file):
        """Rotate does not modify other keys."""
        original_content = open(keys_file).read()
        prod_line = [
            line for line in original_content.split("\n") if line.startswith("production-key:")
        ][0]
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_rotate(args)
        new_content = open(keys_file).read()
        assert prod_line in new_content

    def test_rotate_missing_file_fails(self, tmp_path):
        """Rotate fails if keys file does not exist."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(name="any-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_rotate(args)
        assert result == 1


class TestFilePermissions:
    """Tests for file permission security."""

    def test_file_permissions_after_generate(self, tmp_path):
        """File has 0o600 permissions after generate."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="test-key", file=file_path, quiet=True)
        key_mgmt.cmd_generate(args)
        file_stat = os.stat(file_path)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_file_permissions_after_remove(self, keys_file):
        """File has 0o600 permissions after remove."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_remove(args)
        file_stat = os.stat(keys_file)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_file_permissions_after_rotate(self, keys_file):
        """File has 0o600 permissions after rotate."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_rotate(args)
        file_stat = os.stat(keys_file)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600


class TestAtomicWrite:
    """Tests for atomic file write behavior."""

    def test_atomic_write_creates_file(self, tmp_path):
        """Atomic write creates a new file."""
        file_path = str(tmp_path / "new_keys.txt")
        key_mgmt.atomic_write(file_path, ["line1", "line2"])
        assert os.path.exists(file_path)
        content = open(file_path).read()
        assert "line1\n" in content
        assert "line2\n" in content

    def test_atomic_write_replaces_file(self, tmp_path):
        """Atomic write replaces existing content entirely."""
        file_path = str(tmp_path / "keys.txt")
        open(file_path, "w").write("old content\n")
        key_mgmt.atomic_write(file_path, ["new content"])
        content = open(file_path).read()
        assert "old content" not in content
        assert "new content" in content

    def test_atomic_write_no_temp_files_left(self, tmp_path):
        """No temporary files remain after successful write."""
        file_path = str(tmp_path / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])
        remaining = os.listdir(tmp_path)
        assert remaining == ["keys.txt"]

    def test_atomic_write_permissions(self, tmp_path):
        """Written file has 0o600 permissions."""
        file_path = str(tmp_path / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])
        file_stat = os.stat(file_path)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        """Atomic write creates parent directories if needed."""
        file_path = str(tmp_path / "subdir" / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])
        assert os.path.exists(file_path)


class TestCLIIntegration:
    """Integration tests running the CLI as a subprocess."""

    SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "key_mgmt.py")

    def test_cli_generate_and_list(self, tmp_path):
        """Full round-trip: generate a key, then list it."""
        file_path = str(tmp_path / "keys.txt")
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "generate", "--name", "cli-test"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cli-test" in result.stdout
        assert "sk-" in result.stdout
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cli-test" in result.stdout
        assert "1 key(s) configured" in result.stdout

    def test_cli_quiet_generate(self, tmp_path):
        """Quiet mode outputs only the key value."""
        file_path = str(tmp_path / "keys.txt")
        result = subprocess.run(
            [
                sys.executable,
                self.SCRIPT,
                "--file",
                file_path,
                "--quiet",
                "generate",
                "--name",
                "quiet-test",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        assert output.startswith("sk-")
        assert len(output) == 46

    def test_cli_no_command_shows_help(self):
        """Running without a command exits with code 1."""
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", "/tmp/fake.txt"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_cli_remove_and_verify(self, tmp_path):
        """Generate, remove, verify key is gone."""
        file_path = str(tmp_path / "keys.txt")
        subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "generate", "--name", "to-remove"],
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "remove", "--name", "to-remove"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "list"],
            capture_output=True,
            text=True,
        )
        assert "to-remove" not in result.stdout
        assert "0 key(s) configured" in result.stdout

    def test_cli_rotate_and_verify(self, tmp_path):
        """Generate, rotate, verify key changed."""
        file_path = str(tmp_path / "keys.txt")
        gen_result = subprocess.run(
            [
                sys.executable,
                self.SCRIPT,
                "--file",
                file_path,
                "--quiet",
                "generate",
                "--name",
                "to-rotate",
            ],
            capture_output=True,
            text=True,
        )
        original_key = gen_result.stdout.strip()
        rot_result = subprocess.run(
            [
                sys.executable,
                self.SCRIPT,
                "--file",
                file_path,
                "--quiet",
                "rotate",
                "--name",
                "to-rotate",
            ],
            capture_output=True,
            text=True,
        )
        assert rot_result.returncode == 0
        new_key = rot_result.stdout.strip()
        assert new_key != original_key
        assert new_key.startswith("sk-")


class TestGetDefaultKeysFile:
    """Tests for get_default_keys_file() environment variable resolution."""

    def test_auth_keys_file_env(self, monkeypatch):
        """AUTH_KEYS_FILE takes precedence over DATA_DIR."""
        monkeypatch.setenv("AUTH_KEYS_FILE", "/custom/path/keys.txt")
        monkeypatch.setenv("DATA_DIR", "/some/data")
        result = key_mgmt.get_default_keys_file()
        assert result == "/custom/path/keys.txt"

    def test_data_dir_env(self, monkeypatch):
        """DATA_DIR is used when AUTH_KEYS_FILE is not set."""
        monkeypatch.delenv("AUTH_KEYS_FILE", raising=False)
        monkeypatch.setenv("DATA_DIR", "/my/data")
        result = key_mgmt.get_default_keys_file()
        assert result == "/my/data/api_keys.txt"

    def test_default_path(self, monkeypatch):
        """Falls back to /data/api_keys.txt when no env vars set."""
        monkeypatch.delenv("AUTH_KEYS_FILE", raising=False)
        monkeypatch.delenv("DATA_DIR", raising=False)
        result = key_mgmt.get_default_keys_file()
        assert result == "/data/api_keys.txt"


class TestLoadKeysFileEdgeCases:
    """Tests for load_keys_file() edge cases."""

    def test_nonexistent_file(self, tmp_path):
        """Loading a nonexistent file returns empty list."""
        result = key_mgmt.load_keys_file(str(tmp_path / "nonexistent.txt"))
        assert result == []

    def test_lines_without_colon(self, tmp_path):
        """Lines without a colon are treated as other type."""
        path = tmp_path / "keys.txt"
        path.write_text("this line has no colon\nalice:sk-test-key\n")
        result = key_mgmt.load_keys_file(str(path))
        assert len(result) == 2
        assert result[0] == ("other", "", "this line has no colon")
        assert result[1] == ("key", "alice", "alice:sk-test-key")

    def test_comment_lines(self, tmp_path):
        """Comment lines are treated as other type."""
        path = tmp_path / "keys.txt"
        path.write_text("# comment\nalice:sk-key\n")
        result = key_mgmt.load_keys_file(str(path))
        assert result[0][0] == "other"
        assert result[1][0] == "key"

    def test_blank_lines(self, tmp_path):
        """Blank lines are treated as other type."""
        path = tmp_path / "keys.txt"
        path.write_text("\n\nalice:sk-key\n\n")
        result = key_mgmt.load_keys_file(str(path))
        other_count = sum(1 for t, _, _ in result if t == "other")
        key_count = sum(1 for t, _, _ in result if t == "key")
        assert key_count == 1
        assert other_count >= 2


class TestAtomicWriteFailure:
    """Tests for atomic_write() error handling."""

    def test_atomic_write_cleanup_on_failure(self, tmp_path):
        """Temp file is cleaned up if writing fails."""
        file_path = str(tmp_path / "keys.txt")
        with patch("key_mgmt.os.fdopen") as mock_fdopen:
            mock_fdopen.side_effect = OSError("Disk full")
            with pytest.raises(OSError, match="Disk full"):
                key_mgmt.atomic_write(file_path, ["test line"])
        remaining = os.listdir(tmp_path)
        temp_files = [f for f in remaining if f.startswith(".keys_")]
        assert len(temp_files) == 0


class TestBuildParserKeyMgmt:
    """Tests for build_parser() CLI argument structure."""

    def test_parser_creation(self):
        """Build_parser returns an ArgumentParser."""
        parser = key_mgmt.build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_generate_subcommand(self):
        """Parser accepts generate subcommand with --name."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--file", "/tmp/keys.txt", "generate", "--name", "test-key"])
        assert args.command == "generate"
        assert args.name == "test-key"

    def test_list_subcommand(self):
        """Parser accepts list subcommand."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--file", "/tmp/keys.txt", "list"])
        assert args.command == "list"

    def test_remove_subcommand(self):
        """Parser accepts remove subcommand with --name."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--file", "/tmp/keys.txt", "remove", "--name", "test-key"])
        assert args.command == "remove"
        assert args.name == "test-key"

    def test_rotate_subcommand(self):
        """Parser accepts rotate subcommand with --name."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--file", "/tmp/keys.txt", "rotate", "--name", "test-key"])
        assert args.command == "rotate"
        assert args.name == "test-key"

    def test_quiet_flag(self):
        """Parser accepts --quiet flag."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--quiet", "--file", "/tmp/keys.txt", "list"])
        assert args.quiet is True

    def test_quiet_short_flag(self):
        """Parser accepts -q short flag."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["-q", "--file", "/tmp/keys.txt", "list"])
        assert args.quiet is True

    def test_no_command_returns_none(self):
        """Parser with no subcommand sets command to None."""
        parser = key_mgmt.build_parser()
        args = parser.parse_args(["--file", "/tmp/keys.txt"])
        assert args.command is None


class TestMainFunction:
    """Tests for main() CLI entry point."""

    def test_main_no_command_returns_1(self):
        """No command argument returns exit code 1."""
        with patch("key_mgmt.build_parser") as mock_bp:
            mock_args = argparse.Namespace(command=None)
            mock_bp.return_value.parse_args.return_value = mock_args
            result = key_mgmt.main()
            assert result == 1

    def test_main_generate_command(self, tmp_path):
        """Generate command via main() creates key file."""
        file_path = str(tmp_path / "keys.txt")
        with patch("sys.argv", ["key_mgmt", "--file", file_path, "generate", "--name", "test"]):
            result = key_mgmt.main()
            assert result == 0
            assert os.path.exists(file_path)

    def test_main_list_command(self, tmp_path):
        """List command via main() succeeds."""
        file_path = str(tmp_path / "keys.txt")
        open(file_path, "w").write("test:sk-test-key\n")
        with patch("sys.argv", ["key_mgmt", "--file", file_path, "list"]):
            result = key_mgmt.main()
            assert result == 0

    def test_main_unknown_command_returns_1(self):
        """Unknown command returns exit code 1."""
        with patch("key_mgmt.build_parser") as mock_bp:
            mock_args = argparse.Namespace(command="unknown_command")
            mock_bp.return_value.parse_args.return_value = mock_args
            result = key_mgmt.main()
            assert result == 1

    def test_main_remove_command(self, tmp_path):
        """Remove command via main() removes key."""
        file_path = str(tmp_path / "keys.txt")
        open(file_path, "w").write("test-key:sk-test-key\n")
        with patch("sys.argv", ["key_mgmt", "--file", file_path, "remove", "--name", "test-key"]):
            result = key_mgmt.main()
            assert result == 0

    def test_main_rotate_command(self, tmp_path):
        """Rotate command via main() rotates key."""
        file_path = str(tmp_path / "keys.txt")
        open(file_path, "w").write("test-key:sk-test-key\n")
        with patch("sys.argv", ["key_mgmt", "--file", file_path, "rotate", "--name", "test-key"]):
            result = key_mgmt.main()
            assert result == 0


class TestListQuietMode:
    """Tests for cmd_list in quiet mode."""

    def test_list_quiet_mode_missing_file(self, tmp_path, capsys):
        """Quiet mode with missing file suppresses detailed messages."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(file=file_path, quiet=True)
        result = key_mgmt.cmd_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No keys file found" not in captured.out
        assert "0 key(s) configured" in captured.out

    def test_list_quiet_mode_with_keys(self, keys_file, capsys):
        """Quiet mode suppresses headers but still shows count."""
        args = argparse.Namespace(file=keys_file, quiet=True)
        result = key_mgmt.cmd_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "KEY_ID" not in captured.out
        assert "2 key(s) configured" in captured.out


class TestRemoveQuietMode:
    """Tests for cmd_remove in quiet mode."""

    def test_remove_quiet_mode(self, keys_file, capsys):
        """Quiet mode suppresses success message."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=True)
        result = key_mgmt.cmd_remove(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Removed" not in captured.out
