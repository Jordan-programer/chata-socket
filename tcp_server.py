import socket
import threading
import json
import sys

HOST = '127.0.0.1'
PORT = 5001

clients = []
clients_lock = threading.Lock()

def broadcast(message, sender_socket=None):
    """Sends a message to all connected clients except the sender."""
    with clients_lock:
        for client in clients:
            if client != sender_socket:
                try:
                    client.sendall(message.encode('utf-8'))
                except Exception:
                    # If sending fails, client will be removed in its connection thread
                    pass

def handle_client(client_socket, client_address):
    """Handles communication with a single connected client."""
    print(f"[TCP SERVER] Nova conexão de {client_address[0]}:{client_address[1]}")
    with clients_lock:
        clients.append(client_socket)
    
    try:
        while True:
            data = client_socket.recv(4096)
            if not data:
                break
            
            message_str = data.decode('utf-8')
            try:
                # Expect JSON message
                msg_data = json.loads(message_str)
                seq = msg_data.get("seq", 0)
                ts = msg_data.get("timestamp", 0)
                sender = msg_data.get("sender", "Anônimo")
                content = msg_data.get("content", "")
                
                print(f"[TCP SERVER] Recebido de {sender}: seq={seq}, msg='{content}'")
                
                # Echo back to the sender for RTT measurement
                response = {
                    "type": "echo",
                    "seq": seq,
                    "timestamp": ts,
                    "sender": "SERVER",
                    "content": content
                }
                client_socket.sendall((json.dumps(response) + "\n").encode('utf-8'))
                
                # Broadcast the message to other chat clients (as a chat message)
                chat_broadcast = {
                    "type": "chat",
                    "seq": seq,
                    "timestamp": ts,
                    "sender": sender,
                    "content": content
                }
                broadcast(json.dumps(chat_broadcast) + "\n", client_socket)
                
            except json.JSONDecodeError:
                # If not JSON, treat as raw text
                print(f"[TCP SERVER] Recebido raw text: {message_str}")
                # Simple echo back
                client_socket.sendall(data)
                
    except ConnectionResetError:
        print(f"[TCP SERVER] Conexão resetada pelo cliente {client_address}")
    except Exception as e:
        print(f"[TCP SERVER] Erro ao tratar cliente {client_address}: {e}")
    finally:
        with clients_lock:
            if client_socket in clients:
                clients.remove(client_socket)
        client_socket.close()
        print(f"[TCP SERVER] Conexão encerrada com {client_address}")

def start_server(host=HOST, port=PORT):
    """Starts the TCP socket server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow address/port reuse to prevent "address already in use" errors on restarts
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(10)
        print(f"[TCP SERVER] Servidor TCP rodando em {host}:{port}")
        
        while True:
            client_socket, client_address = server_socket.accept()
            # Handle socket timeout or keepalive if necessary
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            t = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
            t.start()
            
    except KeyboardInterrupt:
        print("\n[TCP SERVER] Encerrando servidor por solicitação do usuário.")
    except Exception as e:
        print(f"[TCP SERVER] Erro no servidor: {e}")
    finally:
        server_socket.close()
        print("[TCP SERVER] Servidor encerrado.")

if __name__ == "__main__":
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port=port)
