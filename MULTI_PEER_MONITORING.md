# libp2p Multi-Peer Resource Monitoring

Complete guide for monitoring resource usage when connecting 50+ libp2p peers to a single server.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -e .
```

### 2. Start Monitoring Infrastructure
```bash
# Start Prometheus and Grafana
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Start libp2p Server
```bash
# Terminal 1: Start the resource monitoring server
ping-resource-demo -p 8001 -m 8081

# Note the multiaddr from the output, e.g.:
# /ip4/0.0.0.0/tcp/8001/p2p/QmSNCsT3oFhGDdCcXTdTcMboZExUxLsMWhjT5mKoFGNuMF
```

### 4. Connect Multiple Clients
```bash
# Terminal 2: First client
ping-resource-demo -p 8002 -m 8082 -d /ip4/0.0.0.0/tcp/8001/p2p/QmSNCsT3oFhGDdCcXTdTcMboZExUxLsMWhjT5mKoFGNuMF

# Terminal 3: Second client  
ping-resource-demo -p 8003 -m 8083 -d /ip4/0.0.0.0/tcp/8001/p2p/QmSNCsT3oFhGDdCcXTdTcMboZExUxLsMWhjT5mKoFGNuMF

# Continue for as many clients as needed...
```

### 5. View Dashboards
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Metrics Endpoints**: http://localhost:8081, http://localhost:8082, etc.

## 📊 Available Dashboards

### Multi-Peer Dashboard
**URL**: http://localhost:3000/d/multi-peer

**Key Panels**:
- **Concurrent Peer Connections** - Real-time peer count
- **Connection Pool Utilization** - Capacity usage (0-100%)
- **Memory per Peer** - Average memory usage per connected peer
- **Resource Efficiency** - CPU/Memory/FD usage per peer
- **Performance Under Load** - Ping RTT and error rates
- **Connection Duration Distribution** - 50th, 95th, 99th percentiles

## 🔧 Configuration

### Prometheus Configuration
File: `prometheus.yml`
- Scrapes metrics every 5 seconds
- Configured for `host.docker.internal` to access host metrics from Docker

### Grafana Provisioning
- **Data Source**: Automatically configured Prometheus
- **Dashboards**: Auto-imported from JSON files
- **Refresh Rate**: 5 seconds for real-time monitoring

## 📈 Key Metrics

### Multi-Peer Specific
- `libp2p_concurrent_peers` - Number of connected peers
- `libp2p_connection_pool_utilization` - Pool usage percentage (0-1)
- `libp2p_memory_per_peer_bytes` - Average memory per peer
- `libp2p_peer_connection_duration_seconds` - Connection duration histogram

### Resource Metrics
- `libp2p_memory_rss_bytes` - Resident memory usage
- `libp2p_cpu_usage_percent` - CPU usage percentage
- `libp2p_fd_count` - File descriptor count
- `libp2p_thread_count` - Thread count

### Network Metrics
- `libp2p_io_read_bytes_total` - Total bytes read
- `libp2p_io_write_bytes_total` - Total bytes written
- `libp2p_ping_rtt_seconds` - Ping round-trip time

## 🧪 Testing Scenarios

### Load Testing with 50 Peers

1. **Start Server**:
   ```bash
   ping-resource-demo -p 8001 -m 8081
   ```

2. **Launch Multiple Clients** (use different terminals or background processes):
   ```bash
   # Method 1: Manual terminals
   for i in {2..51}; do
     port=$((8000 + i))
     metrics_port=$((8080 + i))
     echo "Starting client on port $port with metrics on $metrics_port"
     ping-resource-demo -p $port -m $metrics_port -d /ip4/0.0.0.0/tcp/8001/p2p/YOUR_PEER_ID &
   done
   ```

3. **Monitor Resources**:
   - Watch the "Concurrent Peer Connections" panel
   - Observe "Memory per Peer" scaling
   - Check "Connection Pool Utilization"
   - Monitor "Performance Under Load"

### Expected Behavior
- **Memory Usage**: Should scale roughly linearly with peer count
- **CPU Usage**: May increase with ping frequency
- **Connection Pool**: Should show utilization percentage
- **RTT**: May increase slightly under load

## 🔍 Troubleshooting

### Common Issues

1. **"Connection Refused" in Prometheus**
   - Ensure metrics endpoints are accessible
   - Check `host.docker.internal` resolves correctly
   - Verify ports are not blocked by firewall

2. **Empty Grafana Dashboards**
   - Check Prometheus is scraping metrics: http://localhost:9090/targets
   - Verify metrics are being exposed: `curl http://localhost:8081`
   - Ensure data source is configured correctly

3. **High Memory Usage**
   - Monitor "Memory per Peer" - should be consistent
   - Check for memory leaks in "Memory Allocation Patterns"
   - Use tracemalloc data to identify allocation hotspots

4. **Connection Failures**
   - Verify server multiaddr is correct
   - Check network connectivity between peers
   - Ensure ports are available and not conflicting

### Debug Commands
```bash
# Check metrics are being exposed
curl -s http://localhost:8081 | grep libp2p

# Verify Prometheus targets
curl -s http://localhost:9090/api/v1/targets

# Check Docker services
docker-compose logs prometheus
docker-compose logs grafana
```

## 📋 Performance Expectations

### Resource Usage (Approximate)
- **Memory per Peer**: 1-5 MB baseline + protocol overhead
- **CPU per Peer**: <1% for ping operations
- **File Descriptors**: 1-2 per peer connection
- **Network**: ~64 bytes per ping (32 bytes each way)

### Scaling Limits
- **Max Concurrent Peers**: 100 (configurable in code)
- **Connection Pool**: 200 connections
- **Recommended Load**: Start with 10 peers, scale up gradually

## 🛠️ Advanced Configuration

### Adjusting Connection Limits
Edit `libp2p/metrics/resources.py`:
```python
self.max_concurrent_peers = 200  # Increase limit
self.connection_pool_size = 400  # Increase pool
```

### Custom Metrics Collection
Add new metrics in `libp2p/metrics/resources.py`:
```python
CUSTOM_METRIC = default_registry.create_gauge(
    "libp2p_custom_metric",
    "Description of custom metric"
)
```

### Prometheus Retention
Edit `docker-compose.yml` to add retention settings:
```yaml
command:
  - '--storage.tsdb.retention.time=7d'
  - '--storage.tsdb.retention.size=1GB'
```

## 🧹 Cleanup

To stop all services and clean up:
```bash
# Stop all background ping processes
pkill -f ping-resource-demo

# Stop Docker services
docker-compose down

# Clean up Docker volumes (optional)
docker-compose down -v
``` 