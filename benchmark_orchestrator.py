import os
import sys
import time
import subprocess
import threading
import json
import socket
import psutil  # Checked as installed in previous step

from tcp_client import TCPClient
from udp_client import UDPClient

# Ports dedicated to benchmarking to avoid conflict with interactive sessions
BENCHMARK_TCP_PORT = 6001
BENCHMARK_UDP_PORT = 6002

class ResourceMonitor(threading.Thread):
    """Periodically samples CPU and RAM usage of server and client processes."""
    def __init__(self, server_pid, sample_interval=0.05):
        super().__init__()
        self.server_pid = server_pid
        self.sample_interval = sample_interval
        self.running = False
        
        self.server_cpu_samples = []
        self.server_ram_samples = []
        self.client_cpu_samples = []
        self.client_ram_samples = []
        
        try:
            self.server_proc = psutil.Process(server_pid)
            self.client_proc = psutil.Process(os.getpid())
        except Exception:
            self.server_proc = None
            self.client_proc = None

    def run(self):
        self.running = True
        # First sample CPU to initialize psutil interval logic
        if self.server_proc and self.client_proc:
            try:
                self.server_proc.cpu_percent(interval=None)
                self.client_proc.cpu_percent(interval=None)
            except Exception:
                pass
                
        while self.running:
            time.sleep(self.sample_interval)
            if not self.running:
                break
                
            if self.server_proc and self.client_proc:
                try:
                    # Capture server metrics
                    with self.server_proc.oneshot():
                        # Divide by number of CPU cores to get system-relative or keep it as process percentage
                        # psutil cpu_percent can sometimes go above 100% on multi-core, which is standard process-level CPU
                        s_cpu = self.server_proc.cpu_percent(interval=None)
                        s_ram = self.server_proc.memory_info().rss / (1024 * 1024) # MB
                        self.server_cpu_samples.append(s_cpu)
                        self.server_ram_samples.append(s_ram)
                        
                    # Capture client metrics
                    with self.client_proc.oneshot():
                        c_cpu = self.client_proc.cpu_percent(interval=None)
                        c_ram = self.client_proc.memory_info().rss / (1024 * 1024) # MB
                        self.client_cpu_samples.append(c_cpu)
                        self.client_ram_samples.append(c_ram)
                except Exception:
                    # Subprocess might have closed or permission error
                    pass

    def stop(self):
        self.running = False

    def get_averages(self):
        avg_server_cpu = sum(self.server_cpu_samples) / len(self.server_cpu_samples) if self.server_cpu_samples else 0.0
        avg_server_ram = sum(self.server_ram_samples) / len(self.server_ram_samples) if self.server_ram_samples else 0.0
        avg_client_cpu = sum(self.client_cpu_samples) / len(self.client_cpu_samples) if self.client_cpu_samples else 0.0
        avg_client_ram = sum(self.client_ram_samples) / len(self.client_ram_samples) if self.client_ram_samples else 0.0
        
        return {
            "server_cpu_percent": round(avg_server_cpu, 2),
            "server_ram_mb": round(avg_server_ram, 2),
            "client_cpu_percent": round(avg_client_cpu, 2),
            "client_ram_mb": round(avg_client_ram, 2)
        }


def run_benchmark(protocol, num_messages=100, interval_ms=10, payload_size_bytes=128, simulated_loss_percent=0):
    """
    Executes a comprehensive benchmark run for TCP or UDP.
    
    :param protocol: 'TCP' or 'UDP'
    :param num_messages: Total messages to send
    :param interval_ms: Delay between messages in milliseconds
    :param payload_size_bytes: Size of string payload to send
    :param simulated_loss_percent: (UDP only) Artificial package loss rate percentage
    """
    protocol = protocol.upper()
    print(f"\n[BENCHMARK] Iniciando teste {protocol}...")
    print(f"            Mensagens: {num_messages}, Intervalo: {interval_ms}ms, Tamanho Payload: {payload_size_bytes}B")
    if protocol == 'UDP':
        print(f"            Perda UDP Simulada: {simulated_loss_percent}%")

    # 1. Start Server Subprocess
    server_process = None
    if protocol == 'TCP':
        server_process = subprocess.Popen([sys.executable, "tcp_server.py", str(BENCHMARK_TCP_PORT)],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        server_process = subprocess.Popen([sys.executable, "udp_server.py", str(BENCHMARK_UDP_PORT), str(simulated_loss_percent)],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for server to bind
    time.sleep(0.5)

    # 2. Setup telemetry structures
    send_times = {}
    recv_times = {}
    arrival_sequence = []
    
    # Lock for thread-safe access to telemetry lists
    telemetry_lock = threading.Lock()

    def on_message_received(msg_data):
        recv_time = time.perf_counter()
        seq = msg_data.get("seq", 0)
        with telemetry_lock:
            recv_times[seq] = recv_time
            arrival_sequence.append(seq)

    # 3. Instantiate and start Client
    client = None
    client_started = False
    
    if protocol == 'TCP':
        client = TCPClient(port=BENCHMARK_TCP_PORT, name="Bench_TCP")
        client.on_message_callback = on_message_received
        client_started = client.connect()
    else:
        client = UDPClient(port=BENCHMARK_UDP_PORT, name="Bench_UDP")
        client.on_message_callback = on_message_received
        client_started = client.start()

    if not client_started:
        print("[BENCHMARK] Falha ao iniciar cliente de teste. Cancelando.")
        if server_process:
            server_process.terminate()
            server_process.wait()
        return None

    # 4. Start Resource Monitoring
    monitor = ResourceMonitor(server_process.pid, sample_interval=0.02)
    monitor.start()

    # Create target payload content
    payload_content = "A" * payload_size_bytes

    # 5. Send messages
    test_start_time = time.perf_counter()
    
    for seq in range(1, num_messages + 1):
        send_time = time.perf_counter()
        with telemetry_lock:
            send_times[seq] = send_time
        
        # Send
        client.send(payload_content, seq=seq)
        
        # Interval delay
        if interval_ms > 0:
            # We compensate for the processing time of send
            elapsed = time.perf_counter() - send_time
            remaining_delay = (interval_ms / 1000.0) - elapsed
            if remaining_delay > 0:
                time.sleep(remaining_delay)

    # 6. Wait for all trailing messages to arrive (Timeout up to 2 seconds of inactivity)
    wait_start = time.perf_counter()
    last_count = 0
    while time.perf_counter() - wait_start < 2.0:
        with telemetry_lock:
            current_count = len(recv_times)
        if current_count == num_messages:
            break # All messages arrived!
        if current_count > last_count:
            # Progress made, reset wait window
            wait_start = time.perf_counter()
            last_count = current_count
        time.sleep(0.05)

    test_end_time = time.perf_counter()

    # 7. Terminate Resource Monitoring
    monitor.stop()
    monitor.join()
    resources = monitor.get_averages()

    # 8. Clean shut down of clients and servers
    if protocol == 'TCP':
        client.disconnect()
    else:
        client.stop()
        
    server_process.terminate()
    server_process.wait()

    # 9. Perform statistical analysis of the telemetry data
    rtts = []
    out_of_order_count = 0
    messages_lost = 0
    
    # Track highest sequence number seen so far to detect ordering inversion
    highest_seq_seen = 0
    
    with telemetry_lock:
        # Compute Latency/RTTs and Loss
        for seq in range(1, num_messages + 1):
            if seq in recv_times:
                rtt = (recv_times[seq] - send_times[seq]) * 1000.0 # Milliseconds
                rtts.append(rtt)
            else:
                messages_lost += 1

        # Check out-of-order counts using actual arrival order
        for seq in arrival_sequence:
            if seq >= highest_seq_seen:
                highest_seq_seen = seq
            else:
                out_of_order_count += 1

    # Computations
    total_received = len(rtts)
    loss_rate_percent = (messages_lost / num_messages) * 100.0 if num_messages > 0 else 0.0
    ordering_errors_percent = (out_of_order_count / total_received) * 100.0 if total_received > 0 else 0.0
    
    avg_rtt = sum(rtts) / total_received if total_received > 0 else 0.0
    min_rtt = min(rtts) if total_received > 0 else 0.0
    max_rtt = max(rtts) if total_received > 0 else 0.0
    
    # Standard deviation for jitter
    variance = sum((x - avg_rtt) ** 2 for x in rtts) / total_received if total_received > 0 else 0.0
    jitter = variance ** 0.5

    # Throughput (Received packets / Duration of active transmission)
    duration = test_end_time - test_start_time
    throughput_msgs_sec = total_received / duration if duration > 0 else 0.0
    # Bytes per second (assuming full payload size + metadata overhead roughly payload size)
    throughput_kb_sec = (total_received * payload_size_bytes) / 1024.0 / duration if duration > 0 else 0.0

    result = {
        "protocol": protocol,
        "config": {
            "num_messages": num_messages,
            "interval_ms": interval_ms,
            "payload_size_bytes": payload_size_bytes,
            "simulated_loss_percent": simulated_loss_percent if protocol == 'UDP' else 0
        },
        "metrics": {
            "sent": num_messages,
            "received": total_received,
            "lost": messages_lost,
            "loss_rate_percent": round(loss_rate_percent, 2),
            "out_of_order": out_of_order_count,
            "out_of_order_percent": round(ordering_errors_percent, 2),
            "duration_sec": round(duration, 3),
            "throughput_msgs_sec": round(throughput_msgs_sec, 2),
            "throughput_kb_sec": round(throughput_kb_sec, 2)
        },
        "latency_ms": {
            "min": round(min_rtt, 3),
            "max": round(max_rtt, 3),
            "avg": round(avg_rtt, 3),
            "jitter": round(jitter, 3)
        },
        "resources": resources
    }
    
    print(f"[BENCHMARK] Teste {protocol} finalizado!")
    print(f"            Perda: {result['metrics']['loss_rate_percent']}% | Latência Média: {result['latency_ms']['avg']}ms | Msgs/s: {result['metrics']['throughput_msgs_sec']}")
    return result

if __name__ == "__main__":
    # Can run standalone for debugging
    res_tcp = run_benchmark("TCP", num_messages=200, interval_ms=5, payload_size_bytes=256)
    res_udp = run_benchmark("UDP", num_messages=200, interval_ms=5, payload_size_bytes=256, simulated_loss_percent=10)
    print(json.dumps({"TCP": res_tcp, "UDP": res_udp}, indent=2))
