#!/usr/bin/env python3
"""
Smoke test for Spring '83 server and client.

This script:
1. Starts a test server
2. Publishes a test board
3. Runs the client to fetch the board
4. Verifies the client received the correct board
"""

import http.client
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.spring83_server import BOARD_LIMIT, TEST_KEY


def run_server(port):
    """Start the server in a subprocess."""
    server_path = Path(__file__).parent.parent / "server" / "spring83_server.py"
    boards_dir = tempfile.mkdtemp()
    
    process = subprocess.Popen(
        [sys.executable, str(server_path), "--port", str(port), "--boards-dir", boards_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Give the server time to start
    time.sleep(1)
    
    return process, boards_dir


def publish_board(port):
    """Publish a test board to the server."""
    # Create a test board
    now = datetime.now(timezone.utc)
    board_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Board</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>Spring '83 Smoke Test</h1>
        <p>This is a test board published by the smoke test script.</p>
        <time datetime="{now.isoformat()}">{now.strftime("%Y-%m-%d %H:%M:%S")}</time>
    </body>
    </html>
    """
    
    # Connect to the server
    conn = http.client.HTTPConnection("127.0.0.1", port)
    headers = {
        "Content-Type": "text/html; charset=utf-8",
        "Spring-Version": "83",
    }
    
    # Publish to the test key
    conn.request("PUT", f"/{TEST_KEY}", body=board_content, headers=headers)
    response = conn.getresponse()
    
    assert response.status == 201, f"Failed to publish board: {response.status} {response.reason}"
    conn.close()
    
    return board_content


def setup_client_config(port):
    """Set up the client configuration."""
    # Create a temporary directory for client config
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / ".83"
    cache_dir = Path(temp_dir) / ".83_cache"
    cache_dir.mkdir()
    
    # Create the config file
    with open(config_path, "w") as f:
        f.write(f"http://127.0.0.1:{port}/{TEST_KEY}\n")
    
    return config_path, cache_dir


def run_client(config_path, cache_dir):
    """Run the client to fetch boards."""
    client_path = Path(__file__).parent.parent / "client" / "spring83_client.py"
    
    process = subprocess.run(
        [
            sys.executable, 
            str(client_path), 
            "--config", 
            str(config_path), 
            "--cache-dir", 
            str(cache_dir),
            "--verbose"
        ],
        capture_output=True,
        text=True,
    )
    
    return process.returncode, process.stdout, process.stderr


def verify_client_output(returncode, stdout, stderr, cache_dir):
    """Verify the client output and cached board."""
    # Check that the client ran successfully
    assert returncode == 0, f"Client failed with return code {returncode}: {stderr}"
    
    # Check that the board was cached
    cache_file = cache_dir / f"{TEST_KEY}.html"
    assert cache_file.exists(), f"Board was not cached at {cache_file}"
    
    # Read the cached board
    with open(cache_file, "r") as f:
        cached_content = f.read()
    
    # Verify the cached content
    assert "Spring '83 Smoke Test" in cached_content, "Cached board doesn't contain expected content"
    assert "<time" in cached_content, "Cached board doesn't contain a time element"
    
    print("✅ Client successfully fetched and cached the board")


def cleanup(server_process, boards_dir, config_path, cache_dir):
    """Clean up temporary files and processes."""
    # Stop the server
    server_process.terminate()
    server_process.wait()
    
    # Clean up temporary directories
    for path in [Path(boards_dir), config_path.parent, cache_dir]:
        if path.exists():
            for file in path.glob("*"):
                file.unlink()
            path.rmdir()


def main():
    """Run the smoke test."""
    print("🚀 Starting Spring '83 smoke test")
    
    # Use a non-standard port to avoid conflicts
    port = 8383
    
    try:
        # Start the server
        print("📡 Starting test server...")
        server_process, boards_dir = run_server(port)
        
        # Publish a board
        print("📝 Publishing test board...")
        board_content = publish_board(port)
        
        # Set up client config
        print("🔧 Setting up client configuration...")
        config_path, cache_dir = setup_client_config(port)
        
        # Run the client
        print("🔍 Running client to fetch boards...")
        returncode, stdout, stderr = run_client(config_path, cache_dir)
        print(stdout)
        
        # Verify the client output
        print("✅ Verifying client output...")
        verify_client_output(returncode, stdout, stderr, cache_dir)
        
        print("🎉 Smoke test passed!")
        return 0
        
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        return 1
        
    finally:
        # Clean up
        if 'server_process' in locals():
            print("🧹 Cleaning up...")
            cleanup(server_process, boards_dir, config_path, cache_dir)


if __name__ == "__main__":
    sys.exit(main())