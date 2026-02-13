"""Unit tests for scripts/key_mgmt.py - API Key Management CLI."""

import argparse
import os
import stat
import subprocess
import sys

import pytest

# Add scripts/ to path so we can import key_mgmt module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import key_mgmt  # noqa: E402

# --- Fixtures ---


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


# --- Test validate_key_id ---


class TestValidateKeyId:
    """Tests for key_id format validation."""

    def test_valid_alphanumeric(self):
        assert key_mgmt.validate_key_id("alice123") is True

    def test_valid_with_hyphens(self):
        assert key_mgmt.validate_key_id("alice-laptop") is True

    def test_valid_with_underscores(self):
        assert key_mgmt.validate_key_id("alice_laptop") is True

    def test_valid_mixed(self):
        assert key_mgmt.validate_key_id("prod-key_01") is True

    def test_valid_single_char(self):
        assert key_mgmt.validate_key_id("a") is True

    def test_valid_max_length(self):
        assert key_mgmt.validate_key_id("a" * 64) is True

    def test_invalid_empty(self):
        assert key_mgmt.validate_key_id("") is False

    def test_invalid_too_long(self):
        assert key_mgmt.validate_key_id("a" * 65) is False

    def test_invalid_special_chars(self):
        assert key_mgmt.validate_key_id("alice@laptop") is False

    def test_invalid_spaces(self):
        assert key_mgmt.validate_key_id("alice laptop") is False

    def test_invalid_dots(self):
        assert key_mgmt.validate_key_id("alice.laptop") is False

    def test_invalid_colon(self):
        assert key_mgmt.validate_key_id("alice:laptop") is False


# --- Test generate_api_key ---


class TestGenerateApiKey:
    """Tests for API key generation."""

    def test_starts_with_prefix(self):
        key = key_mgmt.generate_api_key()
        assert key.startswith("sk-")

    def test_correct_length(self):
        key = key_mgmt.generate_api_key()
        # sk- (3) + 43 base64url chars = 46
        assert len(key) == 46

    def test_unique_keys(self):
        keys = {key_mgmt.generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_valid_characters(self):
        key = key_mgmt.generate_api_key()
        # base64url uses A-Z, a-z, 0-9, -, _
        suffix = key[3:]  # strip sk-
        assert all(c.isalnum() or c in "-_" for c in suffix)


# --- Test cmd_generate ---


class TestGenerate:
    """Tests for the generate command."""

    def test_generate_creates_key(self, tmp_path):
        """Generate should create a valid key and append to file."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="test-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_generate(args)

        assert result == 0
        assert os.path.exists(file_path)

        content = open(file_path).read()
        assert "test-key:" in content
        assert "sk-" in content

        # Verify the line count (header comment + key)
        lines = [line for line in content.strip().split("\n") if line.strip()]
        key_lines = [line for line in lines if not line.startswith("#")]
        assert len(key_lines) == 1

    def test_generate_duplicate_name_fails(self, keys_file):
        """Generate should reject duplicate key_id."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_generate(args)
        assert result == 1

    def test_generate_invalid_name_fails(self, tmp_path):
        """Generate should reject key_id with special characters."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="bad@name!", file=file_path, quiet=False)
        result = key_mgmt.cmd_generate(args)
        assert result == 1
        # File should not be created for invalid name
        assert not os.path.exists(file_path)

    def test_generate_quiet_mode(self, tmp_path, capsys):
        """Quiet mode should only output the key value."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="quiet-key", file=file_path, quiet=True)
        result = key_mgmt.cmd_generate(args)

        assert result == 0
        captured = capsys.readouterr()
        output = captured.out.strip()
        # Should be just the key, no other text
        assert output.startswith("sk-")
        assert "Generated" not in output

    def test_generate_preserves_comments(self, keys_file):
        """Generate should preserve existing comments and keys."""
        args = argparse.Namespace(name="new-key", file=keys_file, quiet=False)
        key_mgmt.cmd_generate(args)

        content = open(keys_file).read()
        assert "# Test keys" in content
        assert "alice-laptop:" in content
        assert "production-key:" in content
        assert "new-key:" in content


# --- Test cmd_list ---


class TestList:
    """Tests for the list command."""

    def test_list_empty_file(self, empty_keys_file, capsys):
        """Empty file should show 0 keys."""
        args = argparse.Namespace(file=empty_keys_file, quiet=False)
        result = key_mgmt.cmd_list(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "0 key(s) configured" in captured.out

    def test_list_with_keys(self, keys_file, capsys):
        """Should show correct key_ids and count."""
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
        """List should NEVER display actual API key values."""
        args = argparse.Namespace(file=keys_file, quiet=False)
        key_mgmt.cmd_list(args)

        captured = capsys.readouterr()
        assert "sk-test-AAAA" not in captured.out
        assert "sk-test-BBBB" not in captured.out

    def test_list_missing_file(self, tmp_path, capsys):
        """Missing file should show 0 keys with helpful message."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(file=file_path, quiet=False)
        result = key_mgmt.cmd_list(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "0 key(s) configured" in captured.out


# --- Test cmd_remove ---


class TestRemove:
    """Tests for the remove command."""

    def test_remove_existing_key(self, keys_file):
        """Remove should delete the correct key line."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_remove(args)

        assert result == 0
        content = open(keys_file).read()
        assert "alice-laptop" not in content
        # Other key should remain
        assert "production-key" in content

    def test_remove_nonexistent_fails(self, keys_file):
        """Remove should fail for a key_id that doesn't exist."""
        args = argparse.Namespace(name="nonexistent", file=keys_file, quiet=False)
        result = key_mgmt.cmd_remove(args)
        assert result == 1

    def test_remove_preserves_comments(self, keys_file):
        """Remove should preserve comments and other keys."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_remove(args)

        content = open(keys_file).read()
        assert "# Test keys" in content

    def test_remove_missing_file_fails(self, tmp_path):
        """Remove should fail if keys file doesn't exist."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(name="any-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_remove(args)
        assert result == 1


# --- Test cmd_rotate ---


class TestRotate:
    """Tests for the rotate command."""

    def test_rotate_existing_key(self, keys_file):
        """Rotate should change the api_key but keep the key_id."""
        # Read original key value
        original_content = open(keys_file).read()
        original_line = [
            line for line in original_content.split("\n") if line.startswith("alice-laptop:")
        ][0]
        original_api_key = original_line.split(":", 1)[1]

        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        result = key_mgmt.cmd_rotate(args)

        assert result == 0

        # Read updated content
        new_content = open(keys_file).read()
        new_line = [line for line in new_content.split("\n") if line.startswith("alice-laptop:")][0]
        new_api_key = new_line.split(":", 1)[1]

        # key_id preserved, api_key changed
        assert "alice-laptop:" in new_content
        assert new_api_key != original_api_key
        assert new_api_key.startswith("sk-")

    def test_rotate_nonexistent_fails(self, keys_file):
        """Rotate should fail for a key_id that doesn't exist."""
        args = argparse.Namespace(name="nonexistent", file=keys_file, quiet=False)
        result = key_mgmt.cmd_rotate(args)
        assert result == 1

    def test_rotate_quiet_mode(self, keys_file, capsys):
        """Quiet mode should only output the new key value."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=True)
        result = key_mgmt.cmd_rotate(args)

        assert result == 0
        captured = capsys.readouterr()
        output = captured.out.strip()
        assert output.startswith("sk-")
        assert "Rotated" not in output

    def test_rotate_preserves_other_keys(self, keys_file):
        """Rotate should not modify other keys."""
        original_content = open(keys_file).read()
        prod_line = [
            line for line in original_content.split("\n") if line.startswith("production-key:")
        ][0]

        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_rotate(args)

        new_content = open(keys_file).read()
        assert prod_line in new_content

    def test_rotate_missing_file_fails(self, tmp_path):
        """Rotate should fail if keys file doesn't exist."""
        file_path = str(tmp_path / "nonexistent.txt")
        args = argparse.Namespace(name="any-key", file=file_path, quiet=False)
        result = key_mgmt.cmd_rotate(args)
        assert result == 1


# --- Test file permissions ---


class TestFilePermissions:
    """Tests for file permission security."""

    def test_file_permissions_after_generate(self, tmp_path):
        """File should have 0o600 permissions after generate."""
        file_path = str(tmp_path / "keys.txt")
        args = argparse.Namespace(name="test-key", file=file_path, quiet=True)
        key_mgmt.cmd_generate(args)

        file_stat = os.stat(file_path)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_file_permissions_after_remove(self, keys_file):
        """File should have 0o600 permissions after remove."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_remove(args)

        file_stat = os.stat(keys_file)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_file_permissions_after_rotate(self, keys_file):
        """File should have 0o600 permissions after rotate."""
        args = argparse.Namespace(name="alice-laptop", file=keys_file, quiet=False)
        key_mgmt.cmd_rotate(args)

        file_stat = os.stat(keys_file)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600


# --- Test atomic write ---


class TestAtomicWrite:
    """Tests for atomic file write behavior."""

    def test_atomic_write_creates_file(self, tmp_path):
        """atomic_write should create a new file."""
        file_path = str(tmp_path / "new_keys.txt")
        key_mgmt.atomic_write(file_path, ["line1", "line2"])

        assert os.path.exists(file_path)
        content = open(file_path).read()
        assert "line1\n" in content
        assert "line2\n" in content

    def test_atomic_write_replaces_file(self, tmp_path):
        """atomic_write should replace existing content entirely."""
        file_path = str(tmp_path / "keys.txt")
        open(file_path, "w").write("old content\n")

        key_mgmt.atomic_write(file_path, ["new content"])

        content = open(file_path).read()
        assert "old content" not in content
        assert "new content" in content

    def test_atomic_write_no_temp_files_left(self, tmp_path):
        """No temporary files should remain after successful write."""
        file_path = str(tmp_path / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])

        remaining = os.listdir(tmp_path)
        assert remaining == ["keys.txt"]

    def test_atomic_write_permissions(self, tmp_path):
        """Written file should have 0o600 permissions."""
        file_path = str(tmp_path / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])

        file_stat = os.stat(file_path)
        perms = stat.S_IMODE(file_stat.st_mode)
        assert perms == 0o600

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        """atomic_write should create parent directories if needed."""
        file_path = str(tmp_path / "subdir" / "keys.txt")
        key_mgmt.atomic_write(file_path, ["test"])

        assert os.path.exists(file_path)


# --- Test CLI integration via subprocess ---


class TestCLIIntegration:
    """Integration tests running the CLI as a subprocess."""

    SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "key_mgmt.py")

    def test_cli_generate_and_list(self, tmp_path):
        """Full round-trip: generate a key, then list it."""
        file_path = str(tmp_path / "keys.txt")

        # Generate
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "generate", "--name", "cli-test"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cli-test" in result.stdout
        assert "sk-" in result.stdout

        # List
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cli-test" in result.stdout
        assert "1 key(s) configured" in result.stdout

    def test_cli_quiet_generate(self, tmp_path):
        """Quiet mode should output only the key value."""
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
        """Running without a command should show help and exit 1."""
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", "/tmp/fake.txt"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_cli_remove_and_verify(self, tmp_path):
        """Generate, remove, verify key is gone."""
        file_path = str(tmp_path / "keys.txt")

        # Generate
        subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "generate", "--name", "to-remove"],
            capture_output=True,
            text=True,
        )

        # Remove
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--file", file_path, "remove", "--name", "to-remove"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Verify gone
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

        # Generate
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

        # Rotate
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
