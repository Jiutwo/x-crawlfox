import json
import pytest
from pathlib import Path
from unittest.mock import patch


def make_config_manager(cwd, home):
    """Instantiate ConfigManager with patched Path.cwd() and Path.home()."""
    with patch("x_crawlfox.cli.config.Path") as mock_path_cls:
        # We need Path to behave normally except for .cwd() and .home()
        # Instead, directly patch the attributes on a real instance
        pass

    # Simpler approach: patch at instance level by importing after monkeypatching
    from x_crawlfox.cli.config import ConfigManager

    cm = ConfigManager.__new__(ConfigManager)
    cm.local_dir = cwd / ".x-crawlfox"
    cm.global_dir = home / ".x-crawlfox"
    cm.config_dir = cm.get_config_dir()
    cm.auth_path = cm.config_dir / "x_cookies.json"
    return cm


def test_get_default_config_nested_format():
    """get_default_config() must return nested {global, x} structure."""
    from x_crawlfox.cli.config import ConfigManager

    cfg = ConfigManager.__new__(ConfigManager)
    result = cfg.get_default_config()

    assert "global" in result, "Missing 'global' key"
    assert "x" in result, "Missing 'x' key"
    assert "output_dir" in result["global"]
    assert "headless" in result["global"]
    assert "timeline" in result["x"]
    assert "news" in result["x"]


def test_get_default_config_no_flat_keys():
    """Flat top-level keys (timeline, news) must not exist at root level."""
    from x_crawlfox.cli.config import ConfigManager

    cfg = ConfigManager.__new__(ConfigManager)
    result = cfg.get_default_config()

    assert "timeline" not in result, "timeline should be nested under 'x', not at root"
    assert "news" not in result, "news should be nested under 'x', not at root"


def test_init_config_writes_nested_format(tmp_path):
    """init_config() must write nested {global, x} JSON to disk."""
    from x_crawlfox.cli.config import ConfigManager

    with patch("x_crawlfox.cli.config.Path.cwd", return_value=tmp_path):
        ConfigManager.init_config(global_mode=False)

    config_file = tmp_path / ".x-crawlfox" / "crawl_config.json"
    assert config_file.exists(), "crawl_config.json was not created"

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "global" in data
    assert "x" in data
    assert "timeline" in data["x"]
    assert "news" in data["x"]
    assert "timeline" not in data  # not at root


def test_init_config_global_mode(tmp_path):
    """init_config(global_mode=True) writes to home directory."""
    from x_crawlfox.cli.config import ConfigManager

    with patch("x_crawlfox.cli.config.Path.home", return_value=tmp_path):
        ConfigManager.init_config(global_mode=True)

    config_file = tmp_path / ".x-crawlfox" / "crawl_config.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "global" in data
    assert "x" in data


def test_get_config_dir_prefers_local(tmp_path):
    """get_config_dir() returns local .x-crawlfox when it exists."""
    from x_crawlfox.cli.config import ConfigManager

    local_dir = tmp_path / "project" / ".x-crawlfox"
    local_dir.mkdir(parents=True)
    global_dir = tmp_path / "home" / ".x-crawlfox"

    cm = ConfigManager.__new__(ConfigManager)
    cm.local_dir = local_dir
    cm.global_dir = global_dir

    assert cm.get_config_dir() == local_dir


def test_get_config_dir_falls_back_to_global(tmp_path):
    """get_config_dir() falls back to global dir when local does not exist."""
    from x_crawlfox.cli.config import ConfigManager

    local_dir = tmp_path / "project" / ".x-crawlfox"   # intentionally not created
    global_dir = tmp_path / "home" / ".x-crawlfox"

    cm = ConfigManager.__new__(ConfigManager)
    cm.local_dir = local_dir
    cm.global_dir = global_dir

    assert cm.get_config_dir() == global_dir


def test_get_crawl_config_path(tmp_path):
    """get_crawl_config_path() returns <config_dir>/crawl_config.json."""
    from x_crawlfox.cli.config import ConfigManager

    local_dir = tmp_path / ".x-crawlfox"
    local_dir.mkdir()

    cm = ConfigManager.__new__(ConfigManager)
    cm.local_dir = local_dir
    cm.global_dir = tmp_path / "home" / ".x-crawlfox"
    cm.config_dir = cm.get_config_dir()
    cm.auth_path = cm.config_dir / "x_cookies.json"

    expected = local_dir / "crawl_config.json"
    assert cm.get_crawl_config_path() == expected
