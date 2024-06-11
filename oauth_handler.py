from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import threading

# Global variables to store the code and state
code = None
state = None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global code, state
        # Parse the URL to get the query parameters
        parsed_path = urlparse.urlparse(self.path)
        query_params = urlparse.parse_qs(parsed_path.query)

        # Extract 'code' and 'state' parameters
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]

        # Log the received code and state
        print(f"Received code: {code}")
        print(f"Received state: {state}")

        # Send a response to the client
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"OAuth code and state received. You can close this window.")

        # Signal the server to stop
        self.server.stop_event.set()
        return code, state


class StoppableHTTPServer(HTTPServer):
    def serve_forever(self):
        self.stop_event = threading.Event()
        while not self.stop_event.is_set():
            self.handle_request()


def run(server_class=StoppableHTTPServer, handler_class=OAuthHandler, port=6414):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting HTTP server on port {port}")
    httpd.serve_forever()
    print("Server stopped.")


if __name__ == '__main__':
    run()
