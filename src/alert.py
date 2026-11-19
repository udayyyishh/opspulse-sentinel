import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from src.models import HealthState, TargetConfig

logger = logging.getLogger("OpsPulse.Alert")


class AlertDispatcher:
    def __init__(self, webhook_url: Optional[str] = None, console_alerts: bool = True):
        self.webhook_url = webhook_url
        self.console_alerts = console_alerts

    async def send_state_change_alert(
        self,
        target: TargetConfig,
        old_state: HealthState,
        new_state: HealthState,
        reason: str,
        latency_ms: Optional[float] = None
    ) -> bool:
        """Trigger alerts on health transitions (e.g. HEALTHY -> DOWN or DOWN -> HEALTHY)."""
        timestamp = datetime.now(timezone.utc).isoformat()
        is_recovery = (new_state == HealthState.HEALTHY)
        severity = "INFO" if is_recovery else ("CRITICAL" if target.critical else "WARNING")

        alert_msg = (
            f"[{severity}] Target '{target.name}' ({target.id}) transitioned: "
            f"{old_state.value} -> {new_state.value}. Reason: {reason}"
        )
        if latency_ms is not None:
            alert_msg += f" (Latency: {latency_ms:.1f}ms)"

        if self.console_alerts:
            if is_recovery:
                logger.info("RECOVERY ALERT: %s", alert_msg)
            else:
                logger.warning("INCIDENT ALERT: %s", alert_msg)

        if not self.webhook_url:
            return True

        # Send HTTP Webhook (compatible with Slack, Discord, or Incident Management APIs)
        payload = {
            "timestamp": timestamp,
            "severity": severity,
            "target_id": target.id,
            "target_name": target.name,
            "target_url": target.url,
            "previous_state": old_state.value,
            "current_state": new_state.value,
            "reason": reason,
            "latency_ms": latency_ms,
            "text": alert_msg,
        }

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                return res.status_code < 300
        except Exception as e:
            logger.error("Failed to deliver webhook alert for %s: %s", target.id, e)
            return False
