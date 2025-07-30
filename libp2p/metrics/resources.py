"""
Comprehensive resource tracking for libp2p.
"""
import gc
import os
import threading
import time
import tracemalloc
from typing import Dict, Optional, List, Tuple
import psutil

from libp2p.metrics.prometheus import default_registry

# Memory metrics
MEMORY_RSS_BYTES = default_registry.create_gauge(
    "libp2p_memory_rss_bytes",
    "Resident Set Size memory usage in bytes"
)

MEMORY_VMS_BYTES = default_registry.create_gauge(
    "libp2p_memory_vms_bytes", 
    "Virtual Memory Size in bytes"
)

MEMORY_PEAK_BYTES = default_registry.create_gauge(
    "libp2p_memory_peak_bytes",
    "Peak memory usage in bytes"
)

MEMORY_TRACEMALLOC_BYTES = default_registry.create_gauge(
    "libp2p_memory_tracemalloc_bytes",
    "Current memory usage tracked by tracemalloc"
)

MEMORY_TRACEMALLOC_PEAK_BYTES = default_registry.create_gauge(
    "libp2p_memory_tracemalloc_peak_bytes",
    "Peak memory usage tracked by tracemalloc"
)

# GC metrics
GC_COLLECTIONS_TOTAL = default_registry.create_counter(
    "libp2p_gc_collections_total",
    "Total number of garbage collections",
    {"generation"}
)

GC_OBJECTS_COLLECTED_TOTAL = default_registry.create_counter(
    "libp2p_gc_objects_collected_total",
    "Total number of objects collected by GC",
    {"generation"}
)

GC_UNCOLLECTABLE_OBJECTS = default_registry.create_gauge(
    "libp2p_gc_uncollectable_objects",
    "Number of uncollectable objects"
)

# CPU metrics  
CPU_USER_TIME_SECONDS = default_registry.create_gauge(
    "libp2p_cpu_user_time_seconds",
    "CPU time spent in user mode"
)

CPU_SYSTEM_TIME_SECONDS = default_registry.create_gauge(
    "libp2p_cpu_system_time_seconds", 
    "CPU time spent in system mode"
)

CPU_PERCENT_CURRENT = default_registry.create_gauge(
    "libp2p_cpu_percent_current",
    "Current CPU usage percentage"
)

# Thread metrics
THREAD_COUNT = default_registry.create_gauge(
    "libp2p_thread_count",
    "Number of threads"
)

# File descriptor metrics
FD_COUNT = default_registry.create_gauge(
    "libp2p_file_descriptors",
    "Number of open file descriptors"
)

FD_LIMIT = default_registry.create_gauge(
    "libp2p_file_descriptors_limit",
    "File descriptor limit"
)

# Network socket metrics
SOCKET_COUNT = default_registry.create_gauge(
    "libp2p_socket_count",
    "Number of open sockets",
    {"family", "type"}
)

# I/O metrics
IO_READ_BYTES_TOTAL = default_registry.create_counter(
    "libp2p_io_read_bytes_total",
    "Total bytes read from disk"
)

IO_WRITE_BYTES_TOTAL = default_registry.create_counter(
    "libp2p_io_write_bytes_total", 
    "Total bytes written to disk"
)

IO_READ_COUNT_TOTAL = default_registry.create_counter(
    "libp2p_io_read_count_total",
    "Total number of read operations"
)

IO_WRITE_COUNT_TOTAL = default_registry.create_counter(
    "libp2p_io_write_count_total",
    "Total number of write operations"
)

# Context switch metrics
CONTEXT_SWITCHES_VOLUNTARY_TOTAL = default_registry.create_counter(
    "libp2p_context_switches_voluntary_total",
    "Total voluntary context switches"
)

CONTEXT_SWITCHES_INVOLUNTARY_TOTAL = default_registry.create_counter(
    "libp2p_context_switches_involuntary_total", 
    "Total involuntary context switches"
)

# Resource allocation tracking
RESOURCE_ALLOCATIONS_TOTAL = default_registry.create_counter(
    "libp2p_resource_allocations_total",
    "Total resource allocations",
    {"resource_type"}
)

RESOURCE_DEALLOCATIONS_TOTAL = default_registry.create_counter(
    "libp2p_resource_deallocations_total",
    "Total resource deallocations", 
    {"resource_type"}
)

ACTIVE_RESOURCES = default_registry.create_gauge(
    "libp2p_active_resources",
    "Currently active resources",
    {"resource_type"}
)

# Multi-peer metrics
CONCURRENT_PEERS = default_registry.create_gauge(
    "libp2p_concurrent_peers",
    "Number of currently connected peers"
)

PEER_CONNECTION_DURATION = default_registry.create_histogram(
    "libp2p_peer_connection_duration_seconds",
    "Duration of peer connections",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, float('inf')]
)

MEMORY_PER_PEER = default_registry.create_gauge(
    "libp2p_memory_per_peer_bytes",
    "Average memory usage per connected peer"
)

CONNECTION_POOL_UTILIZATION = default_registry.create_gauge(
    "libp2p_connection_pool_utilization",
    "Percentage of connection pool being used"
)


class ResourceTracker:
    """Comprehensive resource tracking for libp2p."""
    
    def __init__(self, enable_tracemalloc: bool = True):
        """Initialize resource tracker with multi-peer support."""
        self.process = psutil.Process()
        self.start_time = time.time()
        self.last_cpu_times = self.process.cpu_times()
        self.last_io_counters = None
        self.last_ctx_switches = None
        self.enable_tracemalloc = enable_tracemalloc
        self.peak_memory = 0
        
        # Resource allocation tracking
        self.resource_counts: Dict[str, int] = {}
        self.resource_lock = threading.Lock()
        
        # Multi-peer tracking
        self.peer_connections: Dict[str, Dict] = {}
        self.max_concurrent_peers = 100
        self.connection_pool_size = 200
        
        # Initialize tracemalloc if enabled
        if self.enable_tracemalloc:
            try:
                tracemalloc.start()
            except RuntimeError:
                # Already started
                pass
        
        # Initialize baseline values
        try:
            self.last_io_counters = self.process.io_counters()
        except (psutil.AccessDenied, AttributeError):
            pass
            
        try:
            self.last_ctx_switches = self.process.num_ctx_switches()
        except (psutil.AccessDenied, AttributeError):
            pass
    
    def update_all_metrics(self) -> None:
        """Update all resource metrics."""
        self.update_memory_metrics()
        self.update_cpu_metrics()
        self.update_thread_metrics()
        self.update_fd_metrics()
        self.update_socket_metrics()
        self.update_io_metrics()
        self.update_context_switch_metrics()
        self.update_gc_metrics()
    
    def update_memory_metrics(self) -> None:
        """Update memory usage metrics."""
        try:
            memory_info = self.process.memory_info()
            
            # Basic memory metrics
            MEMORY_RSS_BYTES.set(memory_info.rss)
            MEMORY_VMS_BYTES.set(memory_info.vms)
            
            # Track peak memory
            if memory_info.rss > self.peak_memory:
                self.peak_memory = memory_info.rss
            MEMORY_PEAK_BYTES.set(self.peak_memory)
            
            # Tracemalloc metrics
            if self.enable_tracemalloc:
                try:
                    current, peak = tracemalloc.get_traced_memory()
                    MEMORY_TRACEMALLOC_BYTES.set(current)
                    MEMORY_TRACEMALLOC_PEAK_BYTES.set(peak)
                except Exception:
                    pass
                    
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    
    def update_cpu_metrics(self) -> None:
        """Update CPU metrics."""
        try:
            cpu_times = self.process.cpu_times()
            CPU_USER_TIME_SECONDS.set(cpu_times.user)
            CPU_SYSTEM_TIME_SECONDS.set(cpu_times.system)
            
            # CPU percentage (requires interval)
            cpu_percent = self.process.cpu_percent()
            CPU_PERCENT_CURRENT.set(cpu_percent)
            
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    
    def update_thread_metrics(self) -> None:
        """Update thread metrics."""
        try:
            thread_count = self.process.num_threads()
            THREAD_COUNT.set(thread_count)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    
    def update_fd_metrics(self) -> None:
        """Update file descriptor metrics."""
        try:
            # Number of open file descriptors
            if hasattr(self.process, 'num_fds'):
                fd_count = self.process.num_fds()
                FD_COUNT.set(fd_count)
            
            # File descriptor limit
            try:
                import resource
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                FD_LIMIT.set(soft_limit)
            except (ImportError, OSError):
                pass
                
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
            pass
    
    def update_socket_metrics(self) -> None:
        """Update socket metrics."""
        try:
            connections = self.process.connections()
            socket_counts: Dict[Tuple[str, str], int] = {}
            
            for conn in connections:
                family = conn.family.name if hasattr(conn.family, 'name') else str(conn.family)
                type_name = conn.type.name if hasattr(conn.type, 'name') else str(conn.type)
                key = (family, type_name)
                socket_counts[key] = socket_counts.get(key, 0) + 1
            
            # Reset all socket counts first
            for (family, type_name), count in socket_counts.items():
                SOCKET_COUNT.labels(family=family, type=type_name).set(count)
                
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    
    def update_io_metrics(self) -> None:
        """Update I/O metrics."""
        try:
            io_counters = self.process.io_counters()
            
            if self.last_io_counters:
                # Calculate deltas
                read_bytes_delta = io_counters.read_bytes - self.last_io_counters.read_bytes
                write_bytes_delta = io_counters.write_bytes - self.last_io_counters.write_bytes
                read_count_delta = io_counters.read_count - self.last_io_counters.read_count
                write_count_delta = io_counters.write_count - self.last_io_counters.write_count
                
                # Update counters
                if read_bytes_delta > 0:
                    IO_READ_BYTES_TOTAL.inc(read_bytes_delta)
                if write_bytes_delta > 0:
                    IO_WRITE_BYTES_TOTAL.inc(write_bytes_delta)
                if read_count_delta > 0:
                    IO_READ_COUNT_TOTAL.inc(read_count_delta)
                if write_count_delta > 0:
                    IO_WRITE_COUNT_TOTAL.inc(write_count_delta)
            
            self.last_io_counters = io_counters
            
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
            pass
    
    def update_context_switch_metrics(self) -> None:
        """Update context switch metrics."""
        try:
            ctx_switches = self.process.num_ctx_switches()
            
            if self.last_ctx_switches:
                vol_delta = ctx_switches.voluntary - self.last_ctx_switches.voluntary
                invol_delta = ctx_switches.involuntary - self.last_ctx_switches.involuntary
                
                if vol_delta > 0:
                    CONTEXT_SWITCHES_VOLUNTARY_TOTAL.inc(vol_delta)
                if invol_delta > 0:
                    CONTEXT_SWITCHES_INVOLUNTARY_TOTAL.inc(invol_delta)
            
            self.last_ctx_switches = ctx_switches
            
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
            pass
    
    def update_gc_metrics(self) -> None:
        """Update garbage collection metrics."""
        try:
            # Get GC stats
            for i, stats in enumerate(gc.get_stats()):
                gen = str(i)
                if 'collections' in stats:
                    # This will increment from baseline, so we track total
                    pass
                    
            # Get current GC counts
            gc_counts = gc.get_count()
            for i, count in enumerate(gc_counts):
                # Note: gc.get_count() returns current objects, not total collections
                pass
                
            # Count uncollectable objects
            uncollectable = len(gc.garbage)
            GC_UNCOLLECTABLE_OBJECTS.set(uncollectable)
            
        except Exception:
            pass
    
    def allocate_resource(self, resource_type: str) -> None:
        """Track resource allocation."""
        with self.resource_lock:
            self.resource_counts[resource_type] = self.resource_counts.get(resource_type, 0) + 1
            RESOURCE_ALLOCATIONS_TOTAL.labels(resource_type=resource_type).inc()
            ACTIVE_RESOURCES.labels(resource_type=resource_type).set(self.resource_counts[resource_type])
    
    def deallocate_resource(self, resource_type: str) -> None:
        """Track resource deallocation."""
        with self.resource_lock:
            if resource_type in self.resource_counts and self.resource_counts[resource_type] > 0:
                self.resource_counts[resource_type] -= 1
                RESOURCE_DEALLOCATIONS_TOTAL.labels(resource_type=resource_type).inc()
                ACTIVE_RESOURCES.labels(resource_type=resource_type).set(self.resource_counts[resource_type])
    
    def track_peer_connection(self, peer_id: str, connection_info: Dict = None) -> None:
        """Track a new peer connection for resource monitoring."""
        if connection_info is None:
            connection_info = {}
        
        with self.resource_lock:
            self.peer_connections[peer_id] = {
                'connected_at': time.time(),
                'memory_at_connect': self.process.memory_info().rss,
                'streams': 0,
                'bytes_sent': 0,
                'bytes_received': 0,
                **connection_info
            }
            self.allocate_resource("peer_connection")
            
            # Update multi-peer metrics
            CONCURRENT_PEERS.set(len(self.peer_connections))
            CONNECTION_POOL_UTILIZATION.set(len(self.peer_connections) / self.max_concurrent_peers)
            
            # Update memory per peer
            current_memory = self.process.memory_info().rss
            if len(self.peer_connections) > 0:
                MEMORY_PER_PEER.set(current_memory / len(self.peer_connections))
    
    def untrack_peer_connection(self, peer_id: str) -> Dict:
        """Stop tracking a peer connection and return stats."""
        with self.resource_lock:
            if peer_id in self.peer_connections:
                stats = self.peer_connections.pop(peer_id)
                stats['disconnected_at'] = time.time()
                stats['connection_duration'] = stats['disconnected_at'] - stats['connected_at']
                
                # Record connection duration histogram
                PEER_CONNECTION_DURATION.observe(stats['connection_duration'])
                
                self.deallocate_resource("peer_connection")
                
                # Update multi-peer metrics
                CONCURRENT_PEERS.set(len(self.peer_connections))
                CONNECTION_POOL_UTILIZATION.set(len(self.peer_connections) / self.max_concurrent_peers)
                
                # Update memory per peer
                current_memory = self.process.memory_info().rss
                if len(self.peer_connections) > 0:
                    MEMORY_PER_PEER.set(current_memory / len(self.peer_connections))
                else:
                    MEMORY_PER_PEER.set(0)
                
                return stats
            return {}
    
    def get_peer_stats(self) -> Dict:
        """Get statistics about connected peers."""
        with self.resource_lock:
            return {
                'total_peers': len(self.peer_connections),
                'max_peers': self.max_concurrent_peers,
                'connection_utilization': len(self.peer_connections) / self.max_concurrent_peers,
                'peer_ids': list(self.peer_connections.keys())[:10]  # Show first 10
            }
    
    def get_memory_top_allocations(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top memory allocations by tracemalloc."""
        if not self.enable_tracemalloc:
            return []
        
        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            result = []
            for stat in top_stats[:limit]:
                result.append((str(stat.traceback), stat.size))
            return result
        except Exception:
            return []
    
    def get_resource_summary(self) -> Dict[str, any]:
        """Get a summary of current resource usage."""
        try:
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()
            
            summary = {
                'memory_rss_mb': memory_info.rss / (1024 * 1024),
                'memory_vms_mb': memory_info.vms / (1024 * 1024),
                'cpu_percent': cpu_percent,
                'thread_count': self.process.num_threads(),
                'uptime_seconds': time.time() - self.start_time,
            }
            
            if hasattr(self.process, 'num_fds'):
                summary['file_descriptors'] = self.process.num_fds()
            
            if self.enable_tracemalloc:
                try:
                    current, peak = tracemalloc.get_traced_memory()
                    summary['tracemalloc_current_mb'] = current / (1024 * 1024)
                    summary['tracemalloc_peak_mb'] = peak / (1024 * 1024)
                except Exception:
                    pass
            
            return summary
        except Exception:
            return {}


# Global resource tracker instance
resource_tracker = ResourceTracker() 