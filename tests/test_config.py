from src.config import load_config
from src.models import AppConfig


def test_load_default_config_file():
    config = load_config("config/targets.yaml")
    assert isinstance(config, AppConfig)
    assert len(config.targets) >= 1
    assert config.settings.poll_interval_seconds > 0


def test_fallback_config_when_file_not_found(tmp_path):
    fake_path = tmp_path / "non_existent.yaml"
    config = load_config(str(fake_path))
    assert isinstance(config, AppConfig)
    assert len(config.targets) == 1
    assert config.targets[0].id == "local-self-check"
