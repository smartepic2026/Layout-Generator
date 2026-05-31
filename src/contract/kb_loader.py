"""Knowledge Base loader. Caches JSON files from src/rule_engine/kb/."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).parent / "kb"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((KB_DIR / name).read_text())


def rooms_kb(modality: str = "mAb") -> dict:
    """Room catalog for the given modality. Currently only mAb is shipped."""
    if modality != "mAb":
        raise NotImplementedError(f"Room KB for modality={modality} not yet provided")
    return _load("rooms_mab.json")


def equipment_kb() -> dict:
    return _load("equipment.json")


def grade_colors_kb() -> dict:
    return _load("grade_colors.json")


def acph_kb() -> dict:
    return _load("acph_table.json")


def gowning_kb() -> dict:
    return _load("gowning_table.json")


def flow_policy_kb(modality: str = "mAb") -> dict:
    data = _load("flow_policy_defaults.json")
    if modality not in data:
        raise NotImplementedError(f"Flow policy for modality={modality} not in KB")
    return data[modality]
