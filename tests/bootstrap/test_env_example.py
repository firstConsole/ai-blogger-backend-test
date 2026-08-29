from __future__ import annotations

from pathlib import Path

from ai_blogger.bootstrap.config import Section, Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def _keys_from_example() -> set[str]:
    keys: set[str] = set()
    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip().upper())
    return keys


def _keys_from_settings() -> tuple[set[str], set[str]]:
    allowed: set[str] = set()
    required: set[str] = set()

    for name, field in Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, Section):
            for sub_name, sub_field in annotation.model_fields.items():
                key = f"{name}__{sub_name}".upper()
                allowed.add(key)
                if sub_field.is_required():
                    required.add(key)
        else:
            allowed.add(name.upper())

    return allowed, required


def test_example_contains_no_unknown_variables() -> None:
    allowed, _ = _keys_from_settings()
    unknown = _keys_from_example() - allowed

    assert not unknown, f"в .env.example есть лишние переменные: {sorted(unknown)}"


def test_example_lists_every_required_variable() -> None:
    _, required = _keys_from_settings()
    missing = required - _keys_from_example()

    assert not missing, f"в .env.example не хватает обязательных переменных: {sorted(missing)}"


def test_example_keeps_all_values_empty_or_safe() -> None:
    filled_secrets: list[str] = []

    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        looks_secret = any(word in key.upper() for word in ("TOKEN", "KEY", "PASSWORD", "SECRET"))
        if looks_secret and value:
            filled_secrets.append(key)

    assert not filled_secrets, f"в .env.example заполнены секреты: {sorted(filled_secrets)}"
