#!/usr/bin/env python3
"""
Standalone libp2p resource monitoring demo.

This example shows resource usage without requiring peer connections.
Perfect for testing resource tracking in isolation.
"""
import argparse
import asyncio
import logging
import time
from typing import Dict, Any

import trio

from libp2p.metrics.prometheus import default_registry
from libp2p.metrics.resources import resource_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("standalone-resource-demo")


async def simulate_workload():
    """Simulate various workloads to show resource usage."""
    workload_count = 0
    
    while True:
        workload_count += 1
        
        logger.info(f"🔄 Starting workload simulation #{workload_count}")
        
        # Track resource allocation
        resource_tracker.allocate_resource("simulation_task")
        
        try:
            # Simulate some memory allocation
            data = []
            for i in range(1000):
                data.append(f"test_data_{i}" * 10)
            
            # Simulate some CPU work
            start_time = time.time()
            result = sum(range(10000))
            duration = time.time() - start_time
            
            # Log the work done
            logger.info(f"  ✅ Computed sum: {result} in {duration:.4f}s")
            logger.info(f"  💾 Allocated {len(data)} items")
            
            # Hold the data for a bit to show memory usage
            await trio.sleep(2)
            
            # Clear the data to show memory deallocation
            data.clear()
            
        finally:
            # Track resource deallocation
            resource_tracker.deallocate_resource("simulation_task")
        
        # Wait before next workload
        await trio.sleep(5)


async def resource_monitoring_task():
    """Background task to continuously monitor and log resources."""
    while True:
        try:
            # Update all resource metrics
            resource_tracker.update_all_metrics()
            
            # Log resource summary every 15 seconds
            if int(time.time()) % 15 == 0:
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
                
                logger.info("─" * 50)
        
        except Exception as e:
            logger.debug(f"Error in resource monitoring: {e}")
        
        await trio.sleep(1)  # Update every second


async def memory_stress_test():
    """Periodically run memory stress tests."""
    test_count = 0
    
    while True:
        await trio.sleep(30)  # Run every 30 seconds
        
        test_count += 1
        logger.info(f"🧪 Running memory stress test #{test_count}")
        
        resource_tracker.allocate_resource("stress_test")
        
        try:
            # Allocate a larger chunk of memory
            big_data = [f"stress_test_{i}" * 100 for i in range(5000)]
            
            # Show memory impact
            summary = resource_tracker.get_resource_summary()
            logger.info(f"  📈 Memory after allocation: {summary.get('memory_rss_mb', 0):.1f} MB")
            
            # Hold for a few seconds
            await trio.sleep(3)
            
            # Clear the memory
            big_data.clear()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            summary = resource_tracker.get_resource_summary()
            logger.info(f"  📉 Memory after cleanup: {summary.get('memory_rss_mb', 0):.1f} MB")
            
        finally:
            resource_tracker.deallocate_resource("stress_test")


async def run(metrics_port: int) -> None:
    """Run the standalone resource monitoring demo."""
    
    # Start metrics server
    default_registry.start_http_server(metrics_port)
    logger.info(f"🚀 Started resource monitoring server on port {metrics_port}")
    logger.info(f"📊 Comprehensive resource metrics available at http://localhost:{metrics_port}")
    
    logger.info("🔧 Standalone Resource Monitoring Mode")
    logger.info("📈 This demo will:")
    logger.info("  • Track memory usage (RSS, VMS, peak, tracemalloc)")
    logger.info("  • Monitor CPU usage and system time")
    logger.info("  • Count file descriptors and threads")
    logger.info("  • Track I/O operations")
    logger.info("  • Monitor garbage collection")
    logger.info("  • Show resource allocation patterns")
    logger.info("  • Run periodic memory stress tests")
    logger.info(f"📊 View dashboard at: http://localhost:3000/d/1a4791ec-50be-432c-aace-6dc17c72b98e")
    logger.info("─" * 60)
    
    # Track initial resources
    resource_tracker.allocate_resource("main_process")
    
    async with trio.open_nursery() as nursery:
        # Start background tasks
        nursery.start_soon(resource_monitoring_task)
        nursery.start_soon(simulate_workload)
        nursery.start_soon(memory_stress_test)
        
        # Keep running
        await trio.sleep_forever()


def main() -> None:
    """Main entry point."""
    description = """
    🔍 Standalone libp2p Resource Monitoring Demo
    
    This demo runs resource monitoring without requiring peer connections.
    Perfect for testing and understanding resource usage patterns.
    
    Features:
    • Real-time memory tracking (RSS, VMS, peak)
    • CPU usage monitoring
    • File descriptor and thread counting
    • Tracemalloc memory profiling
    • I/O operation tracking
    • Garbage collection metrics
    • Periodic stress testing
    • Resource allocation tracking
    
    📊 View metrics in Grafana at the resource monitoring dashboard!
    """
    
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-m", "--metrics-port", default=8080, type=int, help="metrics port")
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting Standalone Resource Monitoring Demo")
    logger.info(f"📊 Metrics will be available at http://localhost:{args.metrics_port}")
    logger.info("🎯 This will generate resource usage data for monitoring")
    
    try:
        trio.run(run, args.metrics_port)
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