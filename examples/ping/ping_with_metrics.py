#!/usr/bin/env python3
"""
Ping example with Prometheus metrics.

This example demonstrates how to use the ping protocol with Prometheus metrics.
It starts a Prometheus HTTP server that exposes metrics about ping operations.
"""
import argparse
import logging

import multiaddr
import trio

from libp2p import (
    new_host,
)
from libp2p.host.ping_metrics import (
    ID as PING_PROTOCOL_ID,
    PingServiceWithMetrics,
    handle_ping,
)
from libp2p.metrics.prometheus import default_registry
from libp2p.peer.peerinfo import (
    info_from_p2p_addr,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ping-metrics-demo")


async def run(port: int, metrics_port: int, destination: str = None) -> None:
    """
    Run the ping example with metrics.
    
    Args:
        port: The port to listen on
        metrics_port: The port to expose metrics on
        destination: Optional destination multiaddr to ping
    """
    # Start the metrics server
    default_registry.start_http_server(metrics_port)
    logger.info(f"Started Prometheus metrics server on port {metrics_port}")
    
    # Set up the libp2p host
    listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")
    host = new_host(listen_addrs=[listen_addr])
    
    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        # Start the peer-store cleanup task
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)
        
        if not destination:
            # Server mode: handle incoming ping requests
            host.set_stream_handler(PING_PROTOCOL_ID, handle_ping)
            
            logger.info(
                "Run this from the same folder in another console:\n\n"
                f"python ping_with_metrics.py "
                f"-p <PORT> -m <METRICS_PORT> "
                f"-d {host.get_addrs()[0]}\n"
            )
            logger.info("Waiting for incoming connection...")
            logger.info(f"Prometheus metrics available at http://localhost:{metrics_port}")
            
            await trio.sleep_forever()
        else:
            # Client mode: send pings to the destination
            maddr = multiaddr.Multiaddr(destination)
            info = info_from_p2p_addr(maddr)
            
            logger.info(f"Connecting to peer {info.peer_id} at {destination}")
            await host.connect(info)
            
            # Create the ping service with metrics
            ping_service = PingServiceWithMetrics(host)
            
            # Send pings every 5 seconds
            while True:
                try:
                    logger.info(f"Pinging {info.peer_id}...")
                    rtts = await ping_service.ping(info.peer_id, ping_amt=3)
                    
                    for i, rtt in enumerate(rtts):
                        logger.info(f"Ping {i+1} RTT: {rtt} microseconds")
                    
                    logger.info(f"Prometheus metrics available at http://localhost:{metrics_port}")
                    
                    # Wait before sending the next ping
                    await trio.sleep(5)
                except Exception as e:
                    logger.error(f"Error during ping: {e}")
                    await trio.sleep(5)


def main() -> None:
    """Main entry point for the ping metrics example."""
    description = """
    This program demonstrates a p2p ping application with Prometheus metrics using libp2p.
    
    To use it:
    1. First run 'python ping_with_metrics.py -p <PORT> -m <METRICS_PORT>', where:
       - <PORT> is the port number for libp2p
       - <METRICS_PORT> is the port number for Prometheus metrics
       
    2. Then, run another instance with:
       'python ping_with_metrics.py -p <ANOTHER_PORT> -m <ANOTHER_METRICS_PORT> -d <DESTINATION>',
       where <DESTINATION> is the multiaddress of the previous listener host.
       
    3. Access the metrics at http://localhost:<METRICS_PORT> in your browser.
    """
    
    example_maddr = (
        "/ip4/127.0.0.1/tcp/8000/p2p/QmQn4SwGkDZKkUEpBRBvTmheQycxAHJUNmVEnjA2v1qe8Q"
    )
    
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-p", "--port", default=8000, type=int, help="source port number")
    parser.add_argument("-m", "--metrics-port", default=8080, type=int, help="metrics port number")
    parser.add_argument(
        "-d",
        "--destination",
        type=str,
        help=f"destination multiaddr string, e.g. {example_maddr}",
    )
    args = parser.parse_args()
    
    try:
        trio.run(run, *(args.port, args.metrics_port, args.destination))
    except KeyboardInterrupt:
        logger.info("Exiting...")


if __name__ == "__main__":
    main() 