import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE_SNOWFLAKE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="Set RUN_LIVE_SNOWFLAKE_TESTS=1 to run Snowflake and Cortex tests.")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
