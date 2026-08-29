"""Дымовой тест: проверяем, что пакет вообще собирается и импортируется"""

import ai_blogger


def test_package_imports_and_reports_version() -> None:
    assert ai_blogger.__version__
