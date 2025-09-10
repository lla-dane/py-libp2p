"""
Network metrics for libp2p connections and streams.
"""
from typing import Optional

from libp2p.metrics.prometheus import default_registry
from libp2p.peer.id import ID as PeerID

# Connection metrics
ACTIVE_CONNECTIONS = default_registry.create_gauge(
    "libp2p_connections_active",
    "Number of active connections",
    {"peer_id", "transport"}
)

CONNECTION_ATTEMPTS_TOTAL = default_registry.create_counter(
    "libp2p_connection_attempts_total",
    "Total number of connection attempts",
    {"peer_id", "transport", "result"}
)

CONNECTION_DURATION_SECONDS = default_registry.create_histogram(
    "libp2p_connection_duration_seconds",
    "Duration of connections in seconds",
    {"peer_id", "transport"},
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

# Stream metrics
ACTIVE_STREAMS = default_registry.create_gauge(
    "libp2p_streams_active",
    "Number of active streams",
    {"peer_id", "protocol"}
)

STREAM_OPENS_TOTAL = default_registry.create_counter(
    "libp2p_stream_opens_total",
    "Total number of streams opened",
    {"peer_id", "protocol", "direction"}
)

STREAM_CLOSES_TOTAL = default_registry.create_counter(
    "libp2p_stream_closes_total",
    "Total number of streams closed",
    {"peer_id", "protocol", "reason"}
)

# Bandwidth metrics
BYTES_SENT_TOTAL = default_registry.create_counter(
    "libp2p_bytes_sent_total",
    "Total bytes sent",
    {"peer_id", "protocol"}
)

BYTES_RECEIVED_TOTAL = default_registry.create_counter(
    "libp2p_bytes_received_total",
    "Total bytes received",
    {"peer_id", "protocol"}
)

# Protocol metrics
PROTOCOL_HANDLERS_ACTIVE = default_registry.create_gauge(
    "libp2p_protocol_handlers_active",
    "Number of active protocol handlers",
    {"protocol"}
)

MESSAGE_SIZE_BYTES = default_registry.create_histogram(
    "libp2p_message_size_bytes",
    "Size of messages in bytes",
    {"peer_id", "protocol", "direction"},
    buckets=[32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
)


class NetworkMetrics:
    """Helper class to track network metrics."""
    
    @staticmethod
    def record_connection_attempt(peer_id: PeerID, transport: str, success: bool) -> None:
        """Record a connection attempt."""
        result = "success" if success else "failure"
        CONNECTION_ATTEMPTS_TOTAL.labels(
            peer_id=str(peer_id), 
            transport=transport, 
            result=result
        ).inc()
        
        if success:
            ACTIVE_CONNECTIONS.labels(peer_id=str(peer_id), transport=transport).inc()
    
    @staticmethod
    def record_connection_close(peer_id: PeerID, transport: str, duration_seconds: float) -> None:
        """Record a connection closure."""
        ACTIVE_CONNECTIONS.labels(peer_id=str(peer_id), transport=transport).dec()
        CONNECTION_DURATION_SECONDS.labels(
            peer_id=str(peer_id), 
            transport=transport
        ).observe(duration_seconds)
    
    @staticmethod
    def record_stream_open(peer_id: PeerID, protocol: str, direction: str) -> None:
        """Record a stream opening."""
        STREAM_OPENS_TOTAL.labels(
            peer_id=str(peer_id), 
            protocol=protocol, 
            direction=direction
        ).inc()
        ACTIVE_STREAMS.labels(peer_id=str(peer_id), protocol=protocol).inc()
    
    @staticmethod
    def record_stream_close(peer_id: PeerID, protocol: str, reason: str) -> None:
        """Record a stream closure."""
        STREAM_CLOSES_TOTAL.labels(
            peer_id=str(peer_id), 
            protocol=protocol, 
            reason=reason
        ).inc()
        ACTIVE_STREAMS.labels(peer_id=str(peer_id), protocol=protocol).dec()
    
    @staticmethod
    def record_bytes_transferred(
        peer_id: PeerID, 
        protocol: str, 
        direction: str, 
        bytes_count: int
    ) -> None:
        """Record bytes sent or received."""
        if direction == "sent":
            BYTES_SENT_TOTAL.labels(peer_id=str(peer_id), protocol=protocol).inc(bytes_count)
        else:
            BYTES_RECEIVED_TOTAL.labels(peer_id=str(peer_id), protocol=protocol).inc(bytes_count)
        
        MESSAGE_SIZE_BYTES.labels(
            peer_id=str(peer_id), 
            protocol=protocol, 
            direction=direction
        ).observe(bytes_count)
    
    @staticmethod
    def set_protocol_handlers(protocol: str, count: int) -> None:
        """Set the number of active protocol handlers."""
        PROTOCOL_HANDLERS_ACTIVE.labels(protocol=protocol).set(count) 