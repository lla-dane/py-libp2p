#!/usr/bin/env python3
"""
libp2p ping demo with comprehensive resource monitoring.

This example tracks detailed resource usage including memory, CPU, I/O, and more.
"""
import argparse
import asyncio
import logging
import time
from typing import Dict, Any

import multiaddr
import trio

from libp2p import new_host
from libp2p.host.ping import ID as PING_PROTOCOL_ID, PingService, handle_ping
from libp2p.metrics.network import NetworkMetrics
from libp2p.metrics.ping import PingMetrics, PingTimer
from libp2p.metrics.prometheus import default_registry
from libp2p.metrics.resources import resource_tracker
from libp2p.peer.peerinfo import info_from_p2p_addr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resource-monitoring-demo")


async def resource_monitoring_task():
    """Background task to continuously monitor resources."""
    while True:
        try:
            # Update all resource metrics
            resource_tracker.update_all_metrics()
            
            # Log resource summary every 30 seconds
            if int(time.time()) % 30 == 0:
                summary = resource_tracker.get_resource_summary()
                logger.info("📊 Resource Summary:")
                logger.info(f"  💾 Memory RSS: {summary.get('memory_rss_mb', 0):.1f} MB")
                logger.info(f"  💾 Memory VMS: {summary.get('memory_vms_mb', 0):.1f} MB")
                logger.info(f"  🧠 CPU: {summary.get('cpu_percent', 0):.1f}%")
                logger.info(f"  🧵 Threads: {summary.get('thread_count', 0)}")
                logger.info(f"  📁 File Descriptors: {summary.get('file_descriptors', 0)}")
                logger.info(f"  ⏱️  Uptime: {summary.get('uptime_seconds', 0):.1f}s")
                
                if 'tracemalloc_current_mb' in summary:
                    logger.info(f"  🔍 Tracemalloc Current: {summary.get('tracemalloc_current_mb', 0):.1f} MB")
                    logger.info(f"  🔍 Tracemalloc Peak: {summary.get('tracemalloc_peak_mb', 0):.1f} MB")
                
                # Get top memory allocations
                top_allocations = resource_tracker.get_memory_top_allocations(3)
                if top_allocations:
                    logger.info("  🔝 Top Memory Allocations:")
                    for i, (traceback, size) in enumerate(top_allocations, 1):
                        size_mb = size / (1024 * 1024)
                        # Get just the filename and line number
                        location = traceback.split('\n')[0] if '\n' in traceback else traceback
                        logger.info(f"    {i}. {size_mb:.2f} MB - {location}")
        
        except Exception as e:
            logger.debug(f"Error in resource monitoring: {e}")
        
        await trio.sleep(2)  # Update every 2 seconds


async def resource_aware_ping_client(host, peer_info):
    """Ping client that tracks resource usage per operation."""
    ping_service = PingService(host)
    
    ping_count = 0
    
    while True:
        try:
            ping_count += 1
            
            # Track resource allocation for this ping session
            resource_tracker.allocate_resource("ping_session")
            
            logger.info(f"🏓 Starting ping session #{ping_count}")
            
            # Record stream and network metrics
            NetworkMetrics.record_stream_open(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "outbound"
            )
            
            start_time = time.time()
            memory_before = resource_tracker.get_resource_summary().get('memory_rss_mb', 0)
            
            # Perform pings with resource tracking
            with PingTimer(peer_info.peer_id):
                rtts = await ping_service.ping(peer_info.peer_id, ping_amt=5)
            
            end_time = time.time()
            memory_after = resource_tracker.get_resource_summary().get('memory_rss_mb', 0)
            
            # Log ping results with resource usage
            session_duration = end_time - start_time
            memory_delta = memory_after - memory_before
            
            logger.info(f"✅ Ping session #{ping_count} completed:")
            logger.info(f"  ⚡ RTTs: {[f'{rtt}μs' for rtt in rtts]}")
            logger.info(f"  ⏱️  Duration: {session_duration:.3f}s")
            logger.info(f"  💾 Memory delta: {memory_delta:+.2f} MB")
            
            # Record bandwidth (ping payload is 32 bytes each way)
            total_bytes = 32 * len(rtts) * 2  # bidirectional
            NetworkMetrics.record_bytes_transferred(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "sent", 
                32 * len(rtts)
            )
            NetworkMetrics.record_bytes_transferred(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "received", 
                32 * len(rtts)
            )
            
            # Record stream close
            NetworkMetrics.record_stream_close(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "normal"
            )
            
            # Deallocate resource
            resource_tracker.deallocate_resource("ping_session")
            
            # Show resource efficiency
            bytes_per_mb = total_bytes / max(abs(memory_delta), 0.001)
            logger.info(f"  📊 Efficiency: {bytes_per_mb:.0f} bytes/MB memory")
            
            await trio.sleep(10)  # Wait between ping sessions
            
        except Exception as e:
            logger.error(f"❌ Error in ping session #{ping_count}: {e}")
            resource_tracker.deallocate_resource("ping_session")
            NetworkMetrics.record_stream_close(
                peer_info.peer_id, 
                str(PING_PROTOCOL_ID), 
                "error"
            )
            await trio.sleep(5)


async def resource_tracking_ping_handler(stream):
    """Ping handler with resource tracking."""
    peer_id = stream.muxed_conn.peer_id
    
    # Track incoming connection resources
    resource_tracker.allocate_resource("ping_handler")
    
    NetworkMetrics.record_stream_open(
        peer_id, 
        str(PING_PROTOCOL_ID), 
        "inbound"
    )
    
    try:
        logger.info(f"📥 Handling ping from {peer_id}")
        await handle_ping(stream)
        NetworkMetrics.record_stream_close(peer_id, str(PING_PROTOCOL_ID), "normal")
        logger.info(f"✅ Ping handler completed for {peer_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in ping handler for {peer_id}: {e}")
        NetworkMetrics.record_stream_close(peer_id, str(PING_PROTOCOL_ID), "error")
    finally:
        resource_tracker.deallocate_resource("ping_handler")


async def run(port: int, metrics_port: int, destination: str = None) -> None:
    """Run the resource monitoring ping demo."""
    
    # Start metrics server
    default_registry.start_http_server(metrics_port)
    logger.info(f"🚀 Started comprehensive metrics server on port {metrics_port}")
    logger.info(f"📊 Metrics include: ping, network, system resources, memory tracking")
    
    # Set up libp2p host
    listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")
    host = new_host(listen_addrs=[listen_addr])
    
    # Track host creation
    resource_tracker.allocate_resource("libp2p_host")
    
    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        # Start background tasks
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)
        nursery.start_soon(resource_monitoring_task)
        
        # Record successful host startup
        NetworkMetrics.record_connection_attempt(host.get_id(), "tcp", True)
        
        if not destination:
            # Server mode
            host.set_stream_handler(PING_PROTOCOL_ID, resource_tracking_ping_handler)
            
            logger.info("🔧 Resource Monitoring Server Mode")
            logger.info(f"📡 Connect with: python ping_resource_monitoring.py -p <PORT> -m <METRICS_PORT> -d {host.get_addrs()[0]}")
            logger.info("📈 Tracking:")
            logger.info("  • Memory usage (RSS, VMS, peak, tracemalloc)")
            logger.info("  • CPU usage and context switches") 
            logger.info("  • File descriptors and sockets")
            logger.info("  • I/O operations and bandwidth")
            logger.info("  • Garbage collection metrics")
            logger.info("  • Resource allocation/deallocation")
            logger.info(f"📊 View metrics at: http://localhost:{metrics_port}")
            
            await trio.sleep_forever()
        else:
            # Client mode
            maddr = multiaddr.Multiaddr(destination)
            info = info_from_p2p_addr(maddr)
            
            logger.info(f"📡 Connecting to {info.peer_id} with resource monitoring...")
            
            start_time = time.time()
            await host.connect(info)
            connect_duration = time.time() - start_time
            
            # Record connection metrics
            NetworkMetrics.record_connection_attempt(info.peer_id, "tcp", True)
            
            logger.info(f"✅ Connected in {connect_duration:.3f}s")
            logger.info("🏓 Starting resource-monitored ping sessions...")
            
            # Track this peer connection
            resource_tracker.track_peer_connection(str(info.peer_id), {
                'transport': 'tcp',
                'connection_time': connect_duration
            })
            
            try:
                await resource_aware_ping_client(host, info)
            finally:
                # Untrack peer connection when done
                stats = resource_tracker.untrack_peer_connection(str(info.peer_id))
                if stats:
                    logger.info(f"📊 Peer connection stats: {stats}")


def main() -> None:
    """Main entry point."""
    description = """
    🔍 libp2p Resource Monitoring Demo
    
    Comprehensive resource tracking including:
    • Memory usage (RSS, VMS, peak tracking)
    • CPU usage and system time
    • File descriptors and socket counts  
    • I/O operations and bandwidth
    • Garbage collection metrics
    • Resource allocation tracking
    • Context switches and thread counts
    
    📊 Perfect for performance analysis and optimization!
    """
    
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-p", "--port", default=8000, type=int, help="libp2p port")
    parser.add_argument("-m", "--metrics-port", default=8080, type=int, help="metrics port")  
    parser.add_argument("-d", "--destination", type=str, help="destination multiaddr")
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting libp2p Resource Monitoring Demo")
    logger.info(f"📊 Metrics will be available at http://localhost:{args.metrics_port}")
    
    try:
        trio.run(run, args.port, args.metrics_port, args.destination)
    except KeyboardInterrupt:
        logger.info("👋 Shutting down resource monitoring...")
        
        # Final resource summary
        final_summary = resource_tracker.get_resource_summary()
        logger.info("📊 Final Resource Summary:")
        for key, value in final_summary.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.2f}")
            else:
                logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    main() 