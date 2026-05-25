import http.server
import socketserver
import json
import os
import sys
import subprocess
import urllib.parse
import threading
import time
import socket
import sqlite3
import hashlib
from benchmark_orchestrator import run_benchmark

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_database.db")

def init_db():
    """Initializes the SQLite database tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    # Create messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocol TEXT NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            seq INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database immediately
init_db()


# Port for the web dashboard server
PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")

# Ensure the dashboard directory exists
if not os.path.exists(DIRECTORY):
    os.makedirs(DIRECTORY)

class DashboardAPIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialize with directory parameter to serve static files from the 'dashboard' folder
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        """Intercepts API GET calls or falls back to serving static files."""
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/api/chat/messages":
            self.handle_chat_messages()
        else:
            super().do_GET()

    def do_POST(self):
        """Intercepts API POST calls."""
        parsed_url = urllib.parse.urlparse(self.path)
        
        if parsed_url.path == "/api/run-benchmark":
            self.handle_run_benchmark()
        elif parsed_url.path == "/api/chat/send":
            self.handle_chat_send()
        elif parsed_url.path == "/api/auth/register":
            self.handle_auth_register()
        elif parsed_url.path == "/api/auth/login":
            self.handle_auth_login()
        else:
            self.send_error(404, "Endpoint não encontrado")

    def handle_chat_messages(self):
        """Returns the full list of received chat messages from the SQLite database."""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT protocol, sender, content, timestamp, seq FROM messages ORDER BY id ASC")
            rows = cursor.fetchall()
            conn.close()
            
            messages = []
            for row in rows:
                messages.append({
                    "protocol": row[0],
                    "sender": row[1],
                    "content": row[2],
                    "timestamp": row[3],
                    "seq": row[4]
                })
            self.send_json_response(messages)
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_auth_register(self):
        """Registers a new user into the SQLite database."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            name = params.get("name", "").strip()
            username = params.get("username", "").strip().lower()
            password = params.get("password", "")
            
            if not name or not username or not password:
                self.send_json_response({"success": False, "error": "Todos os campos são obrigatórios."}, status=400)
                return
                
            password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (name, username, password) VALUES (?, ?, ?)",
                    (name, username, password_hash)
                )
                conn.commit()
                self.send_json_response({"success": True, "message": "Usuário cadastrado com sucesso!"})
            except sqlite3.IntegrityError:
                self.send_json_response({"success": False, "error": "Nome de usuário já cadastrado. Por favor, escolha outro."}, status=400)
            finally:
                conn.close()
                
        except Exception as e:
            self.send_json_response({"success": False, "error": f"Erro de processamento: {str(e)}"}, status=400)

    def handle_auth_login(self):
        """Authenticates a user against the SQLite database."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            username = params.get("username", "").strip().lower()
            password = params.get("password", "")
            
            if not username or not password:
                self.send_json_response({"success": False, "error": "Usuário e senha são obrigatórios."}, status=400)
                return
                
            password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT name, username FROM users WHERE username = ? AND password = ?", (username, password_hash))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                self.send_json_response({
                    "success": True, 
                    "user": {
                        "name": user[0],
                        "username": user[1]
                    }
                })
            else:
                self.send_json_response({"success": False, "error": "Usuário ou senha incorretos."}, status=401)
                
        except Exception as e:
            self.send_json_response({"success": False, "error": f"Erro de processamento: {str(e)}"}, status=400)

    def handle_run_benchmark(self):
        """Runs the benchmark and returns the JSON analysis."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            protocol = params.get("protocol", "TCP")
            num_messages = int(params.get("num_messages", 100))
            interval_ms = int(params.get("interval_ms", 10))
            payload_size_bytes = int(params.get("payload_size_bytes", 128))
            simulated_loss_percent = int(params.get("simulated_loss_percent", 0))
            
            # Execute the orchestrated benchmark
            result = run_benchmark(
                protocol=protocol,
                num_messages=num_messages,
                interval_ms=interval_ms,
                payload_size_bytes=payload_size_bytes,
                simulated_loss_percent=simulated_loss_percent
            )
            
            if result is None:
                self.send_json_response({"error": "Falha ao executar o benchmark"}, status=500)
            else:
                self.send_json_response(result)
                
        except Exception as e:
            self.send_json_response({"error": f"Parâmetros inválidos ou erro interno: {str(e)}"}, status=400)

    def handle_chat_send(self):
        """Sends a single chat message dynamically and returns real-time metrics."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            protocol = params.get("protocol", "TCP").upper()
            sender = params.get("sender", "WebUser")
            content = params.get("content", "Olá!")
            
            # Run one socket interaction depending on the protocol
            if protocol == "TCP":
                self.test_single_tcp_message(sender, content)
            else:
                self.test_single_udp_message(sender, content)
                
        except Exception as e:
            self.send_json_response({"error": f"Erro de processamento: {str(e)}"}, status=400)

    def test_single_tcp_message(self, sender, content):
        """Spins up a temporary TCP connection to send and receive one message."""
        import socket
        import time
        
        # Connects to the standard tcp_server.py port (5001)
        host, port = '127.0.0.1', 5001
        start_time = time.perf_counter()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            
            payload = {
                "seq": 1,
                "timestamp": time.time(),
                "sender": sender,
                "content": content
            }
            
            sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))
            
            # Wait for response
            data = sock.recv(4096)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            
            sock.close()
            
            if data:
                response_str = data.decode('utf-8').strip()
                # Server sends multiple answers separated by newlines (echo and broadcast echo)
                # Parse the first JSON line
                first_line = response_str.split("\n")[0]
                resp_json = json.loads(first_line)
                
                self.send_json_response({
                    "success": True,
                    "rtt_ms": round(elapsed_ms, 3),
                    "response": resp_json
                })
            else:
                self.send_json_response({"success": False, "error": "Servidor não retornou dados"}, status=500)
                
        except ConnectionRefusedError:
            print("[TCP SINGLE MSG] Connection refused on 5001")
            self.send_json_response({
                "success": False, 
                "error": "Conexão Recusada. O servidor TCP (tcp_server.py) está ativo na porta 5001?"
            }, status=503)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def test_single_udp_message(self, sender, content):
        """Sends a single UDP datagram and listens for an echo ACK with a short timeout."""
        import socket
        import time
        
        # Connects to the standard udp_server.py port (5002)
        host, port = '127.0.0.1', 5002
        start_time = time.perf_counter()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.5)
            
            payload = {
                "seq": 1,
                "timestamp": time.time(),
                "sender": sender,
                "content": content
            }
            
            sock.sendto(json.dumps(payload).encode('utf-8'), (host, port))
            
            # Wait for response
            data, server_addr = sock.recvfrom(4096)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            
            sock.close()
            
            if data:
                resp_json = json.loads(data.decode('utf-8'))
                self.send_json_response({
                    "success": True,
                    "rtt_ms": round(elapsed_ms, 3),
                    "response": resp_json
                })
            else:
                self.send_json_response({"success": False, "error": "Servidor UDP não respondeu"}, status=500)
                
        except socket.timeout:
            print("[UDP SINGLE MSG] Socket timeout on 5002")
            self.send_json_response({
                "success": False, 
                "error": "Timeout de resposta. O servidor UDP (udp_server.py) está ativo na porta 5002?"
            }, status=503)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def send_json_response(self, data, status=200):
        """Utility helper to write JSON responses."""
        try:
            response = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            # Add CORS headers so we can run tests across local interfaces
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response)
        except Exception as e:
            print(f"[HTTP SERVER] Erro ao enviar resposta: {e}")

    def end_headers(self):
        """Custom CORS support for pre-flight checks."""
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def start_background_listeners():
    """Starts background listeners to capture broadcasts from TCP and UDP servers."""
    def tcp_listener_thread():
        from tcp_client import TCPClient
        
        def on_tcp_msg(msg_data):
            sender = msg_data.get("sender")
            content = msg_data.get("content")
            msg_type = msg_data.get("type", "chat")
            # Only listen to chat messages broadcasted to other clients
            if msg_type != "chat":
                return
            if content in ("HEARTBEAT", "PING") or sender in ("PingTest", "Bench_TCP"):
                return
            # Save message to SQLite database
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (protocol, sender, content, timestamp, seq) VALUES (?, ?, ?, ?, ?)",
                    ("TCP", sender, content, msg_data.get("timestamp", time.time()), msg_data.get("seq", 0))
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[TCP LISTENER] Erro ao gravar mensagem no banco: {e}")

        client = TCPClient(port=5001, name="WebDashboard_TCP_Listener")
        client.on_message_callback = on_tcp_msg
        
        while True:
            try:
                if not client.running:
                    client.connect()
            except Exception:
                pass
            time.sleep(1)

    def udp_listener_thread():
        from udp_client import UDPClient
        
        def on_udp_msg(msg_data):
            sender = msg_data.get("sender")
            content = msg_data.get("content")
            if content in ("HEARTBEAT", "PING") or sender in ("PingTest", "Bench_UDP"):
                return
            # Save message to SQLite database
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (protocol, sender, content, timestamp, seq) VALUES (?, ?, ?, ?, ?)",
                    ("UDP", sender, content, msg_data.get("timestamp", time.time()), msg_data.get("seq", 0))
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[UDP LISTENER] Erro ao gravar mensagem no banco: {e}")

        client = UDPClient(port=5002, name="WebDashboard_UDP_Listener")
        client.on_message_callback = on_udp_msg
        if client.start():
            # Keep sending heartbeats so the UDP server knows our address and will broadcast to us
            while True:
                try:
                    if client.running:
                        client.send("HEARTBEAT", seq=0)
                except Exception:
                    pass
                time.sleep(5)

    t_tcp = threading.Thread(target=tcp_listener_thread, daemon=True)
    t_tcp.start()
    
    t_udp = threading.Thread(target=udp_listener_thread, daemon=True)
    t_udp.start()

def start_web_server():
    # Use ThreadingTCPServer to avoid blocking the server when performing benchmarks
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True

    # Start the TCP/UDP broadcast background listeners
    start_background_listeners()

    # Automatic startup of the interactive chat servers in the background
    background_servers = []
    
    # Check if TCP server is already running on 5001
    tcp_running = False
    import socket
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(0.2)
        test_sock.connect(('127.0.0.1', 5001))
        tcp_running = True
        test_sock.close()
    except Exception:
        pass

    # Check if UDP server is already running on 5002
    udp_running = False
    try:
        # Binding on port 5002 in UDP will raise an exception if it is already in use
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(('127.0.0.1', 5002))
        test_sock.close()
    except Exception:
        # Port is already bound, meaning another process (or our udp_server) is active
        udp_running = True

    if not tcp_running:
        print("[DASHBOARD SERVER] Inicializando Servidor TCP Interativo (tcp_server.py) na porta 5001...")
        p_tcp = subprocess.Popen([sys.executable, "tcp_server.py", "5001"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        background_servers.append(p_tcp)
        
    if not udp_running:
        print("[DASHBOARD SERVER] Inicializando Servidor UDP Interativo (udp_server.py) na porta 5002...")
        p_udp = subprocess.Popen([sys.executable, "udp_server.py", "5002", "0"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        background_servers.append(p_udp)

    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardAPIHandler)
    print(f"\n[DASHBOARD SERVER] Servidor web iniciado com sucesso!")
    print(f"=========================================================")
    print(f"  Abra em seu navegador: http://localhost:{PORT}")
    print(f"=========================================================")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[DASHBOARD SERVER] Encerrando servidor web.")
    finally:
        server.server_close()
        # Clean up background servers
        for bg_s in background_servers:
            try:
                bg_s.terminate()
                bg_s.wait()
            except Exception:
                pass
        print("[DASHBOARD SERVER] Servidor web encerrado.")

if __name__ == "__main__":
    start_web_server()

