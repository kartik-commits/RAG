# VectorCache 3.0 — Technical Reference Manual

## 1. Overview

VectorCache is a distributed, in-memory caching system designed for high-throughput machine learning inference pipelines. It supports sub-millisecond key-value lookups, automatic cache invalidation based on embedding drift, and native integration with vector databases like ChromaDB and Milvus.

VectorCache was built to solve a specific problem: ML inference pipelines that repeatedly compute embeddings for the same input data waste GPU cycles. By caching embedding vectors alongside their source text, VectorCache reduces redundant computation by up to 94% in production workloads.

## 2. Architecture

### 2.1 Core Components

The system consists of three primary layers:

1. **Ingestion Layer**: Accepts raw text or pre-computed embeddings via gRPC or REST API. Supports batch ingestion of up to 10,000 entries per request.
2. **Storage Layer**: Uses a combination of in-memory hash maps for hot data and memory-mapped files for warm data. Cold data is evicted to disk using LRU policy.
3. **Query Layer**: Handles similarity search requests. Supports exact match (hash lookup), approximate nearest neighbor (HNSW index), and hybrid queries combining both.

### 2.2 Data Flow

When a client sends a query:
1. The query text is hashed using MurmurHash3 to check for exact cache hits.
2. If no exact match, the query is embedded using the configured model.
3. The embedding is searched against the HNSW index for approximate matches.
4. Results above the similarity threshold (default: 0.85) are returned.
5. The query and its embedding are added to the cache for future lookups.

### 2.3 Cluster Topology

VectorCache runs in a leader-follower topology. The leader node handles all write operations and replicates changes to followers asynchronously. Read requests are load-balanced across all nodes.

Minimum cluster size: 3 nodes (1 leader + 2 followers).
Recommended production cluster: 5 nodes with cross-zone deployment.

## 3. Installation

### 3.1 System Requirements

- Python 3.10 or higher
- 16 GB RAM minimum (32 GB recommended for production)
- 4 CPU cores minimum
- Linux (Ubuntu 22.04+ or RHEL 9+) — macOS supported for development only
- CUDA 12.0+ for GPU-accelerated embedding (optional)

### 3.2 Quick Start

```bash
pip install vectorcache[all]
vectorcache init --config ./config.yaml
vectorcache start --mode standalone
```

For cluster mode:

```bash
vectorcache start --mode cluster --role leader --bind 0.0.0.0:7400
vectorcache start --mode cluster --role follower --leader-addr 10.0.1.1:7400
```

### 3.3 Docker Deployment

```yaml
# docker-compose.yml
version: "3.8"
services:
  vectorcache-leader:
    image: vectorcache/server:3.0
    ports:
      - "7400:7400"
      - "7401:7401"
    environment:
      - VC_MODE=cluster
      - VC_ROLE=leader
      - VC_MAX_MEMORY=8g
    volumes:
      - vc-data:/var/lib/vectorcache

  vectorcache-follower:
    image: vectorcache/server:3.0
    environment:
      - VC_MODE=cluster
      - VC_ROLE=follower
      - VC_LEADER_ADDR=vectorcache-leader:7400
    deploy:
      replicas: 2
```

## 4. Configuration Reference

### 4.1 Core Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_memory` | string | `"4g"` | Maximum memory allocation for cache storage |
| `eviction_policy` | string | `"lru"` | Eviction strategy: `lru`, `lfu`, or `ttl` |
| `ttl_seconds` | int | `3600` | Default TTL for cached entries |
| `similarity_threshold` | float | `0.85` | Minimum cosine similarity for cache hits |
| `embedding_model` | string | `"all-MiniLM-L6-v2"` | Sentence-transformer model for auto-embedding |
| `embedding_dim` | int | `384` | Dimension of embedding vectors |
| `hnsw_ef_construction` | int | `200` | HNSW index build-time parameter |
| `hnsw_m` | int | `16` | HNSW max connections per node |
| `batch_size` | int | `512` | Default batch size for bulk operations |

### 4.2 Example Configuration

```yaml
# config.yaml
server:
  host: 0.0.0.0
  port: 7400
  grpc_port: 7401
  workers: 4

cache:
  max_memory: "8g"
  eviction_policy: lru
  ttl_seconds: 7200
  similarity_threshold: 0.82

embedding:
  model: "all-MiniLM-L6-v2"
  device: "cuda"
  batch_size: 256

index:
  type: hnsw
  ef_construction: 200
  m: 16
  ef_search: 100

logging:
  level: INFO
  format: json
  output: /var/log/vectorcache/server.log
```

## 5. API Reference

### 5.1 REST API

#### PUT /cache/entry

Store a single entry in the cache.

```json
{
  "key": "doc_12345",
  "text": "The transformer architecture uses self-attention mechanisms...",
  "metadata": {
    "source": "arxiv",
    "doc_id": "1706.03762",
    "chunk_index": 42
  },
  "embedding": [0.023, -0.119, 0.445, ...]
}
```

If `embedding` is omitted, VectorCache will compute it automatically using the configured model.

**Response** (201 Created):
```json
{
  "key": "doc_12345",
  "status": "stored",
  "embedding_computed": true,
  "ttl_remaining": 7200
}
```

#### POST /cache/search

Search for similar entries.

```json
{
  "query": "How does self-attention work?",
  "top_k": 5,
  "threshold": 0.80,
  "filter": {
    "source": "arxiv"
  }
}
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "key": "doc_12345",
      "text": "The transformer architecture uses self-attention mechanisms...",
      "score": 0.92,
      "metadata": {"source": "arxiv", "doc_id": "1706.03762"}
    }
  ],
  "query_time_ms": 2.3,
  "total_searched": 150000
}
```

### 5.2 Python SDK

```python
from vectorcache import CacheClient

client = CacheClient("localhost:7400")

# Store entries
client.put("doc_001", text="Neural networks learn hierarchical representations...")
client.put_batch([
    {"key": "doc_002", "text": "Gradient descent optimizes..."},
    {"key": "doc_003", "text": "Backpropagation computes gradients..."}
])

# Search
results = client.search("How do neural networks learn?", top_k=3)
for r in results:
    print(f"[{r.score:.3f}] {r.key}: {r.text[:100]}")

# Delete
client.delete("doc_001")
client.flush()  # Clear entire cache
```

## 6. Monitoring & Observability

### 6.1 Metrics Endpoint

VectorCache exposes Prometheus-compatible metrics at `/metrics`:

- `vc_cache_hits_total` — Total number of cache hits
- `vc_cache_misses_total` — Total number of cache misses
- `vc_cache_size_bytes` — Current cache memory usage
- `vc_query_duration_seconds` — Histogram of query latencies
- `vc_embedding_compute_seconds` — Time spent computing embeddings
- `vc_evictions_total` — Total number of evicted entries

### 6.2 Health Check

```bash
curl http://localhost:7400/health
```

Response:
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "cache_entries": 1523042,
  "memory_used": "6.2g",
  "memory_limit": "8g",
  "leader": true,
  "followers_connected": 2
}
```

## 7. Troubleshooting

### 7.1 High Latency on Queries

**Symptom**: Query latency exceeds 50ms.

**Possible causes**:
1. HNSW `ef_search` is set too high. Reduce from 100 to 50 for faster (but less accurate) results.
2. Cache memory is near capacity, causing frequent evictions and re-computations.
3. Embedding model is running on CPU. Switch to GPU with `device: cuda` in config.

**Fix**:
```yaml
index:
  ef_search: 50
embedding:
  device: cuda
```

### 7.2 Follower Nodes Out of Sync

**Symptom**: Followers return stale results compared to leader.

**Cause**: Network partition or replication lag exceeding `max_replication_lag` (default: 5 seconds).

**Fix**: Check network connectivity between nodes. If lag persists, trigger a full sync:

```bash
vectorcache admin sync --target follower-2 --full
```

### 7.3 Out of Memory Errors

**Symptom**: Server crashes with `MemoryError` or OOM killer terminates process.

**Cause**: `max_memory` is set too close to system RAM, leaving no room for OS and embedding model.

**Rule of thumb**: Set `max_memory` to at most 60% of total system RAM. Reserve at least 4 GB for the embedding model if running locally.

### 7.4 Embedding Dimension Mismatch

**Symptom**: Error `DimensionMismatchError: expected 384, got 768`.

**Cause**: Entries were indexed with one embedding model (e.g., `all-MiniLM-L6-v2`, dim=384) but queries are using a different model (e.g., `all-mpnet-base-v2`, dim=768).

**Fix**: All entries in a cache namespace must use the same embedding model. To switch models, create a new namespace and re-index:

```python
client.create_namespace("v2", embedding_dim=768)
client.reindex(source="default", target="v2", model="all-mpnet-base-v2")
```

## 8. Performance Tuning

### 8.1 Batch Ingestion

For bulk loading, use the batch API with optimal batch sizes:

- **CPU-only**: batch_size=128 gives best throughput
- **Single GPU**: batch_size=512 saturates most cards
- **Multi-GPU**: batch_size=1024 with `device: cuda:all`

### 8.2 Index Tuning

The HNSW index has two critical parameters:

- **`m`** (max connections): Higher values improve recall but increase memory. Default 16 is good for most cases. Use 32 for datasets >10M entries.
- **`ef_construction`**: Higher values build a better index but take longer. Use 200 for production, 64 for development.
- **`ef_search`**: Controls query-time accuracy vs. speed tradeoff. Start at 100, reduce if latency matters more than recall.

### 8.3 Memory Optimization

Enable compression to reduce memory footprint by ~40%:

```yaml
cache:
  compression: zstd
  compression_level: 3
```

Trade-off: adds ~2ms per query for decompression.
