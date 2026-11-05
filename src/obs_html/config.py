"""Artifact settings: the packaged cfg.json, optionally merged with one override file."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator


DEFAULT_CONFIG = Path(str(files("obs_html").joinpath("cfg.json")))
SCHEMA_PATH = Path(str(files("obs_html").joinpath("cfg.schema.json")))
RENAMED_KEYS = {"report": "artifact"}


class ConfigError(ValueError):
    """Raised when artifact settings are invalid."""


@dataclass(frozen=True)
class Config:
    rendered_check_timeout_seconds: int
    print_default: dict[str, str]
    paper_sizes: dict[str, dict[str, float]]
    artifact: dict[str, object]


def load_config(override_path: Path | None = None) -> Config:
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    if override_path is not None:
        try:
            override = json.loads(override_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigError(f"Cannot read settings {override_path}: {error}") from error
        if not isinstance(override, dict):
            raise ConfigError(f"Settings {override_path} must be a JSON object.")
        for old, new in RENAMED_KEYS.items():
            if old in override:
                raise ConfigError(f"{override_path}: settings key '{old}' was renamed to '{new}'; "
                                  "rename the key in that file.")
        config = _merge(config, override)
    error = next(_validator().iter_errors(config), None)
    if error is not None:
        location = ".".join(str(part) for part in error.absolute_path) or "settings"
        raise ConfigError(f"Invalid {location}: {error.message}")
    artifact = config["artifact"]
    return Config(
        rendered_check_timeout_seconds=config["execution"]["renderedCheckTimeoutSeconds"],
        print_default=artifact["print"]["default"],
        paper_sizes=artifact["print"]["paperSizes"],
        artifact={key: value for key, value in artifact.items() if key != "print"},
    )


def paper(choice: dict[str, str], config: Config) -> dict[str, float]:
    """Resolve a paper and margin choice to physical paper geometry."""
    if choice["paper"] not in config.paper_sizes:
        raise ConfigError(
            f"Print paper must be one of {', '.join(config.paper_sizes)}; got {choice['paper']!r}."
        )
    margin = float(choice["margin"].removesuffix("mm"))
    geometry = {**config.paper_sizes[choice["paper"]], "marginMillimeters": margin}
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    error = next(Draft202012Validator(schema["$defs"]["paper"]).iter_errors(geometry), None)
    if error is not None:
        raise ConfigError(f"Print margin {choice['margin']} is out of range: {error.message}.")
    return geometry


def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def _merge(defaults: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(defaults)
    for key, value in overrides.items():
        default = merged.get(key)
        if isinstance(default, dict) and isinstance(value, dict):
            merged[key] = _merge(default, value)
        else:
            merged[key] = value
    return merged
