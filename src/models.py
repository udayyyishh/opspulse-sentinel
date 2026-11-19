from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"  # Responding, but latency exceeded threshold or status unexpected
    DOWN = "DOWN"          # Connection refused, timeout, or consecutive failures
    UNKNOWN = "UNKNOWN"    # Not yet probed


class TargetConfig(BaseModel):
    id: str
    name: str
    url: str
    method: str = "GET"
    expected_status: int = 200
    max_latency_ms: float = 1000.0
    critical: bool = False


class AppSettings(BaseModel):
    poll_interval_seconds: int = 15
    request_timeout_seconds: float = 5.0
    alert_webhook_url: Optional[str] = None
    enable_console_alerts: bool = True


class AppConfig(BaseModel):
    settings: AppSettings = Field(default_factory=AppSettings)
    targets: List[TargetConfig] = Field(default_factory=list)


class ProbeResult(BaseModel):
    target_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    is_success: bool = False
    error_message: Optional[str] = None


class TargetStatus(BaseModel):
    target: TargetConfig
    current_state: HealthState = HealthState.UNKNOWN
    consecutive_failures: int = 0
    total_checks: int = 0
    total_successes: int = 0
    uptime_percentage: float = 100.0
    last_latency_ms: Optional[float] = None
    average_latency_ms: float = 0.0
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None


class SystemOverview(BaseModel):
    service: str = "OpsPulse Sentinel"
    version: str = "1.0.0"
    status: str = "healthy"
    monitored_targets_count: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    down_count: int = 0
    targets: List[TargetStatus] = Field(default_factory=list)
