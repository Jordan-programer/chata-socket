import socket
import threading
import json
import time
import sys

HOST = '127.0.0.1'
PORT = 5001

class TCPClient:
    def __init__(self, host=HOST, port=PORT, name="Client_TCP"):
        self.host = host
        self.port = port
        self.name = name
        self.sock = None
        self.running = False
        self.receive_thread = None
        self.on_message_callback = None
        self.buffer = ""

    def connect(self):
        """Establishes connection to the TCP server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.connect((self.host, self.port))
            self.running = True
            
            # Start background thread to receive messages
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            print(f"[TCP CLIENT] Conectado com sucesso ao servidor TCP em {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[TCP CLIENT] Falha ao conectar em {self.host}:{self.port} - Erro: {e}")
            return False

    def send(self, content, seq=0):
        """Sends a JSON-formatted message to the server."""
        if not self.running or not self.sock:
            print("[TCP CLIENT] Não conectado ao servidor.")
            return False
        
        payload = {
            "seq": seq,
            "timestamp": time.time(),
            "sender": self.name,
            "content": content
        }
        
        try:
            # We append a newline for framing (so receiver can split easily)
            message_str = json.dumps(payload) + "\n"
            self.sock.sendall(message_str.encode('utf-8'))
            return True
        except Exception as e:
            print(f"[TCP CLIENT] Erro ao enviar mensagem: {e}")
            self.disconnect()
            return False

    def _receive_loop(self):
        """Asynchronously reads data from the socket and decodes framed JSON messages."""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    print("[TCP CLIENT] Conexão encerrada pelo servidor.")
                    self.running = False
                    break
                
                # Append to buffer and split by newline to handle TCP streaming splits/merges
                self.buffer += data.decode('utf-8')
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    
                    try:
                        msg_data = json.loads(line)
                        if self.on_message_callback:
                            self.on_message_callback(msg_data)
                        else:
                            msg_type = msg_data.get("type", "chat")
                            sender = msg_data.get("sender", "SERVER")
                            content = msg_data.get("content", "")
                            # Only print actual chat broadcasts from other users
                            if msg_type == "chat":
                                sys.stdout.write(f"\r\033[K[{sender}]: {content}\n{self.name} > ")
                                sys.stdout.flush()
                    except json.JSONDecodeError:
                        print(f"\n[TCP CLIENT] Mensagem recebida inválida: {line}")
                        
            except (ConnectionResetError, ConnectionAbortedError):
                print("\n[TCP CLIENT] Desconectado do servidor.")
                self.running = False
                break
            except Exception as e:
                if self.running:
                    print(f"\n[TCP CLIENT] Erro na thread de recebimento: {e}")
                self.running = False
                break

    def disconnect(self):
        """Closes the client connection."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        print("[TCP CLIENT] Cliente desconectado.")

def run_interactive_chat():
    name = input("Digite seu nome de usuário: ").strip() or "User_TCP"
    client = TCPClient(name=name)
    if client.connect():
        print("Digite suas mensagens abaixo. Digite '/sair' para fechar.")
        try:
            seq = 1
            while client.running:
                text = input(f"{name} > ").strip()
                if not text:
                    continue
                if text.lower() == '/sair':
                    break
                client.send(text, seq=seq)
                seq += 1
                time.sleep(0.1) # Small delay for clean prompt redraw
        except KeyboardInterrupt:
            pass
        finally:
            client.disconnect()

if __name__ == "__main__":
    run_interactive_chat()
