from __future__ import annotations

from dataclasses import dataclass, replace
from importlib import import_module
from importlib.resources import files
from pkgutil import iter_modules
from types import ModuleType
from typing import Callable

from obs_html.errors import InputError


@dataclass(frozen=True)
class BarDefinition:
    key: str
    label: str
    icon: str
    help: str
    order: int
    render: Callable[[], str]
    script: str = ""
    header_actions: str = ""


def discover_bars(package_name: str = __name__) -> tuple[BarDefinition, ...]:
    package = import_module(package_name)
    definitions = tuple(
        _load_definition(import_module(f"{package_name}.{module.name}"))
        for module in iter_modules(package.__path__)
        if not module.name.startswith("_")
    )
    ordered = tuple(sorted(definitions, key=lambda item: (item.order, item.key)))
    keys = [definition.key for definition in ordered]
    if len(keys) != len(set(keys)):
        raise InputError(package_name, "BAR.key", f"repeats a key among {keys}", "Give every dock bar its own key")
    return ordered


def _load_definition(module: ModuleType) -> BarDefinition:
    definition = getattr(module, "BAR", None)
    if not isinstance(definition, BarDefinition):
        raise InputError(module.__name__, "BAR", "is missing or no BarDefinition",
                         "Export one BarDefinition named BAR")
    missing = next((name for name in ("key", "label", "icon", "help") if not getattr(definition, name)), None)
    if missing is not None:
        raise InputError(module.__name__, f"BAR.{missing}", "is empty", "Give the dock bar a key, label, "
                         "icon and help")
    package, _, name = module.__name__.rpartition(".")
    runtime = files(package).joinpath(f"{name}.js")
    if definition.script:
        raise InputError(module.__name__, "BAR.script", "is set, but a dock bar's browser runtime is a file",
                         f"Move it into {name}.js beside the module")
    return replace(definition, script=runtime.read_text(encoding="utf-8")) if runtime.is_file() else definition
