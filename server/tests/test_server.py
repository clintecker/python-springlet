#!/usr/bin/env python3
"""
Tests for the Spring '83 server implementation.
"""

import http.client
import io
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import the server module
sys.path.insert(0, str(Path(__file__).parent.parent))

import spring83_server


class TestSpring83Server(unittest.TestCase):
    """Test cases for Spring83Server."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for boards
        self.temp_dir = Path("./test_boards")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Set the boards directory for the server
        spring83_server.Spring83Server.boards_dir = self.temp_dir
        
        # Mock request handler
        self.handler = spring83_server.Spring83Server(None, None, None)
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.send_error = MagicMock()
        
        # Setup a valid key for testing
        self.valid_key = "ab589f4dde9fce4180fcf42c7b05185b0a02a5d682e353fa39177995083e0583"
        
        # Create a valid board content
        now = datetime.now(timezone.utc)
        self.valid_board = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Board</title>
        </head>
        <body>
            <h1>Test Board</h1>
            <p>This is a test board.</p>
            <time datetime="{now.isoformat()}">{now.strftime("%Y-%m-%d %H:%M:%S")}</time>
        </body>
        </html>
        """.encode("utf-8")
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove all files in the temporary directory
        for file in self.temp_dir.glob("*"):
            file.unlink()
        
        # Remove the temporary directory
        self.temp_dir.rmdir()
    
    def test_key_regex(self):
        """Test the key format regex."""
        # Valid keys
        self.assertTrue(spring83_server.KEY_RE.match(self.valid_key))
        self.assertTrue(spring83_server.KEY_RE.match(spring83_server.TEST_KEY))
        
        # Invalid keys
        self.assertFalse(spring83_server.KEY_RE.match("ab"))  # Too short
        self.assertFalse(spring83_server.KEY_RE.match("x" * 64))  # Invalid chars
        self.assertFalse(spring83_server.KEY_RE.match("0" * 57 + "83e1333"))  # Invalid month
    
    def test_root_page(self):
        """Test the root page generation."""
        root_page = self.handler.root_page()
        self.assertIn("Spring '83 Server", root_page)
        self.assertIn("22 days", root_page)
        self.assertIn(str(spring83_server.BOARD_LIMIT), root_page)
    
    def test_extract_timestamp(self):
        """Test timestamp extraction from board content."""
        # Create board content with a timestamp
        now = datetime.now(timezone.utc)
        board = f'<time datetime="{now.isoformat()}">Test</time>'.encode("utf-8")
        
        extracted = self.handler.extract_timestamp(board)
        self.assertIsNotNone(extracted)
        
        # Check that the timestamps are the same (ignore microseconds)
        self.assertEqual(extracted.replace(microsecond=0), now.replace(microsecond=0))
        
        # Test with invalid timestamp
        board = b'<time datetime="invalid">Test</time>'
        extracted = self.handler.extract_timestamp(board)
        self.assertIsNone(extracted)
        
        # Test with no timestamp
        board = b'<p>No timestamp here</p>'
        extracted = self.handler.extract_timestamp(board)
        self.assertIsNone(extracted)
    
    def test_do_options(self):
        """Test OPTIONS request handling."""
        self.handler.path = "/"
        self.handler.do_OPTIONS()
        
        self.handler.send_response.assert_called_once_with(200)
        self.handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        self.handler.send_header.assert_any_call("Content-Length", "0")
        self.handler.end_headers.assert_called_once()
    
    def test_do_get_root(self):
        """Test GET request to root path."""
        self.handler.path = "/"
        self.handler.wfile = io.BytesIO()
        self.handler.do_GET()
        
        self.handler.send_response.assert_called_once_with(200)
        self.handler.send_header.assert_any_call("Content-Type", "text/html; charset=utf-8")
        self.handler.end_headers.assert_called_once()
        
        # Check if the response contains the expected content
        response = self.handler.wfile.getvalue().decode("utf-8")
        self.assertIn("Spring '83 Server", response)
    
    def test_do_get_invalid_key(self):
        """Test GET request with invalid key format."""
        self.handler.path = "/invalid-key"
        self.handler.do_GET()
        
        self.handler.send_error.assert_called_once_with(404, "Invalid key format")
    
    def test_do_get_infernal_key(self):
        """Test GET request with infernal key."""
        self.handler.path = f"/{spring83_server.INFERNAL_KEY}"
        self.handler.do_GET()
        
        self.handler.send_error.assert_called_once_with(403, "Infernal key rejected")
    
    def test_do_get_nonexistent_board(self):
        """Test GET request for a board that doesn't exist."""
        self.handler.path = f"/{self.valid_key}"
        self.handler.do_GET()
        
        self.handler.send_error.assert_called_once_with(404, "Board not found")
    
    def test_do_put_and_get_board(self):
        """Test PUT request to create a board and then GET it."""
        # Set up the PUT request
        self.handler.path = f"/{self.valid_key}"
        self.handler.headers = {"Content-Length": str(len(self.valid_board))}
        self.handler.rfile = io.BytesIO(self.valid_board)
        
        # Patch the verify_signature method to return True
        with patch.object(self.handler, "verify_signature", return_value=True):
            self.handler.do_PUT()
        
        self.handler.send_response.assert_called_once_with(201)
        self.handler.send_header.assert_any_call("Spring-Version", "83")
        self.handler.end_headers.assert_called_once()
        
        # Check if the board was saved
        board_path = self.temp_dir / self.valid_key
        self.assertTrue(board_path.exists())
        
        # Reset mocks
        self.handler.send_response.reset_mock()
        self.handler.send_header.reset_mock()
        self.handler.end_headers.reset_mock()
        
        # Set up the GET request
        self.handler.path = f"/{self.valid_key}"
        self.handler.wfile = io.BytesIO()
        
        self.handler.do_GET()
        
        self.handler.send_response.assert_called_once_with(200)
        self.handler.send_header.assert_any_call("Content-Type", "text/html; charset=utf-8")
        self.handler.send_header.assert_any_call("Spring-Version", "83")
        self.handler.end_headers.assert_called_once()
        
        # Check if the response contains the expected content
        response = self.handler.wfile.getvalue()
        self.assertEqual(response, self.valid_board)
    
    def test_do_put_invalid_key(self):
        """Test PUT request with invalid key format."""
        self.handler.path = "/invalid-key"
        self.handler.do_PUT()
        
        self.handler.send_error.assert_called_once_with(400, "Invalid key format")
    
    def test_do_put_infernal_key(self):
        """Test PUT request with infernal key."""
        self.handler.path = f"/{spring83_server.INFERNAL_KEY}"
        self.handler.do_PUT()
        
        self.handler.send_error.assert_called_once_with(403, "Infernal key rejected")
    
    def test_do_put_oversized_board(self):
        """Test PUT request with a board that exceeds the size limit."""
        # Create an oversized board
        oversized_board = b"x" * (spring83_server.BOARD_LIMIT + 1)
        
        # Set up the PUT request
        self.handler.path = f"/{self.valid_key}"
        self.handler.headers = {"Content-Length": str(len(oversized_board))}
        self.handler.rfile = io.BytesIO(oversized_board)
        
        self.handler.do_PUT()
        
        error_msg = f"Board exceeds {spring83_server.BOARD_LIMIT} bytes"
        self.handler.send_error.assert_called_once_with(413, error_msg)
    
    def test_do_put_missing_time_element(self):
        """Test PUT request with a board missing the time element."""
        # Create a board without a time element
        board_without_time = b"<html><body><p>No time element here</p></body></html>"
        
        # Set up the PUT request
        self.handler.path = f"/{self.valid_key}"
        self.handler.headers = {"Content-Length": str(len(board_without_time))}
        self.handler.rfile = io.BytesIO(board_without_time)
        
        self.handler.do_PUT()
        
        self.handler.send_error.assert_called_once_with(400, "Missing <time> element")
    
    def test_do_put_monotonicity(self):
        """Test that timestamps must be monotonically increasing."""
        # Create a board with an older timestamp
        old_time = datetime.now(timezone.utc) - timedelta(days=1)
        old_board = f"""
        <html><body>
            <p>Old board</p>
            <time datetime="{old_time.isoformat()}">Old time</time>
        </body></html>
        """.encode("utf-8")
        
        # Create a board with a newer timestamp
        new_time = datetime.now(timezone.utc)
        new_board = f"""
        <html><body>
            <p>New board</p>
            <time datetime="{new_time.isoformat()}">New time</time>
        </body></html>
        """.encode("utf-8")
        
        # First PUT the newer board
        self.handler.path = f"/{self.valid_key}"
        self.handler.headers = {"Content-Length": str(len(new_board))}
        self.handler.rfile = io.BytesIO(new_board)
        
        # Patch the verify_signature method to return True
        with patch.object(self.handler, "verify_signature", return_value=True):
            self.handler.do_PUT()
        
        self.handler.send_response.assert_called_once_with(201)
        
        # Reset mocks
        self.handler.send_response.reset_mock()
        self.handler.send_error.reset_mock()
        
        # Now try to PUT the older board
        self.handler.path = f"/{self.valid_key}"
        self.handler.headers = {"Content-Length": str(len(old_board))}
        self.handler.rfile = io.BytesIO(old_board)
        
        # Patch the verify_signature method to return True
        with patch.object(self.handler, "verify_signature", return_value=True):
            self.handler.do_PUT()
        
        self.handler.send_error.assert_called_once_with(409, "Timestamp must be monotonically increasing")


if __name__ == "__main__":
    unittest.main()