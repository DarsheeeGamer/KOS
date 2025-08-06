"""
Web server functionality for KOS
"""

import time
import json
import mimetypes
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, parse_qs

class HTTPMethod(Enum):
    """HTTP methods"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"

class HTTPStatus:
    """HTTP status codes"""
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    MOVED_PERMANENTLY = 301
    FOUND = 302
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    SERVICE_UNAVAILABLE = 503

@dataclass
class Request:
    """HTTP request"""
    method: HTTPMethod
    path: str
    headers: Dict[str, str]
    params: Dict[str, List[str]]
    body: bytes
    client_addr: str
    
    def get_param(self, name: str, default: str = None) -> Optional[str]:
        """Get query parameter"""
        values = self.params.get(name, [])
        return values[0] if values else default
    
    def get_header(self, name: str, default: str = None) -> Optional[str]:
        """Get header value"""
        return self.headers.get(name.lower(), default)
    
    def json(self) -> Any:
        """Parse body as JSON"""
        try:
            return json.loads(self.body.decode())
        except:
            return None

@dataclass
class Response:
    """HTTP response"""
    status: int = HTTPStatus.OK
    headers: Dict[str, str] = None
    body: bytes = b''
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
    
    def set_header(self, name: str, value: str):
        """Set response header"""
        self.headers[name] = value
    
    def json(self, data: Any):
        """Set JSON response body"""
        self.body = json.dumps(data).encode()
        self.set_header('Content-Type', 'application/json')
    
    def html(self, content: str):
        """Set HTML response body"""
        self.body = content.encode()
        self.set_header('Content-Type', 'text/html')
    
    def text(self, content: str):
        """Set plain text response body"""
        self.body = content.encode()
        self.set_header('Content-Type', 'text/plain')
    
    def redirect(self, location: str, permanent: bool = False):
        """Set redirect response"""
        self.status = HTTPStatus.MOVED_PERMANENTLY if permanent else HTTPStatus.FOUND
        self.set_header('Location', location)

class WebServer:
    """HTTP web server"""
    
    def __init__(self, vfs=None, host: str = "0.0.0.0", port: int = 8080):
        self.vfs = vfs
        self.host = host
        self.port = port
        self.running = False
        
        # Routes
        self.routes: Dict[str, Dict[HTTPMethod, Callable]] = {}
        self.static_dirs: List[str] = []
        
        # Middleware
        self.middleware: List[Callable] = []
        
        # Configuration
        self.config = {
            'max_request_size': 10485760,  # 10MB
            'timeout': 30,
            'keep_alive': True,
            'compress': True
        }
        
        # Default routes
        self._setup_default_routes()
    
    def _setup_default_routes(self):
        """Setup default routes"""
        self.route('/', HTTPMethod.GET, self._index_handler)
        self.route('/health', HTTPMethod.GET, self._health_handler)
    
    def _index_handler(self, request: Request) -> Response:
        """Default index handler"""
        response = Response()
        response.html("""
        <html>
        <head><title>KOS Web Server</title></head>
        <body>
            <h1>Welcome to KOS Web Server</h1>
            <p>Server is running on {}:{}</p>
        </body>
        </html>
        """.format(self.host, self.port))
        return response
    
    def _health_handler(self, request: Request) -> Response:
        """Health check handler"""
        response = Response()
        response.json({
            'status': 'healthy',
            'timestamp': time.time(),
            'uptime': time.time()  # Would calculate actual uptime
        })
        return response
    
    def route(self, path: str, method: HTTPMethod, handler: Callable):
        """Add route handler"""
        if path not in self.routes:
            self.routes[path] = {}
        
        self.routes[path][method] = handler
    
    def add_static_directory(self, directory: str):
        """Add static file directory"""
        self.static_dirs.append(directory)
    
    def use_middleware(self, middleware: Callable):
        """Add middleware"""
        self.middleware.append(middleware)
    
    def handle_request(self, request: Request) -> Response:
        """Handle HTTP request"""
        # Apply middleware
        for mw in self.middleware:
            result = mw(request)
            if isinstance(result, Response):
                return result
        
        # Check routes
        if request.path in self.routes:
            if request.method in self.routes[request.path]:
                handler = self.routes[request.path][request.method]
                return handler(request)
            else:
                # Method not allowed
                response = Response(status=HTTPStatus.METHOD_NOT_ALLOWED)
                response.text("Method not allowed")
                return response
        
        # Check static files
        for static_dir in self.static_dirs:
            file_path = f"{static_dir}{request.path}"
            if self.vfs and self.vfs.exists(file_path):
                return self._serve_static_file(file_path)
        
        # 404 Not Found
        response = Response(status=HTTPStatus.NOT_FOUND)
        response.text("Not found")
        return response
    
    def _serve_static_file(self, file_path: str) -> Response:
        """Serve static file"""
        if not self.vfs:
            return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
        try:
            # Read file
            with self.vfs.open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'application/octet-stream'
            
            # Create response
            response = Response()
            response.body = content
            response.set_header('Content-Type', content_type)
            response.set_header('Content-Length', str(len(content)))
            
            return response
        except:
            return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
    
    def start(self):
        """Start web server (simulated)"""
        self.running = True
        print(f"Web server listening on {self.host}:{self.port}")
    
    def stop(self):
        """Stop web server"""
        self.running = False
        print("Web server stopped")

class RESTfulAPI:
    """RESTful API framework"""
    
    def __init__(self, server: WebServer):
        self.server = server
        self.resources: Dict[str, 'Resource'] = {}
    
    def add_resource(self, resource: 'Resource', path: str):
        """Add REST resource"""
        self.resources[path] = resource
        
        # Register routes
        base_path = f"/api{path}"
        
        # Collection routes
        self.server.route(base_path, HTTPMethod.GET, 
                         lambda req: resource.list(req))
        self.server.route(base_path, HTTPMethod.POST,
                         lambda req: resource.create(req))
        
        # Item routes
        item_path = f"{base_path}/{{id}}"
        self.server.route(item_path, HTTPMethod.GET,
                         lambda req: resource.get(req))
        self.server.route(item_path, HTTPMethod.PUT,
                         lambda req: resource.update(req))
        self.server.route(item_path, HTTPMethod.DELETE,
                         lambda req: resource.delete(req))

class Resource:
    """REST resource base class"""
    
    def list(self, request: Request) -> Response:
        """List resources"""
        response = Response(status=HTTPStatus.NOT_IMPLEMENTED)
        response.text("Not implemented")
        return response
    
    def get(self, request: Request) -> Response:
        """Get single resource"""
        response = Response(status=HTTPStatus.NOT_IMPLEMENTED)
        response.text("Not implemented")
        return response
    
    def create(self, request: Request) -> Response:
        """Create resource"""
        response = Response(status=HTTPStatus.NOT_IMPLEMENTED)
        response.text("Not implemented")
        return response
    
    def update(self, request: Request) -> Response:
        """Update resource"""
        response = Response(status=HTTPStatus.NOT_IMPLEMENTED)
        response.text("Not implemented")
        return response
    
    def delete(self, request: Request) -> Response:
        """Delete resource"""
        response = Response(status=HTTPStatus.NOT_IMPLEMENTED)
        response.text("Not implemented")
        return response

class WebSocketServer:
    """WebSocket server (simulated)"""
    
    def __init__(self, vfs=None, port: int = 8081):
        self.vfs = vfs
        self.port = port
        self.connections: Dict[str, 'WebSocketConnection'] = {}
        self.handlers: Dict[str, Callable] = {}
    
    def on(self, event: str, handler: Callable):
        """Register event handler"""
        self.handlers[event] = handler
    
    def broadcast(self, message: str):
        """Broadcast message to all connections"""
        for conn in self.connections.values():
            conn.send(message)
    
    def emit(self, connection_id: str, message: str):
        """Send message to specific connection"""
        if connection_id in self.connections:
            self.connections[connection_id].send(message)

@dataclass
class WebSocketConnection:
    """WebSocket connection"""
    id: str
    remote_addr: str
    connected_at: float
    
    def send(self, message: str):
        """Send message (simulated)"""
        print(f"WS [{self.id}] <- {message}")
    
    def close(self):
        """Close connection"""
        pass

class TemplateEngine:
    """Simple template engine"""
    
    def __init__(self, vfs=None, template_dir: str = "/var/www/templates"):
        self.vfs = vfs
        self.template_dir = template_dir
        self.cache: Dict[str, str] = {}
    
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with context"""
        # Load template
        template = self._load_template(template_name)
        if not template:
            return ""
        
        # Simple variable replacement
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        # Simple conditionals
        import re
        
        # {% if condition %} ... {% endif %}
        if_pattern = r'{%\s*if\s+(\w+)\s*%}(.*?){%\s*endif\s*%}'
        for match in re.finditer(if_pattern, result, re.DOTALL):
            condition = match.group(1)
            content = match.group(2)
            
            if context.get(condition):
                result = result.replace(match.group(0), content)
            else:
                result = result.replace(match.group(0), '')
        
        # {% for item in items %} ... {% endfor %}
        for_pattern = r'{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}(.*?){%\s*endfor\s*%}'
        for match in re.finditer(for_pattern, result, re.DOTALL):
            item_var = match.group(1)
            items_var = match.group(2)
            content = match.group(3)
            
            items = context.get(items_var, [])
            loop_result = []
            
            for item in items:
                item_content = content.replace(f"{{{{{item_var}}}}}", str(item))
                loop_result.append(item_content)
            
            result = result.replace(match.group(0), ''.join(loop_result))
        
        return result
    
    def _load_template(self, template_name: str) -> Optional[str]:
        """Load template from file"""
        # Check cache
        if template_name in self.cache:
            return self.cache[template_name]
        
        if not self.vfs:
            return None
        
        template_path = f"{self.template_dir}/{template_name}"
        
        try:
            with self.vfs.open(template_path, 'r') as f:
                template = f.read().decode()
            
            # Cache template
            self.cache[template_name] = template
            return template
        except:
            return None

class Session:
    """Web session management"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.timeout = 3600  # 1 hour
    
    def create_session(self) -> str:
        """Create new session"""
        import secrets
        session_id = secrets.token_hex(16)
        
        self.sessions[session_id] = {
            'id': session_id,
            'created': time.time(),
            'last_accessed': time.time(),
            'data': {}
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check timeout
        if time.time() - session['last_accessed'] > self.timeout:
            del self.sessions[session_id]
            return None
        
        # Update last accessed
        session['last_accessed'] = time.time()
        
        return session
    
    def destroy_session(self, session_id: str):
        """Destroy session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def set_data(self, session_id: str, key: str, value: Any):
        """Set session data"""
        if session_id in self.sessions:
            self.sessions[session_id]['data'][key] = value
    
    def get_data(self, session_id: str, key: str) -> Any:
        """Get session data"""
        if session_id in self.sessions:
            return self.sessions[session_id]['data'].get(key)