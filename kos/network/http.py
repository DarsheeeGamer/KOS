"""
HTTP client for KOS
"""

import time
import json
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class HTTPResponse:
    """HTTP response"""
    status_code: int
    headers: Dict[str, str]
    body: str
    url: str
    elapsed: float

class HTTPClient:
    """Simple HTTP client for KOS"""
    
    def __init__(self, dns_resolver=None):
        self.dns_resolver = dns_resolver
        self.timeout = 30
        self.user_agent = "KOS-HTTP/1.0"
        self.session_cookies: Dict[str, str] = {}
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> HTTPResponse:
        """HTTP GET request"""
        return self._request("GET", url, headers=headers)
    
    def post(self, url: str, data: Optional[Any] = None, 
             headers: Optional[Dict[str, str]] = None) -> HTTPResponse:
        """HTTP POST request"""
        return self._request("POST", url, data=data, headers=headers)
    
    def put(self, url: str, data: Optional[Any] = None,
            headers: Optional[Dict[str, str]] = None) -> HTTPResponse:
        """HTTP PUT request"""
        return self._request("PUT", url, data=data, headers=headers)
    
    def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> HTTPResponse:
        """HTTP DELETE request"""
        return self._request("DELETE", url, headers=headers)
    
    def _request(self, method: str, url: str, data: Optional[Any] = None,
                headers: Optional[Dict[str, str]] = None) -> HTTPResponse:
        """Make HTTP request (simulated)"""
        start_time = time.time()
        
        # Parse URL
        scheme, host, port, path = self._parse_url(url)
        
        # Resolve hostname if needed
        if self.dns_resolver and not self._is_ip(host):
            ip = self.dns_resolver.resolve(host)
            if not ip:
                # DNS resolution failed
                return HTTPResponse(
                    status_code=0,
                    headers={},
                    body="DNS resolution failed",
                    url=url,
                    elapsed=time.time() - start_time
                )
        
        # Simulate HTTP request/response
        response = self._simulate_http(method, url, data, headers)
        response.elapsed = time.time() - start_time
        
        return response
    
    def _parse_url(self, url: str) -> Tuple[str, str, int, str]:
        """Parse URL into components"""
        # Simple URL parsing
        if "://" in url:
            scheme, rest = url.split("://", 1)
        else:
            scheme = "http"
            rest = url
        
        if "/" in rest:
            host_port, path = rest.split("/", 1)
            path = "/" + path
        else:
            host_port = rest
            path = "/"
        
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            port = int(port)
        else:
            host = host_port
            port = 443 if scheme == "https" else 80
        
        return scheme, host, port, path
    
    def _is_ip(self, host: str) -> bool:
        """Check if host is an IP address"""
        parts = host.split(".")
        if len(parts) != 4:
            return False
        try:
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except:
            return False
    
    def _simulate_http(self, method: str, url: str, data: Optional[Any],
                      headers: Optional[Dict[str, str]]) -> HTTPResponse:
        """Simulate HTTP response"""
        # Simulate network delay
        time.sleep(0.1)
        
        # Default headers
        response_headers = {
            "Content-Type": "text/html",
            "Server": "KOS-Simulator/1.0",
            "Date": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        
        # Simulate responses for known URLs
        if "google.com" in url:
            return HTTPResponse(
                status_code=200,
                headers=response_headers,
                body="<html><head><title>Google</title></head><body>Google Search (simulated)</body></html>",
                url=url,
                elapsed=0
            )
        elif "github.com" in url:
            if "/api" in url:
                response_headers["Content-Type"] = "application/json"
                body = json.dumps({"message": "API response", "status": "ok"})
            else:
                body = "<html><head><title>GitHub</title></head><body>GitHub (simulated)</body></html>"
            
            return HTTPResponse(
                status_code=200,
                headers=response_headers,
                body=body,
                url=url,
                elapsed=0
            )
        elif "example.com" in url:
            return HTTPResponse(
                status_code=200,
                headers=response_headers,
                body="<html><head><title>Example Domain</title></head><body><h1>Example Domain</h1><p>This domain is for examples.</p></body></html>",
                url=url,
                elapsed=0
            )
        elif url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
            # Local server response
            return HTTPResponse(
                status_code=200,
                headers=response_headers,
                body="<html><head><title>KOS Local Server</title></head><body><h1>Welcome to KOS</h1><p>Local server is running.</p></body></html>",
                url=url,
                elapsed=0
            )
        else:
            # Default 404 response
            return HTTPResponse(
                status_code=404,
                headers=response_headers,
                body="<html><head><title>404 Not Found</title></head><body><h1>404 Not Found</h1></body></html>",
                url=url,
                elapsed=0
            )
    
    def download(self, url: str, filepath: str, vfs=None) -> bool:
        """Download file from URL"""
        response = self.get(url)
        
        if response.status_code == 200 and vfs:
            try:
                with vfs.open(filepath, 'wb') as f:
                    f.write(response.body.encode())
                return True
            except:
                pass
        
        return False
    
    def set_timeout(self, timeout: float):
        """Set request timeout"""
        self.timeout = timeout
    
    def set_user_agent(self, user_agent: str):
        """Set user agent string"""
        self.user_agent = user_agent