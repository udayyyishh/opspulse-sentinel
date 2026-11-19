"""Mock internal microservice used by docker-compose to simulate healthy and flaky services."""
import random
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

FLAKY_MODE = True


class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            # Normal healthy endpoint
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy","uptime":3600}')
        elif self.path == "/flaky":
            # Randomly slow or returns 500 to test alerting
            time.sleep(random.uniform(0.1, 1.2))
            if random.random() < 0.4:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"intermittent upstream failure"}')
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok_after_delay"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence standard HTTP access logs for clean container output
        return


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), MockHandler)
    print("Mock Microservice running on port 8080 (/health, /flaky)...")
    server.serve_forever()
