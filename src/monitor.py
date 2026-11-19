import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from prometheus_client import Gauge, Counter

from src.models import (
    AppConfig,
    HealthState,
    ProbeResult,
    TargetConfig,
    TargetStatus,
    SystemOverview,
)
from src.alert import AlertDispatcher

logger = logging.getLogger("OpsPulse.Monitor")

# Prometheus Metrics
TARGET_UP_GAUGE = Gauge(
    "opspulse_target_up",
    "Health status of target (1=Healthy, 0.5=Degraded, 0=Down)",
    ["target_id", "target_name"]
)
TARGET_LATENCY_GAUGE = Gauge(
    "opspulse_target_latency_ms",
    "Last recorded probe latency in milliseconds",
    ["target_id", "target_name"]
)
TARGET_CHECKS_COUNTER = Counter(
    "opspulse_target_checks_total",
    "Total number of health probe checks conducted",
    ["target_id", "outcome"]
)


class HealthMonitor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.alerter = AlertDispatcher(
            webhook_url=config.settings.alert_webhook_url,
            console_alerts=config.settings.enable_console_alerts
        )
        self.statuses: Dict[str, TargetStatus] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Initialize statuses for all configured targets
        for target in config.targets:
            self.statuses[target.id] = TargetStatus(target=target)

    async def probe_single(self, target: TargetConfig, client: httpx.AsyncClient) -> ProbeResult:
        """Probe an individual target and record performance metrics."""
        start_time = time.perf_counter()
        timeout = self.config.settings.request_timeout_seconds

        try:
            response = await client.request(
                method=target.method,
                url=target.url,
                timeout=timeout,
                follow_redirects=True
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            is_success = (response.status_code == target.expected_status)

            return ProbeResult(
                target_id=target.id,
                timestamp=datetime.now(timezone.utc),
                status_code=response.status_code,
                latency_ms=round(elapsed_ms, 2),
                is_success=is_success,
                error_message=None if is_success else f"Expected {target.expected_status}, got {response.status_code}"
            )
        except httpx.TimeoutException:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProbeResult(
                target_id=target.id,
                timestamp=datetime.now(timezone.utc),
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                is_success=False,
                error_message=f"Request timed out after {timeout}s"
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProbeResult(
                target_id=target.id,
                timestamp=datetime.now(timezone.utc),
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                is_success=False,
                error_message=f"Connection error: {str(exc)}"
            )

    async def evaluate_probe_result(self, target: TargetConfig, result: ProbeResult):
        """Update state machine, Prometheus metrics, and trigger alerts if status changes."""
        status = self.statuses[target.id]
        old_state = status.current_state

        status.total_checks += 1
        status.last_checked_at = result.timestamp
        status.last_latency_ms = result.latency_ms

        # Rolling average latency calculation
        if status.total_checks == 1:
            status.average_latency_ms = result.latency_ms
        else:
            status.average_latency_ms = round(
                (status.average_latency_ms * (status.total_checks - 1) + result.latency_ms) / status.total_checks, 2
            )

        new_state = HealthState.HEALTHY
        reason = "Target responded successfully within latency threshold"

        if result.is_success:
            status.total_successes += 1
            status.consecutive_failures = 0
            status.last_error = None

            if result.latency_ms > target.max_latency_ms:
                new_state = HealthState.DEGRADED
                reason = f"Latency {result.latency_ms:.1f}ms exceeds threshold of {target.max_latency_ms:.1f}ms"
            else:
                new_state = HealthState.HEALTHY
            TARGET_CHECKS_COUNTER.labels(target_id=target.id, outcome="success").inc()
        else:
            status.consecutive_failures += 1
            status.last_error = result.error_message
            TARGET_CHECKS_COUNTER.labels(target_id=target.id, outcome="failure").inc()

            if status.consecutive_failures >= 2 or result.status_code is None:
                new_state = HealthState.DOWN
                reason = f"Failure: {result.error_message} (consecutive failures: {status.consecutive_failures})"
            else:
                new_state = HealthState.DEGRADED
                reason = f"Initial failure: {result.error_message}"

        status.uptime_percentage = round((status.total_successes / status.total_checks) * 100.0, 2)
        status.current_state = new_state

        # Update Prometheus metrics
        metric_value = 1.0 if new_state == HealthState.HEALTHY else (0.5 if new_state == HealthState.DEGRADED else 0.0)
        TARGET_UP_GAUGE.labels(target_id=target.id, target_name=target.name).set(metric_value)
        TARGET_LATENCY_GAUGE.labels(target_id=target.id, target_name=target.name).set(result.latency_ms)

        # State transition alert trigger
        if old_state != HealthState.UNKNOWN and old_state != new_state:
            await self.alerter.send_state_change_alert(
                target=target,
                old_state=old_state,
                new_state=new_state,
                reason=reason,
                latency_ms=result.latency_ms
            )

    async def run_probe_cycle(self) -> List[ProbeResult]:
        """Perform a concurrent probe cycle across all configured targets."""
        async with httpx.AsyncClient() as client:
            tasks = [self.probe_single(target, client) for target in self.config.targets]
            results: List[ProbeResult] = await asyncio.gather(*tasks)

        for result in results:
            target = next(t for t in self.config.targets if t.id == result.target_id)
            await self.evaluate_probe_result(target, result)

        return results

    async def _loop(self):
        """Daemon polling loop."""
        while self._running:
            try:
                await self.run_probe_cycle()
            except Exception as e:
                logger.error("Error during probe cycle: %s", e)
            await asyncio.sleep(self.config.settings.poll_interval_seconds)

    def start(self):
        """Start background daemon monitor."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("OpsPulse background monitor started.")

    def stop(self):
        """Stop background monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("OpsPulse background monitor stopped.")

    def get_overview(self) -> SystemOverview:
        """Produce aggregated cluster health overview."""
        statuses_list = list(self.statuses.values())
        healthy = sum(1 for s in statuses_list if s.current_state == HealthState.HEALTHY)
        degraded = sum(1 for s in statuses_list if s.current_state == HealthState.DEGRADED)
        down = sum(1 for s in statuses_list if s.current_state == HealthState.DOWN)

        overall_status = "healthy"
        if down > 0:
            overall_status = "critical"
        elif degraded > 0:
            overall_status = "degraded"

        return SystemOverview(
            status=overall_status,
            monitored_targets_count=len(statuses_list),
            healthy_count=healthy,
            degraded_count=degraded,
            down_count=down,
            targets=statuses_list
        )
