import socket
import threading
import json
import time
import sys

HOST = '127.0.0.1'
PORT = 5002

class UDPClient:
    def __init__(self, host=HOST, port=PORT, name="Client_UDP"):
        self.host = host
        self.port = port
        self.name = name
        self.sock = None
        self.running = False
        self.receive_thread = None
        self.on_message_callback = None

    def start(self):
        """Prepares the UDP socket and starts the asynchronous receiver thread."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Set a socket timeout so the recvfrom doesn't block indefinitely on shutdown
            self.sock.settimeout(1.0)
            self.running = True
            
            # Start background thread to receive messages
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            # Start background thread to send periodic heartbeats to register with the UDP server
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            print(f"[UDP CLIENT] Cliente UDP inicializado. Alvo: {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[UDP CLIENT] Falha ao inicializar socket UDP: {e}")
            return False

    def _heartbeat_loop(self):
        """Periodically sends heartbeats to the UDP server to maintain active registration."""
        while self.running:
            try:
                self.send("HEARTBEAT", seq=0)
            except Exception:
                pass
            time.sleep(10)

    def send(self, content, seq=0):
        """Sends a JSON-formatted datagram to the server."""
        if not self.running or not self.sock:
            print("[UDP CLIENT] Cliente não inicializado.")
            return False
        
        payload = {
            "seq": seq,
            "timestamp": time.time(),
            "sender": self.name,
            "content": content
        }
        
        try:
            message_str = json.dumps(payload)
            self.sock.sendto(message_str.encode('utf-8'), (self.host, self.port))
            return True
        except Exception as e:
            print(f"[UDP CLIENT] Erro ao enviar pacote UDP: {e}")
            return False

    def _receive_loop(self):
        """Asynchronously reads datagrams from the socket."""
        while self.running:
            try:
                data, server_address = self.sock.recvfrom(4096)
                if not data:
                    continue
                
                try:
                    msg_data = json.loads(data.decode('utf-8'))
                    if self.on_message_callback:
                        self.on_message_callback(msg_data)
                    else:
                        msg_type = msg_data.get("type", "chat")
                        sender = msg_data.get("sender", "SERVER")
                        content = msg_data.get("content", "")
                        # Only print actual chat broadcasts from other users
                        if msg_type == "chat":
                            sys.stdout.write(f"\r\033[K[{sender} (UDP)]: {content}\n{self.name} > ")
                            sys.stdout.flush()
                except json.JSONDecodeError:
                    print(f"\n[UDP CLIENT] Datagrama recebido inválido: {data.decode('utf-8')}")
                    
            except socket.timeout:
                # Timeout is normal, lets us check if self.running is still True
                continue
            except Exception as e:
                if self.running:
                    print(f"\n[UDP CLIENT] Erro na thread de recebimento UDP: {e}")
                self.running = False
                break

    def stop(self):
        """Stops the receiving thread and closes the socket."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        print("[UDP CLIENT] Cliente UDP parado.")

def run_interactive_chat():
    name = input("Digite seu nome de usuário: ").strip() or "User_UDP"
    client = UDPClient(name=name)
    if client.start():
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
            client.stop()

if __name__ == "__main__":
    run_interactive_chat()
