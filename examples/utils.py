import random
import socket


def is_port_available(port: int) -> bool:
    """Check if a TCP port is available on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", port))
            return True
        except OSError:
            return False


def get_random_available_port(start: int = 10000, end: int = 20000) -> int:
    """Find a random available TCP port in the given range."""
    for _ in range(50):  # try up to 50 random ports
        port = random.randint(start, end)
        if is_port_available(port):
            return port
    raise RuntimeError("Could not find an available port in the given range.")
