from __future__ import annotations

import os

import pytest

from clinical_screening.providers import build_provider


@pytest.mark.live
def test_groq_configuration_live():
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY absente")
    assert build_provider("groq").status().configured is True
