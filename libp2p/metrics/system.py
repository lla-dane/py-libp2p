"""
System performance metrics for libp2p.
"""
import time
import psutil
from typing import Dict, Any

from libp2p.metrics.prometheus import default_registry

# System metrics
CPU_USAGE_PERCENT = default_registry.create_gauge(
    "libp2p_cpu_usage_percent",
    "CPU usage percentage of the libp2p process"
)

MEMORY_USAGE_BYTES = default_registry.create_gauge(
    "libp2p_memory_usage_bytes",
    "Memory usage in bytes of the libp2p process"
)

MEMORY_USAGE_PERCENT = default_registry.create_gauge(
    "libp2p_memory_usage_percent",
    "Memory usage percentage of the libp2p process"
)

OPEN_FILE_DESCRIPTORS = default_registry.create_gauge(
    "libp2p_open_file_descriptors",
    "Number of open file descriptors"
)

UPTIME_SECONDS = default_registry.create_gauge(
    "libp2p_uptime_seconds",
    "Uptime of the libp2p process in seconds"
)

# Event loop metrics
EVENT_LOOP_LATENCY_SECONDS = default_registry.create_histogram(
    "libp2p_event_loop_latency_seconds",
    "Event loop latency in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

TASK_COUNT = default_registry.create_gauge(
    "libp2p_active_tasks",
    "Number of active async tasks"
)

# Performance counters
OPERATION_DURATION_SECONDS = default_registry.create_histogram(
    "libp2p_operation_duration_seconds",
    "Duration of various libp2p operations",
    {"operation"},
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

OPERATIONS_TOTAL = default_registry.create_counter(
    "libp2p_operations_total",
    "Total number of operations performed",
    {"operation", "result"}
)


class SystemMetrics:
    """Helper class to track system metrics."""
    
    def __init__(self):
        self.start_time = time.time()
        self.process = psutil.Process()
    
    def update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = self.process.cpu_percent()
            CPU_USAGE_PERCENT.set(cpu_percent)
            
            # Memory usage
            memory_info = self.process.memory_info()
            MEMORY_USAGE_BYTES.set(memory_info.rss)
            
            memory_percent = self.process.memory_percent()
            MEMORY_USAGE_PERCENT.set(memory_percent)
            
            # File descriptors
            try:
                num_fds = self.process.num_fds() if hasattr(self.process, 'num_fds') else 0
                OPEN_FILE_DESCRIPTORS.set(num_fds)
            except (AttributeError, psutil.AccessDenied):
                pass
            
            # Uptime
            uptime = time.time() - self.start_time
            UPTIME_SECONDS.set(uptime)
            
        except Exception:
            # Ignore errors in metrics collection
            pass
    
    @staticmethod
    def record_operation(operation: str, duration: float, success: bool) -> None:
        """Record an operation with its duration and result."""
        OPERATION_DURATION_SECONDS.labels(operation=operation).observe(duration)
        result = "success" if success else "failure"
        OPERATIONS_TOTAL.labels(operation=operation, result=result).inc()
    
    @staticmethod
    def set_active_tasks(count: int) -> None:
        """Set the number of active async tasks."""
        TASK_COUNT.set(count)
    
    @staticmethod
    def record_event_loop_latency(latency: float) -> None:
        """Record event loop latency."""
        EVENT_LOOP_LATENCY_SECONDS.observe(latency)


# Global system metrics instance
system_metrics = SystemMetrics() 