from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.agents.internal_tools.file_tools import (
    MAX_TEXT_FILE_SIZE,
    _check_file_size,
    _count_tokens,
    _is_path_allowed,
    _validate_directory_path,
    _validate_file_extension,
    _validate_file_path,
    internal_create_directory,
    internal_directory_tree,
    internal_edit_file,
    internal_get_file_info,
    internal_list_directory,
    internal_move_file,
    internal_read_media_file,
    internal_read_text_file,
    internal_search_files,
    internal_write_file,
)


class TestFileToolsHelpers:
    """Test helper functions with workspace path mocking."""

    MOCK_WORKSPACE = "/tmp/synkora/workspaces/tenant1/conv1"

    def test_is_path_allowed(self):
        # Valid path within workspace
        with patch("os.path.realpath", side_effect=lambda x: x):
            is_allowed, error = _is_path_allowed(f"{self.MOCK_WORKSPACE}/test.txt", self.MOCK_WORKSPACE)
            assert is_allowed is True
            assert error is None

        # Path outside workspace (not matching blocked patterns)
        with patch("os.path.realpath", side_effect=lambda x: x):
            is_allowed, error = _is_path_allowed("/home/user/test.txt", self.MOCK_WORKSPACE)
            assert is_allowed is False
            assert "outside the workspace" in error

        # Path matching blocked pattern
        with patch("os.path.realpath", side_effect=lambda x: x):
            is_allowed, error = _is_path_allowed("/etc/passwd", self.MOCK_WORKSPACE)
            assert is_allowed is False
            assert "blocked pattern" in error

        # No workspace provided
        is_allowed, error = _is_path_allowed("/tmp/test.txt", None)
        assert is_allowed is False
        assert "No workspace path configured" in error

    def test_validate_file_path(self):
        config = {"workspace_path": self.MOCK_WORKSPACE}
        file_path = f"{self.MOCK_WORKSPACE}/test.txt"

        with (
            patch("os.path.realpath", side_effect=lambda x: x),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_file", return_value=True),
            patch("os.access", return_value=True),
        ):
            valid, error = _validate_file_path(file_path, config=config)
            assert valid is True
            assert error is None

        # Not exists
        with patch("os.path.realpath", side_effect=lambda x: x), patch("pathlib.Path.exists", return_value=False):
            valid, error = _validate_file_path(file_path, config=config)
            assert valid is False
            assert "File not found" in error

        # Not a file
        with (
            patch("os.path.realpath", side_effect=lambda x: x),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            valid, error = _validate_file_path(file_path, config=config)
            assert valid is False
            assert "Path is not a file" in error

    def test_validate_directory_path(self):
        config = {"workspace_path": self.MOCK_WORKSPACE}
        dir_path = f"{self.MOCK_WORKSPACE}/subdir"

        with (
            patch("os.path.realpath", side_effect=lambda x: x),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            valid, error = _validate_directory_path(dir_path, config=config)
            assert valid is True
            assert error is None

        # Not exists
        with patch("os.path.realpath", side_effect=lambda x: x), patch("pathlib.Path.exists", return_value=False):
            valid, error = _validate_directory_path(dir_path, config=config)
            assert valid is False
            assert "Directory not found" in error

    def test_validate_file_extension(self):
        assert _validate_file_extension("test.txt", "text")[0] is True
        assert _validate_file_extension("test.jpg", "media")[0] is True

        valid, error = _validate_file_extension("test.exe", "text")
        assert valid is False
        assert "File extension '.exe' not allowed" in error

        valid, error = _validate_file_extension("test.txt", "unknown")
        assert valid is False
        assert "Unknown file type" in error

    def test_check_file_size(self):
        with patch("os.path.getsize", return_value=1024):
            assert _check_file_size("test.txt", "text")[0] is True

        with patch("os.path.getsize", return_value=MAX_TEXT_FILE_SIZE + 1):
            valid, error = _check_file_size("test.txt", "text")
            assert valid is False
            assert "exceeds maximum allowed" in error

    def test_count_tokens(self):
        text = "Hello world"
        with patch.dict("sys.modules", {"tiktoken": None}):
            assert _count_tokens(text) == len(text) // 4

        # Test with mocked tiktoken
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2]
        with patch.dict("sys.modules", {"tiktoken": MagicMock()}):
            with patch("tiktoken.get_encoding", return_value=mock_encoding):
                assert _count_tokens(text) == 2


class TestInternalFileTools:
    @pytest.mark.asyncio
    async def test_internal_read_text_file(self):
        file_content = "Line 1\nLine 2\nLine 3"

        with (
            patch("src.services.agents.internal_tools.file_tools._validate_file_path", return_value=(True, None)),
            patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")),
            patch("pathlib.Path.stat") as mock_stat,
            patch("builtins.open", mock_open(read_data=file_content)),
        ):
            mock_stat.return_value.st_size = len(file_content)

            # Read all
            result = await internal_read_text_file("/tmp/test.txt")
            assert result["content"] == file_content
            assert result["total_lines"] == 3
            assert result["lines_read"] == 3

            # Read with max lines
            result = await internal_read_text_file("/tmp/test.txt", max_lines=2)
            assert result["lines_read"] == 2
            assert "Line 3" not in result["content"]

            # Read with start line
            result = await internal_read_text_file("/tmp/test.txt", start_line=2)
            assert result["lines_read"] == 2
            assert "Line 1" not in result["content"]

    @pytest.mark.asyncio
    async def test_internal_read_text_file_truncation(self):
        # Create content that exceeds token limit
        # We set MAX_TOKEN_LENGTH to a small value
        file_content = "Line1\nLine2\nLine3\nLine4"

        with (
            patch("src.services.agents.internal_tools.file_tools._validate_file_path", return_value=(True, None)),
            patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")),
            patch("pathlib.Path.stat"),
            patch("builtins.open", mock_open(read_data=file_content)),
            patch("src.services.agents.internal_tools.file_tools.MAX_TOKEN_LENGTH", 5),
            patch("src.services.agents.internal_tools.file_tools._count_tokens", side_effect=lambda x: len(x)),
        ):
            # Lines are ~6 chars each including newline. Total ~24.
            # Max tokens 5.
            # It should truncate significantly.

            result = await internal_read_text_file("/tmp/test.txt")
            assert result["is_truncated"] is True
            assert "Content truncated" in result["truncation_reason"]
            assert len(result["content"]) <= 5

    @pytest.mark.asyncio
    async def test_internal_search_files(self):
        with (
            patch("src.services.agents.internal_tools.file_tools._validate_directory_path", return_value=(True, None)),
            patch("os.walk") as mock_walk,
        ):
            mock_walk.return_value = [("/tmp", [], ["test.txt", "ignore.log"]), ("/tmp/sub", [], ["match.txt"])]

            result = await internal_search_files("/tmp", r".*\.txt$")
            assert result["total_matches"] == 2
            assert any(m["name"] == "test.txt" for m in result["matches"])
            assert any(m["name"] == "match.txt" for m in result["matches"])

    @pytest.mark.asyncio
    async def test_internal_read_media_file(self):
        file_content = b"fake image content"

        with (
            patch("src.services.agents.internal_tools.file_tools._validate_file_path", return_value=(True, None)),
            patch("src.services.agents.internal_tools.file_tools._validate_file_extension", return_value=(True, None)),
            patch("src.services.agents.internal_tools.file_tools._check_file_size", return_value=(True, None)),
            patch("builtins.open", mock_open(read_data=file_content)),
            patch("mimetypes.guess_type", return_value=("image/jpeg", None)),
        ):
            result = await internal_read_media_file("/tmp/image.jpg")
            assert result["encoding"] == "base64"
            assert result["mime_type"] == "image/jpeg"
            assert result["size"] == len(file_content)

    @pytest.mark.asyncio
    async def test_internal_write_file(self):
        with (
            patch("src.services.agents.internal_tools.file_tools._validate_file_path", return_value=(True, None)),
            patch("src.services.agents.internal_tools.file_tools._validate_file_extension", return_value=(True, None)),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()) as mock_file,
            patch("os.path.getsize", return_value=100),
        ):
            result = await internal_write_file("/tmp/new.txt", "content")
            assert result["success"] is True
            mock_file.assert_called_with("/tmp/new.txt", "w", encoding="utf-8")
            mock_file().write.assert_called_with("content")

    @pytest.mark.asyncio
    async def test_internal_edit_file(self):
        original_content = "Hello World"
        with (
            patch("src.services.agents.internal_tools.file_tools._validate_file_path", return_value=(True, None)),
            patch("src.services.agents.internal_tools.file_tools._validate_file_extension", return_value=(True, None)),
            patch("builtins.open", mock_open(read_data=original_content)) as mock_file,
        ):
            result = await internal_edit_file("/tmp/test.txt", "World", "Universe")
            assert result["success"] is True
            assert result["replacements_made"] == 1

            # Verify write call
            handle = mock_file()
            handle.write.assert_called_with("Hello Universe")

    @pytest.mark.asyncio
    async def test_internal_get_file_info(self):
        mock_workspace = "/tmp/synkora/workspaces/tenant1/conv1"
        file_path = f"{mock_workspace}/test.txt"

        with (
            patch("src.services.agents.internal_tools.file_tools._get_workspace_path", return_value=mock_workspace),
            patch("src.services.agents.internal_tools.file_tools._is_path_allowed", return_value=(True, None)),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
            patch("pathlib.Path.is_file", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            patch("os.access", return_value=True),
        ):
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 1000
            mock_stat.return_value.st_ctime = 1000
            mock_stat.return_value.st_mode = 0o644

            result = await internal_get_file_info(file_path)
            assert result["name"] == "test.txt"
            assert result["size"] == 100
            assert result["is_file"] is True

    @pytest.mark.asyncio
    async def test_internal_move_file(self):
        mock_workspace = "/tmp/synkora/workspaces/tenant1/conv1"
        src_path = f"{mock_workspace}/src.txt"
        dest_path = f"{mock_workspace}/dest.txt"

        with (
            patch("src.services.agents.internal_tools.file_tools._get_workspace_path", return_value=mock_workspace),
            patch("src.services.agents.internal_tools.file_tools._is_path_allowed", return_value=(True, None)),
            patch("os.path.exists", return_value=True),
            patch("os.makedirs"),
            patch("shutil.move") as mock_move,
        ):
            result = await internal_move_file(src_path, dest_path)
            assert result["success"] is True
            mock_move.assert_called_with(src_path, dest_path)

    @pytest.mark.asyncio
    async def test_internal_create_directory(self):
        with (
            patch("src.services.agents.internal_tools.file_tools._validate_directory_path", return_value=(True, None)),
            patch("os.makedirs") as mock_makedirs,
            patch("os.path.exists", side_effect=[False, True]),
        ):  # Not exists initially, exists after creation
            result = await internal_create_directory("/tmp/newdir")
            assert result["success"] is True
            mock_makedirs.assert_called_with("/tmp/newdir", exist_ok=True)

    @pytest.mark.asyncio
    async def test_internal_list_directory(self):
        with (
            patch("src.services.agents.internal_tools.file_tools._validate_directory_path", return_value=(True, None)),
            patch("os.listdir", return_value=["file1.txt", "dir1", ".hidden"]),
            patch("os.stat") as mock_stat,
            patch("os.path.isdir", side_effect=lambda x: "dir1" in x),
            patch("os.path.isfile", side_effect=lambda x: "file1" in x),
        ):
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 1000
            mock_stat.return_value.st_mode = 0o644

            result = await internal_list_directory("/tmp")
            items = result["items"]
            assert len(items) == 2  # .hidden should be skipped by default
            assert any(i["name"] == "file1.txt" for i in items)
            assert any(i["name"] == "dir1" for i in items)

            # Test include hidden
            result = await internal_list_directory("/tmp", include_hidden=True)
            assert len(result["items"]) == 3

    @pytest.mark.asyncio
    async def test_internal_directory_tree_requires_isolation(self):
        with patch("subprocess.run") as run:
            result = await internal_directory_tree("/tmp", config={"_compute_session": None})
        assert "Isolated compute" in result["error"]
        run.assert_not_called()
