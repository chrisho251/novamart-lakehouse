"""Smoke tests for the multipage Streamlit dashboard using AppTest (no browser).

Generates a tiny sample, points the data layer at it, then renders every page
and asserts no exception was raised. Skips cleanly if the app extras
(streamlit/plotly/faker) are not installed.
"""

from __future__ import annotations

import os
import random

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["overview", "sales", "customers", "operations", "payments", "pipeline"]

_VIEW_SCRIPT = """
import streamlit as st
from lib import data, theme

theme.install_template()
st.session_state["filters"] = {{}}
from views import {mod}

{mod}.render()
"""


@pytest.fixture()
def sample_dir(tmp_path, monkeypatch):
    faker = pytest.importorskip("faker")
    from novamart_gen.generate import CsvSink, generate_all
    from novamart_gen.schema import ScaleConfig

    fk = faker.Faker("en_US")
    faker.Faker.seed(0)
    sink = CsvSink(str(tmp_path))
    generate_all(ScaleConfig(scale=0.0), sink, random.Random(0), fk, progress=False)
    sink.close()

    monkeypatch.setenv("SAMPLE_DIR", str(tmp_path))
    # reset the cached loader so it re-reads from the new sample dir
    from lib import data

    data.load_raw.clear()
    return tmp_path


@pytest.mark.parametrize("mod", PAGES)
def test_page_renders_without_exception(sample_dir, mod):
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_VIEW_SCRIPT.format(mod=mod), default_timeout=60).run()
    assert not at.exception, f"{mod}: {[str(e.value) for e in at.exception]}"


def test_entrypoint_navigation_runs(sample_dir):
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(os.path.join(ROOT, "app", "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception, [str(e.value) for e in at.exception]
