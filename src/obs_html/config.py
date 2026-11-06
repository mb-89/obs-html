"""Artifact settings: the packaged cfg.json, optionally merged with one override file."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from obs_html.errors import InputError, schema_error


DEFAULT_CONFIG = Path(str(files("obs_html").joinpath("cfg.json")))
SCHEMA_PATH = Path(str(files("obs_html").joinpath("cfg.schema.json")))
RENAMED_KEYS = {"report": "artifact"}


@dataclass(frozen=True)
class Config:
    rendered_check_timeout_seconds: int
    timing_relative_threshold: float
    timing_absolute_threshold_seconds: float
    print_default: dict[str, str]
    paper_sizes: dict[str, dict[str, float]]
    artifact: dict[str, object]
    override_path: Path | None = None
    override: dict[str, object] | None = None

    def source(self, *path: str) -> Path:
        """The settings file a field comes from: the override file when it declares the field."""
        return self.override_path if _declares(self.override, list(path)) else DEFAULT_CONFIG


def load_config(override_path: Path | None = None) -> Config:
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    override: object = {}
    if override_path is not None:
        try:
            override = json.loads(override_path.read_text(encoding="utf-8"))
        except OSError as error:
            raise InputError(override_path, "", f"cannot be read ({error.strerror or error})",
                             "Give --config a readable JSON settings file") from error
        except json.JSONDecodeError as error:
            raise InputError(override_path, "", f"is not JSON ({error.msg} at line {error.lineno}, "
                             f"column {error.colno})", "Correct the JSON there") from error
        if not isinstance(override, dict):
            raise InputError(override_path, "", "must be a JSON object",
                             "Write the settings as one object, as cfg.schema.json describes")
        for old, new in RENAMED_KEYS.items():
            if old in override:
                raise InputError(override_path, old, f"was renamed to {new}", "Rename the key in that file")
        config = _merge(config, override)
    errors = list(_validator().iter_errors(config))
    if errors:  # The settings file names the failure when it declares the failing field.
        declared = _declares(override, list(best_match(errors).absolute_path))
        raise schema_error(errors, override_path if declared else DEFAULT_CONFIG, "cfg.schema.json")
    artifact = config["artifact"]
    return Config(
        rendered_check_timeout_seconds=config["execution"]["renderedCheckTimeoutSeconds"],
        timing_relative_threshold=config["timings"]["relativeThreshold"],
        timing_absolute_threshold_seconds=config["timings"]["absoluteThresholdSeconds"],
        print_default=artifact["print"]["default"],
        paper_sizes=artifact["print"]["paperSizes"],
        artifact={key: value for key, value in artifact.items() if key != "print"},
        override_path=override_path, override=override,
    )


def paper(choice: dict[str, str], config: Config, place: Callable[[str], tuple[object, str]]) -> dict[str, float]:
    """Resolve a paper and margin choice to physical paper geometry. ``place`` names where a
    choice key comes from: its source and field path."""
    if choice["paper"] not in config.paper_sizes:
        raise InputError(*place("paper"), f"is {choice['paper']!r}, not a paper of the print catalogue",
                         f"Choose one of {', '.join(config.paper_sizes)}")
    margin = float(choice["margin"].removesuffix("mm"))
    geometry = {**config.paper_sizes[choice["paper"]], "marginMillimeters": margin}
    limits = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$defs"]["paper"]["properties"]["marginMillimeters"]
    if not limits["minimum"] <= margin <= limits["maximum"]:
        raise InputError(*place("margin"), f"is {choice['margin']}, outside the print margins "
                         f"{limits['minimum']:g}mm to {limits['maximum']:g}mm",
                         "Choose a margin in that range; see cfg.schema.json")
    return geometry


def _declares(value: object, path: list[object]) -> bool:
    """Whether ``value`` holds the field at ``path``."""
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return True


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
