#!/usr/bin/env python3
"""
Tests for the Spring '83 client implementation.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import the client module
sys.path.insert(0, str(Path(__file__).parent.parent))

import spring83_client


class TestSpring83Client(unittest.TestCase):
    """Test cases for Spring83Client."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for config and cache
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / ".83"
        self.cache_dir = Path(self.temp_dir.name) / ".83_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Create a test client
        self.client = spring83_client.Spring83Client(self.config_path, self.cache_dir)
        
        # Create a test config file
        with open(self.config_path, "w") as f:
            f.write("https://test.spring83.example/key1\n")
            f.write("# Comment line\n")
            f.write("https://test.spring83.example/key2\n")
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_read_config(self):
        """Test reading the config file."""
        urls = self.client.read_config()
        
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://test.spring83.example/key1")
        self.assertEqual(urls[1], "https://test.spring83.example/key2")
    
    def test_read_nonexistent_config(self):
        """Test reading a nonexistent config file."""
        # Create a client with a nonexistent config file
        client = spring83_client.Spring83Client(Path("/nonexistent/.83"), self.cache_dir)
        
        urls = client.read_config()
        self.assertEqual(urls, [])
    
    def test_format_http_date(self):
        """Test formatting a timestamp as an HTTP date string."""
        # Test with a known timestamp
        timestamp = 1640995200  # 2022-01-01 00:00:00 GMT
        http_date = self.client.format_http_date(timestamp)
        
        self.assertEqual(http_date, "Sat, 01 Jan 2022 00:00:00 GMT")
    
    @patch("http.client.HTTPSConnection")
    def test_get_board(self, mock_https):
        """Test fetching a board from a server."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.getheaders.return_value = [
            ("Content-Type", "text/html"),
            ("Spring-Version", "83")
        ]
        mock_response.read.return_value = b"<html><body>Test Board</body></html>"
        
        # Set up mock connection
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response
        mock_https.return_value = mock_conn
        
        # Call get_board
        status, headers, content = self.client.get_board("https://test.spring83.example/key1")
        
        # Check that the connection was made correctly
        mock_https.assert_called_once_with("test.spring83.example")
        mock_conn.request.assert_called_once()
        args, kwargs = mock_conn.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "/key1")
        self.assertEqual(kwargs["headers"]["Spring-Version"], "83")
        
        # Check the returned values
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/html")
        self.assertEqual(headers["spring-version"], "83")
        self.assertEqual(content, b"<html><body>Test Board</body></html>")
    
    @patch("http.client.HTTPSConnection")
    def test_get_board_not_modified(self, mock_https):
        """Test fetching a board that hasn't been modified."""
        # Create a cached board
        key = "key1"
        cache_file = self.cache_dir / f"{key}.html"
        with open(cache_file, "wb") as f:
            f.write(b"<html><body>Cached Board</body></html>")
        
        # Set the file's modification time to a known value
        os.utime(cache_file, (1640995200, 1640995200))  # 2022-01-01 00:00:00 GMT
        
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status = 304  # Not Modified
        mock_response.getheaders.return_value = [
            ("Content-Type", "text/html"),
            ("Spring-Version", "83")
        ]
        
        # Set up mock connection
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response
        mock_https.return_value = mock_conn
        
        # Call get_board
        status, headers, content = self.client.get_board("https://test.spring83.example/key1")
        
        # Check that the connection was made correctly with If-Modified-Since
        mock_https.assert_called_once_with("test.spring83.example")
        mock_conn.request.assert_called_once()
        args, kwargs = mock_conn.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "/key1")
        self.assertEqual(kwargs["headers"]["If-Modified-Since"], "Sat, 01 Jan 2022 00:00:00 GMT")
        
        # Check the returned values
        self.assertEqual(status, 304)
        self.assertEqual(headers["content-type"], "text/html")
        self.assertEqual(headers["spring-version"], "83")
        self.assertIsNone(content)
    
    @patch.object(spring83_client.Spring83Client, "get_board")
    def test_fetch_and_cache(self, mock_get_board):
        """Test fetching and caching boards."""
        # Set up mock responses
        mock_get_board.side_effect = [
            # First board - 200 OK
            (200, {"content-type": "text/html"}, b"<html><body>Board 1</body></html>"),
            # Second board - 304 Not Modified
            (304, {"content-type": "text/html"}, None),
            # Third board - 404 Not Found
            (404, {"content-type": "text/html"}, None),
        ]
        
        # Set up test URLs
        urls = [
            "https://test.spring83.example/key1",
            "https://test.spring83.example/key2",
            "https://test.spring83.example/key3",
        ]
        
        # Call fetch_and_cache
        self.client.fetch_and_cache(urls, verbose=True)
        
        # Check that all boards were requested
        self.assertEqual(mock_get_board.call_count, 3)
        
        # Check that the first board was cached
        cache_file = self.cache_dir / "key1.html"
        self.assertTrue(cache_file.exists())
        with open(cache_file, "rb") as f:
            self.assertEqual(f.read(), b"<html><body>Board 1</body></html>")


if __name__ == "__main__":
    unittest.main()