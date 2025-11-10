"""Real-time performance monitoring and bottleneck detection"""

import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from statistics import mean, median, stdev
from asyncio import Lock

from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


@dataclass
class QueryProfile:
    """Profile data for a single query"""
    query_type: str
    duration_ms: float
    timestamp: datetime
    params: Dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class PerformanceMonitor:
    """
    Tracks query performance and identifies bottlenecks.
    Maintains rolling window of recent queries for analysis.
    """
    
    def __init__(self, window_hours: int = 24, max_queries: int = 10000):
        """
        Initialize performance monitor.
        
        Args:
            window_hours: Rolling window size in hours
            max_queries: Maximum queries to store
        """
        self.window_hours = window_hours
        self.max_queries = max_queries
        self.queries: List[QueryProfile] = []
        self.lock = Lock()
    
    async def record_query(
        self,
        query_type: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        **params
    ):
        """
        Record a query execution.
        
        Args:
            query_type: Type of query (e.g., 'historical_data_fetch')
            duration_ms: Duration in milliseconds
            success: Whether query succeeded
            error: Error message if failed
            **params: Query parameters for filtering
        """
        profile = QueryProfile(
            query_type=query_type,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow(),
            params=params,
            success=success,
            error=error
        )
        
        async with self.lock:
            self.queries.append(profile)
            
            # Evict old entries beyond window
            cutoff = datetime.utcnow() - timedelta(hours=self.window_hours)
            self.queries = [q for q in self.queries if q.timestamp > cutoff]
            
            # Evict oldest if at max size
            if len(self.queries) > self.max_queries:
                self.queries = self.queries[-self.max_queries:]
    
    async def get_stats(self, query_type: Optional[str] = None) -> Dict:
        """
        Get performance statistics.
        
        Args:
            query_type: Filter to specific query type (None = all)
        
        Returns:
            Statistics dictionary
        """
        async with self.lock:
            if query_type:
                queries = [q for q in self.queries if q.query_type == query_type]
            else:
                queries = self.queries
            
            if not queries:
                return {
                    "query_type": query_type,
                    "total": 0,
                    "error_count": 0,
                    "error_rate_pct": 0,
                }
            
            durations = [q.duration_ms for q in queries if q.success]
            successful = len(durations)
            failed = sum(1 for q in queries if not q.success)
            
            if durations:
                return {
                    "query_type": query_type or "all",
                    "total": len(queries),
                    "successful": successful,
                    "failed": failed,
                    "error_rate_pct": round((failed / len(queries)) * 100, 2),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "mean_ms": round(mean(durations), 2),
                    "median_ms": round(median(durations), 2),
                    "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2) if len(durations) > 1 else durations[0],
                    "p99_ms": round(sorted(durations)[int(len(durations) * 0.99)], 2) if len(durations) > 1 else durations[0],
                    "stdev_ms": round(stdev(durations), 2) if len(durations) > 1 else 0,
                }
            else:
                return {
                    "query_type": query_type or "all",
                    "total": len(queries),
                    "successful": 0,
                    "failed": len(queries),
                    "error_rate_pct": 100,
                }
    
    async def get_bottlenecks(self, threshold_ms: Optional[float] = None) -> List[Dict]:
        """
        Identify queries slower than threshold.
        
        Args:
            threshold_ms: Duration threshold in milliseconds
                         If None, uses 95th percentile
        
        Returns:
            List of slow queries with stats
        """
        async with self.lock:
            if not self.queries:
                return []
            
            if threshold_ms is None:
                all_durations = [q.duration_ms for q in self.queries if q.success]
                if all_durations:
                    threshold_ms = sorted(all_durations)[int(len(all_durations) * 0.95)]
                else:
                    return []
            
            # Group by query type and find bottlenecks
            by_type = {}
            for q in self.queries:
                if q.duration_ms >= threshold_ms:
                    if q.query_type not in by_type:
                        by_type[q.query_type] = []
                    by_type[q.query_type].append(q.duration_ms)
            
            results = []
            for query_type, durations in by_type.items():
                results.append({
                    "query_type": query_type,
                    "slow_count": len(durations),
                    "threshold_ms": round(threshold_ms, 2),
                    "avg_slow_ms": round(mean(durations), 2),
                    "max_slow_ms": round(max(durations), 2),
                    "pct_of_total": round(
                        (len(durations) / len(self.queries)) * 100, 2
                    )
                })
            
            return sorted(results, key=lambda x: x["slow_count"], reverse=True)
    
    async def get_query_types(self) -> Dict[str, int]:
        """Get count of queries by type"""
        async with self.lock:
            counts = {}
            for q in self.queries:
                counts[q.query_type] = counts.get(q.query_type, 0) + 1
            return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
    
    async def get_summary(self) -> Dict:
        """Get overall performance summary"""
        async with self.lock:
            if not self.queries:
                return {"total_queries": 0}
            
            successful = [q for q in self.queries if q.success]
            failed = [q for q in self.queries if not q.success]
            
            durations = [q.duration_ms for q in successful]
            
            return {
                "total_queries": len(self.queries),
                "successful": len(successful),
                "failed": len(failed),
                "error_rate_pct": round((len(failed) / len(self.queries)) * 100, 2),
                "avg_duration_ms": round(mean(durations), 2) if durations else 0,
                "median_duration_ms": round(median(durations), 2) if durations else 0,
                "p95_duration_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2) if len(durations) > 1 else (durations[0] if durations else 0),
                "p99_duration_ms": round(sorted(durations)[int(len(durations) * 0.99)], 2) if len(durations) > 1 else (durations[0] if durations else 0),
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "window_hours": self.window_hours,
            }


# Global instance
_monitor_instance: Optional[PerformanceMonitor] = None


def init_performance_monitor(window_hours: int = 24) -> PerformanceMonitor:
    """Initialize global performance monitor"""
    global _monitor_instance
    _monitor_instance = PerformanceMonitor(window_hours=window_hours)
    logger.info("Performance monitor initialized", extra={"window_hours": window_hours})
    return _monitor_instance


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PerformanceMonitor()
    return _monitor_instance
