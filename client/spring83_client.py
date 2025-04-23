#!/usr/bin/env python3
"""
Spring '83 Client

A simple command-line client for fetching Spring '83 boards.
Reads board URLs from ~/.83 and caches them in ~/.83_cache/.
"""

import argparse
import http.client
import os
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Spring83Client:
    """Client for fetching Spring '83 boards."""
    
    def __init__(self, config_path: Path = None, cache_dir: Path = None):
        """
        Initialize the Spring '83 client.
        
        Args:
            config_path: Path to the config file (~/.83)
            cache_dir: Path to the cache directory (~/.83_cache)
        """
        self.config_path = config_path or Path.home() / ".83"
        self.cache_dir = cache_dir or Path.home() / ".83_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def read_config(self) -> List[str]:
        """
        Read the board URLs from the config file.
        
        Returns:
            List[str]: List of board URLs
        """
        if not self.config_path.exists():
            print(f"Config file {self.config_path} does not exist.")
            return []
        
        urls = []
        with open(self.config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        
        return urls
    
    def get_board(self, url: str) -> Tuple[int, Dict[str, str], Optional[bytes]]:
        """
        Fetch a board from a Spring '83 server.
        
        Args:
            url: The URL of the board
            
        Returns:
            Tuple[int, Dict[str, str], Optional[bytes]]: Status code, headers, and content
        """
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path or "/"
        
        # Extract the key from the URL path (if present)
        key = path.strip("/")
        
        # Create cache file path
        cache_file = self.cache_dir / f"{key}.html" if key else self.cache_dir / "index.html"
        
        # Check if we have a cached version and when it was last modified
        if_modified_since = None
        if cache_file.exists():
            mtime = cache_file.stat().st_mtime
            if_modified_since = self.format_http_date(mtime)
        
        # Set up the HTTP connection
        conn = http.client.HTTPSConnection(parsed_url.netloc)
        headers = {
            "Spring-Version": "83",
            "User-Agent": "Spring83Client/0.1"
        }
        
        if if_modified_since:
            headers["If-Modified-Since"] = if_modified_since
        
        # Make the request
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        
        # Read the headers and content
        status = response.status
        headers = {k.lower(): v for k, v in response.getheaders()}
        content = response.read() if status == 200 else None
        
        # Close the connection
        conn.close()
        
        return status, headers, content
    
    def fetch_and_cache(self, urls: List[str], verbose: bool = False) -> None:
        """
        Fetch boards from the provided URLs and cache them.
        
        Args:
            urls: List of board URLs
            verbose: Whether to print verbose output
        """
        for url in urls:
            if verbose:
                print(f"Fetching {url}...")
            
            try:
                status, headers, content = self.get_board(url)
                
                # Extract the key from the URL path
                parsed_url = urllib.parse.urlparse(url)
                path = parsed_url.path or "/"
                key = path.strip("/")
                
                # Create cache file path
                cache_file = self.cache_dir / f"{key}.html" if key else self.cache_dir / "index.html"
                
                if status == 200 and content:
                    # Cache the content
                    with open(cache_file, "wb") as f:
                        f.write(content)
                    
                    print(f"{url}: 200 OK (cached)")
                elif status == 304:
                    print(f"{url}: 304 Not Modified (using cache)")
                else:
                    print(f"{url}: {status} {http.client.responses.get(status, 'Unknown')}")
            except Exception as e:
                print(f"{url}: Error: {e}")
    
    @staticmethod
    def format_http_date(timestamp: float) -> str:
        """
        Format a timestamp as an HTTP date string.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            str: Formatted HTTP date string
        """
        return datetime.utcfromtimestamp(timestamp).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )


def main():
    """Main entry point for the Spring '83 client."""
    parser = argparse.ArgumentParser(description="Spring '83 Client")
    parser.add_argument(
        "--config", 
        type=Path, 
        default=Path.home() / ".83",
        help="Path to config file (default: ~/.83)"
    )
    parser.add_argument(
        "--cache-dir", 
        type=Path, 
        default=Path.home() / ".83_cache",
        help="Path to cache directory (default: ~/.83_cache)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    client = Spring83Client(args.config, args.cache_dir)
    urls = client.read_config()
    
    if not urls:
        print(f"No URLs found in {args.config}. Add URLs to this file, one per line.")
        sys.exit(1)
    
    client.fetch_and_cache(urls, args.verbose)


if __name__ == "__main__":
    main()