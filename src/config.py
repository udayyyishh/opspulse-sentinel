import os
import yaml
from pathlib import Path
from src.models import AppConfig, AppSettings, TargetConfig


def load_config(config_path: str = None) -> AppConfig:
    """Load monitoring configuration from YAML file or environment."""
    if not config_path:
        config_path = os.getenv("CONFIG_PATH", "config/targets.yaml")

    path = Path(config_path)
    if not path.exists():
        # Fallback to default in-memory config if file does not exist
        return AppConfig(
            settings=AppSettings(
                poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "15")),
                request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5.0")),
                alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", None),
                enable_console_alerts=os.getenv("ENABLE_CONSOLE_ALERTS", "true").lower() == "true",
            ),
            targets=[
                TargetConfig(
                    id="local-self-check",
                    name="Localhost Probe",
                    url="http://127.0.0.1:8000/healthz",
                    method="GET",
                    expected_status=200,
                    max_latency_ms=500.0,
                    critical=True,
                )
            ]
        )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    settings_data = data.get("settings", {})
    targets_data = data.get("targets", [])

    settings = AppSettings(**settings_data)
    targets = [TargetConfig(**t) for t in targets_data]

    return AppConfig(settings=settings, targets=targets)
