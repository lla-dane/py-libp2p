"""
Metrics for the ping protocol.
"""
import time
from typing import Optional

import trio

from libp2p.metrics.prometheus import default_registry
from libp2p.peer.id import ID as PeerID

# Ping metrics
PING_REQUEST_COUNT = default_registry.create_counter(
    "libp2p_ping_requests_total",
    "Total number of ping requests sent",
    {"peer_id"}
)

PING_RESPONSE_COUNT = default_registry.create_counter(
    "libp2p_ping_responses_total",
    "Total number of ping responses received",
    {"peer_id"}
)

PING_ERROR_COUNT = default_registry.create_counter(
    "libp2p_ping_errors_total",
    "Total number of ping errors",
    {"peer_id", "error_type"}
)

PING_TIMEOUT_COUNT = default_registry.create_counter(
    "libp2p_ping_timeouts_total",
    "Total number of ping timeouts",
    {"peer_id"}
)

# Latency metrics
PING_RTT_HISTOGRAM = default_registry.create_histogram(
    "libp2p_ping_rtt_microseconds",
    "Round-trip time for ping in microseconds",
    {"peer_id"},
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
)

PING_RTT_SUMMARY = default_registry.create_summary(
    "libp2p_ping_rtt_summary_microseconds",
    "Summary of round-trip time for ping in microseconds",
    {"peer_id"}
)

# Active pings
ACTIVE_PINGS = default_registry.create_gauge(
    "libp2p_active_pings",
    "Number of active ping operations",
    {"peer_id"}
)


class PingMetrics:
    """
    Helper class to track ping metrics.
    """
    
    @staticmethod
    def record_ping_request(peer_id: PeerID) -> None:
        """
        Record a ping request.
        
        Args:
            peer_id: The peer ID that was pinged
        """
        PING_REQUEST_COUNT.labels(peer_id=str(peer_id)).inc()
        ACTIVE_PINGS.labels(peer_id=str(peer_id)).inc()
    
    @staticmethod
    def record_ping_response(peer_id: PeerID, rtt_microseconds: int) -> None:
        """
        Record a successful ping response.
        
        Args:
            peer_id: The peer ID that responded
            rtt_microseconds: Round-trip time in microseconds
        """
        peer_id_str = str(peer_id)
        PING_RESPONSE_COUNT.labels(peer_id=peer_id_str).inc()
        PING_RTT_HISTOGRAM.labels(peer_id=peer_id_str).observe(rtt_microseconds)
        PING_RTT_SUMMARY.labels(peer_id=peer_id_str).observe(rtt_microseconds)
        ACTIVE_PINGS.labels(peer_id=peer_id_str).dec()
    
    @staticmethod
    def record_ping_error(peer_id: PeerID, error_type: str) -> None:
        """
        Record a ping error.
        
        Args:
            peer_id: The peer ID that was pinged
            error_type: Type of error
        """
        PING_ERROR_COUNT.labels(peer_id=str(peer_id), error_type=error_type).inc()
        ACTIVE_PINGS.labels(peer_id=str(peer_id)).dec()
    
    @staticmethod
    def record_ping_timeout(peer_id: PeerID) -> None:
        """
        Record a ping timeout.
        
        Args:
            peer_id: The peer ID that timed out
        """
        PING_TIMEOUT_COUNT.labels(peer_id=str(peer_id)).inc()
        ACTIVE_PINGS.labels(peer_id=str(peer_id)).dec()


class PingTimer:
    """
    Context manager to time ping operations and record metrics.
    """
    
    def __init__(self, peer_id: PeerID):
        """
        Initialize the ping timer.
        
        Args:
            peer_id: The peer ID being pinged
        """
        self.peer_id = peer_id
        self.start_time: Optional[float] = None
        self.rtt_microseconds: Optional[int] = None
    
    def __enter__(self):
        """Start timing the ping operation."""
        self.start_time = time.time()
        PingMetrics.record_ping_request(self.peer_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Stop timing the ping operation and record metrics.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if exc_type is None:
            # Successful ping
            assert self.start_time is not None
            self.rtt_microseconds = int((time.time() - self.start_time) * (10**6))
            PingMetrics.record_ping_response(self.peer_id, self.rtt_microseconds)
        elif exc_type is trio.TooSlowError:
            # Timeout
            PingMetrics.record_ping_timeout(self.peer_id)
        else:
            # Other error
            PingMetrics.record_ping_error(self.peer_id, exc_type.__name__) 