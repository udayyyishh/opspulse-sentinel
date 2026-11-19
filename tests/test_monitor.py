import pytest
import httpx
from unittest.mock import AsyncMock
from src.models import (
    AppConfig,
    AppSettings,
    TargetConfig,
    HealthState,
    ProbeResult,
)
from src.monitor import HealthMonitor


@pytest.fixture
def sample_config():
    return AppConfig(
        settings=AppSettings(
            poll_interval_seconds=5,
            request_timeout_seconds=2.0,
            enable_console_alerts=False,
        ),
        targets=[
            TargetConfig(
                id="test-service",
                name="Test Service",
                url="http://mock-service.local/health",
                expected_status=200,
                max_latency_ms=100.0,
                critical=True
            )
        ]
    )


@pytest.mark.asyncio
async def test_probe_single_success(sample_config):
    monitor = HealthMonitor(sample_config)
    target = sample_config.targets[0]

    mock_client = AsyncMock()
    mock_response = httpx.Response(status_code=200, request=httpx.Request("GET", target.url))
    mock_client.request.return_value = mock_response

    result = await monitor.probe_single(target, mock_client)
    assert result.is_success is True
    assert result.status_code == 200
    assert result.error_message is None


@pytest.mark.asyncio
async def test_probe_single_status_mismatch(sample_config):
    monitor = HealthMonitor(sample_config)
    target = sample_config.targets[0]

    mock_client = AsyncMock()
    mock_response = httpx.Response(status_code=500, request=httpx.Request("GET", target.url))
    mock_client.request.return_value = mock_response

    result = await monitor.probe_single(target, mock_client)
    assert result.is_success is False
    assert result.status_code == 500
    assert "Expected 200, got 500" in result.error_message


@pytest.mark.asyncio
async def test_evaluate_state_transitions(sample_config):
    monitor = HealthMonitor(sample_config)
    target = sample_config.targets[0]

    # 1. Successful check -> HEALTHY
    good_result = ProbeResult(
        target_id=target.id,
        status_code=200,
        latency_ms=50.0,
        is_success=True
    )
    await monitor.evaluate_probe_result(target, good_result)
    status = monitor.statuses[target.id]
    assert status.current_state == HealthState.HEALTHY
    assert status.consecutive_failures == 0
    assert status.uptime_percentage == 100.0

    # 2. Slow response -> DEGRADED
    slow_result = ProbeResult(
        target_id=target.id,
        status_code=200,
        latency_ms=250.0,  # exceeds max_latency_ms 100.0
        is_success=True
    )
    await monitor.evaluate_probe_result(target, slow_result)
    assert status.current_state == HealthState.DEGRADED

    # 3. First failure -> DEGRADED
    fail_result = ProbeResult(
        target_id=target.id,
        status_code=503,
        latency_ms=40.0,
        is_success=False,
        error_message="503 Service Unavailable"
    )
    await monitor.evaluate_probe_result(target, fail_result)
    assert status.consecutive_failures == 1
    assert status.current_state == HealthState.DEGRADED

    # 4. Second consecutive failure -> DOWN
    await monitor.evaluate_probe_result(target, fail_result)
    assert status.consecutive_failures == 2
    assert status.current_state == HealthState.DOWN

    # 5. Recovery -> HEALTHY
    await monitor.evaluate_probe_result(target, good_result)
    assert status.consecutive_failures == 0
    assert status.current_state == HealthState.HEALTHY
