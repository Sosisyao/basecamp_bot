import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests

CLIENT_ID = "ac0c795000fec931a74525eefef5f187e535c03c"
CLIENT_SECRET = "d3c372d35789170ef9cc4b09fa9797cf04964719"
REDIRECT_URI = "http://localhost:8080/"

AUTH_URL = f"https://launchpad.37signals.com/authorization/new?type=web_server&client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"

class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        if 'code' in query:
            code = query['code'][0]
            token = exchange_code_for_token(code)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<h1>Access Token:</h1><p>{token}</p>".encode())
            print(f"\n🔐 Access Token: {token}\n")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing authorization code.")

def exchange_code_for_token(code):
    url = "https://launchpad.37signals.com/authorization/token"
    data = {
        "type": "web_server",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()['access_token']

def run_server():
    print("🌐 Откроется окно браузера — нажми 'Yes, allow'")
    webbrowser.open(AUTH_URL)
    server = HTTPServer(('localhost', 8080), AuthHandler)
    server.handle_request()

if __name__ == '__main__':
    run_server() 