import socket
import json
import random
import sys
import threading
import time

HOST = '127.0.0.1'
PORT = 5002

# Registry of active UDP clients: client_address (tuple) -> last_seen_timestamp (float)
udp_clients = {}
clients_lock = threading.Lock()
CLIENT_TIMEOUT = 60.0 # Time in seconds to prune inactive clients

def start_server(host=HOST, port=PORT, loss_rate=0.0):
    """
    Starts the UDP socket server.
    
    :param host: Server bind address
    :param port: Server bind port
    :param loss_rate: Artificial package loss rate between 0.0 (0%) and 1.0 (100%)
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        server_socket.bind((host, port))
        print(f"[UDP SERVER] Servidor UDP rodando em {host}:{port}")
        if loss_rate > 0.0:
            print(f"[UDP SERVER] Simulador de Perda Ativo: {loss_rate * 100:.1f}% dos pacotes serão descartados.")
        
        while True:
            try:
                data, client_address = server_socket.recvfrom(4096)
                if not data:
                    continue
                
                # Apply artificial packet loss simulation
                if loss_rate > 0.0 and random.random() < loss_rate:
                    # Parse sequence number if possible, just for logging the drop
                    try:
                        msg_str = data.decode('utf-8')
                        msg_data = json.loads(msg_str)
                        seq = msg_data.get("seq", -1)
                        print(f"[UDP SERVER] [SIMULATED DROP] Descartando seq={seq} de {client_address}")
                    except Exception:
                        print(f"[UDP SERVER] [SIMULATED DROP] Descartando pacote raw de {client_address}")
                    continue
                
                message_str = data.decode('utf-8')
                try:
                    msg_data = json.loads(message_str)
                    seq = msg_data.get("seq", 0)
                    ts = msg_data.get("timestamp", 0)
                    sender = msg_data.get("sender", "Anônimo")
                    content = msg_data.get("content", "")
                    
                    print(f"[UDP SERVER] Recebido de {sender}: seq={seq}, msg='{content}' de {client_address}")
                    
                    # Echo back to the sender for RTT measurement
                    response = {
                        "type": "echo",
                        "seq": seq,
                        "timestamp": ts,
                        "sender": "SERVER",
                        "content": content
                    }
                    server_socket.sendto(json.dumps(response).encode('utf-8'), client_address)
                    
                    # Register/update client in the dynamic registry
                    current_time = time.time()
                    with clients_lock:
                        udp_clients[client_address] = current_time
                        
                        # Prune inactive clients
                        inactive = [addr for addr, last_seen in udp_clients.items() if current_time - last_seen > CLIENT_TIMEOUT]
                        for addr in inactive:
                            del udp_clients[addr]
                        
                        # Broadcast real chat messages to all other registered clients
                        if content != "HEARTBEAT" and content != "PING" and sender != "PingTest":
                            chat_broadcast = {
                                "type": "chat",
                                "seq": seq,
                                "timestamp": ts,
                                "sender": sender,
                                "content": content
                            }
                            broadcast_bytes = (json.dumps(chat_broadcast) + "\n").encode('utf-8')
                            for other_addr in list(udp_clients.keys()):
                                if other_addr != client_address:
                                    try:
                                        server_socket.sendto(broadcast_bytes, other_addr)
                                    except Exception:
                                        pass
                                        
                except json.JSONDecodeError:
                    print(f"[UDP SERVER] Recebido raw text: {message_str} de {client_address}")
                    # Simple echo back
                    server_socket.sendto(data, client_address)
                    
            except Exception as e:
                print(f"[UDP SERVER] Erro ao processar datagrama: {e}")
                
    except KeyboardInterrupt:
        print("\n[UDP SERVER] Encerrando servidor por solicitação do usuário.")
    except Exception as e:
        print(f"[UDP SERVER] Erro no servidor UDP: {e}")
    finally:
        server_socket.close()
        print("[UDP SERVER] Servidor encerrado.")

if __name__ == "__main__":
    port = PORT
    loss = 0.0
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
            
    if len(sys.argv) > 2:
        try:
            loss = float(sys.argv[2]) / 100.0 # Convert percentage to float
            if not (0.0 <= loss <= 1.0):
                loss = 0.0
        except ValueError:
            pass
            
    start_server(port=port, loss_rate=loss)
