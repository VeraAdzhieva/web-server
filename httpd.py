import socketserver
import os
import sys
from datetime import datetime, timezone
from urllib.parse import unquote


MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.swf': 'application/x-shockwave-flash',
    '.txt': 'text/plain',
}

class HTTPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(5)
            data = self.request.recv(65536)
            
            if not data:
                return

            try:
                request_text = data.decode('utf-8', errors='replace')
            except:
                self.send_error(400, "Bad Request")
                return

            lines = request_text.split('\r\n')
            if not lines or not lines[0].strip():
                self.send_error(400, "Bad Request")
                return
            
            first_line = lines[0].split(' ')
            if len(first_line) < 2:
                 self.send_error(400, "Bad Request")
                 return
            
            method = first_line[0]
            path = first_line[1]
            
            if method not in ('GET', 'HEAD'):
                self.send_error(405, "Method Not Allowed")
                return

            decoded_path = unquote(path)
            clean_path = decoded_path.split('?')[0]
            
            doc_root = self.server.doc_root
            full_path = os.path.join(doc_root, clean_path.lstrip('/'))
            
            real_path = os.path.realpath(full_path)
            if not real_path.startswith(os.path.realpath(doc_root)):
                 self.send_error(403, "Forbidden")
                 return

            is_dir = os.path.isdir(real_path)
            is_file = os.path.isfile(real_path)

            if clean_path.endswith('/'):
                if is_dir:
                    real_path = os.path.join(real_path, 'index.html')
                    if not os.path.isfile(real_path):
                        self.send_error(404, "Not Found")
                        return
                else:
                    self.send_error(404, "Not Found")
                    return
            else:
                if is_dir:
                    self.send_error(404, "Not Found")
                    return
                
                if not is_file:
                    self.send_error(404, "Not Found")
                    return

            try:
                with open(real_path, 'rb') as f:
                    file_content = f.read()
            except Exception:
                self.send_error(403, "Forbidden")
                return

            ext = os.path.splitext(real_path)[1].lower()
            content_type = MIME_TYPES.get(ext, 'application/octet-stream')
           
            self.send_response(200, "OK", file_content, content_type, method)

        except Exception as e:
            try:
                self.send_error(500, "Internal Server Error")
            except:
                pass

    def send_response(self, code, text, body, content_type, method):
        headers = {
            'Server': 'HTTPD',
            'Date': datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Connection': 'close',
            'Content-Length': str(len(body)),
            'Content-Type': content_type,
        }
        
        header_str = "\r\n".join([f"{k}: {v}" for k, v in headers.items()])
        response_start = f"HTTP/1.1 {code} {text}\r\n{header_str}\r\n\r\n"
        
        if method == 'HEAD':
            self.request.sendall(response_start.encode('utf-8'))
        else:
            self.request.sendall(response_start.encode('utf-8') + body)

    def send_error(self, code, text):
        body = f"<h1>{code} {text}</h1>".encode('utf-8')
        headers = {
            'Server': 'HTTPD',
            'Date': datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Connection': 'close',
            'Content-Length': str(len(body)),
            'Content-Type': 'text/html',
        }
        header_str = "\r\n".join([f"{k}: {v}" for k, v in headers.items()])
        response = f"HTTP/1.1 {code} {text}\r\n{header_str}\r\n\r\n".encode('utf-8') + body
        self.request.sendall(response)

class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    
    def __init__(self, server_address, handler_class, doc_root):
        self.doc_root = os.path.abspath(doc_root)
        super().__init__(server_address, handler_class)

if __name__ == '__main__':
    if '-r' not in sys.argv:
        sys.exit(1)
        
    root_index = sys.argv.index('-r')
    if root_index + 1 >= len(sys.argv):
        sys.exit(1)
        
    doc_root = sys.argv[root_index + 1]
    
    if not os.path.isdir(doc_root):
        sys.exit(1)

    HOST, PORT = "127.0.0.1", 8080

    with ThreadedHTTPServer((HOST, PORT), HTTPHandler, doc_root) as server:
        server.serve_forever()