#!/usr/bin/env python3
"""
Spring '83 Server Implementation

A minimal reference implementation of the Spring '83 protocol (June 2022 draft).
Listens on 127.0.0.1:8083 and serves/accepts boards according to protocol spec.
"""

import argparse
import http.server
import json
import os
import re
import socketserver
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

# Constants defined in the Spring '83 spec
KEY_RE = re.compile(r"^[0-9a-f]{57}83e(0[1-9]|1[0-2])\d{2}$")
INFERNAL_KEY = "d17eef211f510479ee6696495a2589f7e9fb055c2576749747d93444883e0123"
TEST_KEY = "ab589f4dde9fce4180fcf42c7b05185b0a02a5d682e353fa39177995083e0583"
BOARD_LIMIT = 2217  # Max board size in bytes
TTL_SECONDS = 22 * 24 * 3600  # 22 days in seconds

# Import vendored pure25519 for Ed25519 signature verification
# This would be included in the repo but placeholder for now
try:
    from pure25519.signing import VerifyingKey
except ImportError:
    print("Warning: pure25519 not found. Signature verification will be skipped.")
    VerifyingKey = None

class Spring83Server(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Spring '83 server."""
    
    server_version = "Spring83/0.1"
    boards_dir = Path("/opt/spring83/boards")
    
    def __init__(self, *args, **kwargs):
        self.boards_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(*args, **kwargs)
    
    def do_OPTIONS(self):
        """Handle OPTIONS request with CORS headers."""
        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests for boards."""
        path = self.path.strip("/")
        
        # Root path shows server info
        if not path:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(self.root_page().encode("utf-8"))
            return
        
        # Test key returns rotating content
        if path == TEST_KEY:
            self.serve_test_key()
            return
        
        # Validate the key format
        if not KEY_RE.match(path):
            self.send_error(404, "Invalid key format")
            return
        
        # Reject infernal key
        if path == INFERNAL_KEY:
            self.send_error(403, "Infernal key rejected")
            return
        
        # Try to serve the board
        board_path = self.boards_dir / path
        if not board_path.exists():
            self.send_error(404, "Board not found")
            return
        
        # Check if board has expired
        mtime = board_path.stat().st_mtime
        if time.time() - mtime > TTL_SECONDS:
            self.send_error(404, "Board expired")
            board_path.unlink()
            return
        
        # Serve the board
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Spring-Version", "83")
        self.send_cors_headers()
        self.end_headers()
        
        with open(board_path, "rb") as f:
            self.wfile.write(f.read())
    
    def do_PUT(self):
        """Handle PUT requests to publish boards."""
        key = self.path.strip("/")
        
        # Validate the key format
        if not KEY_RE.match(key):
            self.send_error(400, "Invalid key format")
            return
        
        # Reject infernal key
        if key == INFERNAL_KEY:
            self.send_error(403, "Infernal key rejected")
            return
        
        # Read and validate content length
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > BOARD_LIMIT:
                self.send_error(413, f"Board exceeds {BOARD_LIMIT} bytes")
                return
            
            board_content = self.rfile.read(content_length)
            if len(board_content) > BOARD_LIMIT:
                self.send_error(413, f"Board exceeds {BOARD_LIMIT} bytes")
                return
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        
        # Validate board content (should contain a <time> element)
        if b"<time" not in board_content:
            self.send_error(400, "Missing <time> element")
            return
        
        # Verify signature if VerifyingKey is available
        if VerifyingKey:
            if not self.verify_signature(key, board_content):
                self.send_error(401, "Invalid signature")
                return
        
        # Save the board
        board_path = self.boards_dir / key
        
        # Check monotonicity if the board already exists
        if board_path.exists():
            try:
                with open(board_path, "rb") as f:
                    old_content = f.read()
                
                old_timestamp = self.extract_timestamp(old_content)
                new_timestamp = self.extract_timestamp(board_content)
                
                if old_timestamp and new_timestamp and new_timestamp <= old_timestamp:
                    self.send_error(409, "Timestamp must be monotonically increasing")
                    return
            except Exception as e:
                self.send_error(500, f"Error checking monotonicity: {e}")
                return
        
        # Write the board
        with open(board_path, "wb") as f:
            f.write(board_content)
        
        self.send_response(201)
        self.send_header("Spring-Version", "83")
        self.send_cors_headers()
        self.end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers as required by Spring '83 spec."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Spring-Signature, Spring-Version")
    
    def root_page(self) -> str:
        """Generate the root page with server info."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spring '83 Server</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2em; }}
                code {{ background: #f0f0f0; padding: 0.2em; }}
            </style>
        </head>
        <body>
            <h1>Spring '83 Server</h1>
            <p>This is a minimal reference implementation of the 
               <a href="https://github.com/robinsloan/spring-83">Spring '83</a> protocol.</p>
            <p>Board TTL: 22 days</p>
            <p>Maximum board size: {BOARD_LIMIT} bytes</p>
            <p>Current time: {datetime.now(timezone.utc).isoformat()}</p>
        </body>
        </html>
        """
    
    def serve_test_key(self):
        """Serve rotating content for the test key."""
        hour = datetime.now().hour
        test_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spring '83 Test Board</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>Test Board</h1>
            <p>This is a test board that rotates content by the hour.</p>
            <p>Current hour: {hour}</p>
            <time datetime="{datetime.now(timezone.utc).isoformat()}">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</time>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Spring-Version", "83")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(test_content.encode("utf-8"))
    
    def verify_signature(self, key: str, content: bytes) -> bool:
        """
        Verify the Ed25519 signature of the board content.
        
        Args:
            key: The public key (also the board ID)
            content: The board content
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        # Placeholder for signature verification
        # In a real implementation, we would:
        # 1. Extract the Spring-Signature header
        # 2. Convert the key to a VerifyingKey object
        # 3. Verify the signature against the content
        return True
    
    def extract_timestamp(self, content: bytes) -> Optional[datetime]:
        """
        Extract the timestamp from the board content.
        
        Args:
            content: The board content
            
        Returns:
            Optional[datetime]: The extracted timestamp or None if not found
        """
        # Very simplistic regex to extract datetime from <time> tag
        # A real implementation would use a proper HTML parser
        match = re.search(rb'<time\s+datetime="([^"]+)"', content)
        if match:
            try:
                return datetime.fromisoformat(match.group(1).decode("utf-8"))
            except ValueError:
                return None
        return None


def run_server(host: str = "127.0.0.1", port: int = 8083, boards_dir: str = "/opt/spring83/boards"):
    """
    Run the Spring '83 server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        boards_dir: Directory to store boards
    """
    # Set the boards directory
    Spring83Server.boards_dir = Path(boards_dir)
    Spring83Server.boards_dir.mkdir(parents=True, exist_ok=True)
    
    # Create server
    with socketserver.TCPServer((host, port), Spring83Server) as server:
        print(f"Spring '83 server running at http://{host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spring '83 Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8083, help="Port to listen on")
    parser.add_argument(
        "--boards-dir", default="/opt/spring83/boards", help="Directory to store boards"
    )
    
    args = parser.parse_args()
    run_server(args.host, args.port, args.boards_dir)