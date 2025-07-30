"""
Prometheus metrics for libp2p.
"""
import logging
from typing import Dict, Optional, Set, Union

try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary
    from prometheus_client.registry import CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Define dummy classes for type checking when prometheus_client is not available
    class DummyMetric:
        def __init__(self, *args, **kwargs):
            pass
        
        def inc(self, *args, **kwargs):
            pass
        
        def dec(self, *args, **kwargs):
            pass
        
        def observe(self, *args, **kwargs):
            pass
        
        def set(self, *args, **kwargs):
            pass
        
        def labels(self, *args, **kwargs):
            return self
    
    Counter = DummyMetric
    Gauge = DummyMetric
    Histogram = DummyMetric
    Summary = DummyMetric
    CollectorRegistry = object

logger = logging.getLogger("libp2p.metrics.prometheus")


class MetricsRegistry:
    """Registry for libp2p metrics."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize the metrics registry.
        
        Args:
            registry: Optional Prometheus registry to use. If not provided, the default registry is used.
        """
        self._registry = registry or prometheus_client.REGISTRY if PROMETHEUS_AVAILABLE else None
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self._enabled = PROMETHEUS_AVAILABLE
        
        if not self._enabled:
            logger.warning("Prometheus metrics are not available. Install prometheus_client package.")
    
    @property
    def enabled(self) -> bool:
        """Return whether metrics are enabled."""
        return self._enabled
    
    def create_counter(self, name: str, description: str, labels: Optional[Set[str]] = None) -> Counter:
        """
        Create a counter metric.
        
        Args:
            name: Name of the metric
            description: Description of the metric
            labels: Optional set of label names
            
        Returns:
            The created counter
        """
        if not self._enabled:
            return Counter()
        
        if name in self._metrics:
            return self._metrics[name]
        
        counter = Counter(
            name,
            description,
            labelnames=list(labels) if labels else [],
            registry=self._registry
        )
        self._metrics[name] = counter
        return counter
    
    def create_gauge(self, name: str, description: str, labels: Optional[Set[str]] = None) -> Gauge:
        """
        Create a gauge metric.
        
        Args:
            name: Name of the metric
            description: Description of the metric
            labels: Optional set of label names
            
        Returns:
            The created gauge
        """
        if not self._enabled:
            return Gauge()
        
        if name in self._metrics:
            return self._metrics[name]
        
        gauge = Gauge(
            name,
            description,
            labelnames=list(labels) if labels else [],
            registry=self._registry
        )
        self._metrics[name] = gauge
        return gauge
    
    def create_histogram(
        self, 
        name: str, 
        description: str, 
        labels: Optional[Set[str]] = None,
        buckets: Optional[list[float]] = None
    ) -> Histogram:
        """
        Create a histogram metric.
        
        Args:
            name: Name of the metric
            description: Description of the metric
            labels: Optional set of label names
            buckets: Optional list of buckets
            
        Returns:
            The created histogram
        """
        if not self._enabled:
            return Histogram()
        
        if name in self._metrics:
            return self._metrics[name]
        
        kwargs = {}
        if buckets is not None:
            kwargs["buckets"] = buckets
        
        histogram = Histogram(
            name,
            description,
            labelnames=list(labels) if labels else [],
            registry=self._registry,
            **kwargs
        )
        self._metrics[name] = histogram
        return histogram
    
    def create_summary(
        self, 
        name: str, 
        description: str, 
        labels: Optional[Set[str]] = None,
    ) -> Summary:
        """
        Create a summary metric.
        
        Args:
            name: Name of the metric
            description: Description of the metric
            labels: Optional set of label names
            
        Returns:
            The created summary
        """
        if not self._enabled:
            return Summary()
        
        if name in self._metrics:
            return self._metrics[name]
        
        summary = Summary(
            name,
            description,
            labelnames=list(labels) if labels else [],
            registry=self._registry,
        )
        self._metrics[name] = summary
        return summary
    
    def start_http_server(self, port: int = 8000, addr: str = "") -> None:
        """
        Start an HTTP server to expose metrics.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
        """
        if not self._enabled:
            logger.warning("Cannot start metrics HTTP server: prometheus_client not available")
            return
        
        try:
            prometheus_client.start_http_server(port, addr, self._registry)
            logger.info(f"Started metrics HTTP server on {addr}:{port}")
        except Exception as e:
            logger.error(f"Failed to start metrics HTTP server: {e}")


# Global metrics registry
default_registry = MetricsRegistry() 