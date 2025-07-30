#!/usr/bin/env python3
"""
Enhanced ping example with comprehensive libp2p metrics.

This example demonstrates system performance, network, and ping metrics.
"""
import argparse
import asyncio
import logging
import time

import multiaddr
import trio

from libp2p import new_host
from libp2p.host.ping import ID as PING_PROTOCOL_ID, PingService, handle_ping
from libp2p.metrics.network import NetworkMetrics
from libp2p.metrics.ping import PingMetrics, PingTimer
from libp2p.metrics.prometheus import default_registry
from libp2p.metrics.system import system_metrics
from libp2p.peer.peerinfo import info_from_p2p_addr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced-ping-metrics")


async def system_metrics_updater():
    """Background task to update system metrics."""
    while True:
        system_metrics.update_system_metrics()
        await trio.sleep(5)  # Update every 5 seconds


async def enhanced_ping_client(host, peer_info):
    """Enhanced ping client with comprehensive metrics."""
    ping_service = PingService(host)
    
    while True:
        try:
            # Record stream open
            NetworkMetrics.record_stream_open(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "outbound"
            )
            
            start_time = time.time()
            
            # Perform ping
            with PingTimer(peer_info.peer_id):
                rtts = await ping_service.ping(peer_info.peer_id, ping_amt=3)
            
            # Record operation success
            duration = time.time() - start_time
            system_metrics.record_operation("ping_session", duration, True)
            
            # Record bytes transferred (ping is 32 bytes each way)
            NetworkMetrics.record_bytes_transferred(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "sent", 
                32 * 3
            )
            NetworkMetrics.record_bytes_transferred(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "received", 
                32 * 3
            )
            
            for i, rtt in enumerate(rtts):
                logger.info(f"Ping {i+1} RTT: {rtt} microseconds")
            
            logger.info("📊 Metrics available at http://localhost:8081")
            
            # Record stream close
            NetworkMetrics.record_stream_close(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "normal"
            )
            
            await trio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error during ping: {e}")
            duration = time.time() - start_time
            system_metrics.record_operation("ping_session", duration, False)
            NetworkMetrics.record_stream_close(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "error"
            )
            await trio.sleep(5)


async def enhanced_ping_handler(stream):
    """Enhanced ping handler with metrics."""
    peer_id = stream.muxed_conn.peer_id
    
    # Record stream open
    NetworkMetrics.record_stream_open(
        peer_id, 
        str(PING_PROTOCOL_ID), 
        "inbound"
    )
    
    try:
        await handle_ping(stream)
        NetworkMetrics.record_stream_close(peer_id, str(PING_PROTOCOL_ID), "normal")
    except Exception as e:
        logger.error(f"Error in ping handler: {e}")
        NetworkMetrics.record_stream_close(peer_id, str(PING_PROTOCOL_ID), "error")


async def run(port: int, metrics_port: int, destination: str = None) -> None:
    """Run the enhanced ping example with comprehensive metrics."""
    # Start metrics server
    default_registry.start_http_server(metrics_port)
    logger.info(f"🚀 Started Prometheus metrics server on port {metrics_port}")
    logger.info(f"📊 Comprehensive metrics available at http://localhost:{metrics_port}")
    
    # Set up libp2p host
    listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")
    host = new_host(listen_addrs=[listen_addr])
    
    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        # Start background tasks
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)
        nursery.start_soon(system_metrics_updater)
        
        # Record connection attempt
        NetworkMetrics.record_connection_attempt(
            host.get_id(), 
            "tcp", 
            True
        )
        
        if not destination:
            # Server mode
            host.set_stream_handler(PING_PROTOCOL_ID, enhanced_ping_handler)
            
            logger.info("🔧 Server mode - waiting for connections")
            logger.info(f"📡 Run client with: python ping_enhanced_metrics.py -p <PORT> -m <METRICS_PORT> -d {host.get_addrs()[0]}")
            logger.info("📈 Available metrics:")
            logger.info("  • Ping latency and success rates")
            logger.info("  • Network connections and streams")
            logger.info("  • System CPU, memory, and performance")
            logger.info("  • Bandwidth and message sizes")
            
            await trio.sleep_forever()
        else:
            # Client mode
            maddr = multiaddr.Multiaddr(destination)
            info = info_from_p2p_addr(maddr)
            
            logger.info(f"📡 Connecting to peer {info.peer_id}")
            
            start_time = time.time()
            await host.connect(info)
            connect_duration = time.time() - start_time
            
            # Record successful connection
            NetworkMetrics.record_connection_attempt(info.peer_id, "tcp", True)
            system_metrics.record_operation("connect", connect_duration, True)
            
            logger.info("✅ Connected! Starting enhanced ping with metrics...")
            
            await enhanced_ping_client(host, info)


def main() -> None:
    """Main entry point."""
    description = """
    Enhanced libp2p ping demo with comprehensive Prometheus metrics.
    
    🚀 Features:
    • Ping latency and success rate tracking
    • Network connection and stream metrics  
    • System performance monitoring (CPU, memory)
    • Bandwidth and message size analysis
    • Real-time Prometheus metrics export
    
    📊 Use with Grafana for professional monitoring dashboards!
    """
    
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-p", "--port", default=8000, type=int, help="libp2p port")
    parser.add_argument("-m", "--metrics-port", default=8080, type=int, help="metrics port")
    parser.add_argument("-d", "--destination", type=str, help="destination multiaddr")
    
    args = parser.parse_args()
    
    try:
        trio.run(run, args.port, args.metrics_port, args.destination)
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")


if __name__ == "__main__":
    main() 