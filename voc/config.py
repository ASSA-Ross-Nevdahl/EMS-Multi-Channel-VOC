"""Load YAML configuration (sources and taxonomy)."""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_sources(config_dir: Path | None = None) -> dict:
    path = (config_dir or DEFAULT_CONFIG_DIR) / "sources.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("rss", [])
    data.setdefault("reddit", [])
    data.setdefault("web", [])
    return data


def load_taxonomy(config_dir: Path | None = None) -> dict:
    path = (config_dir or DEFAULT_CONFIG_DIR) / "taxonomy.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("categories", {})
    data.setdefault("brands", {})
    data.setdefault("themes", {})
    return data
