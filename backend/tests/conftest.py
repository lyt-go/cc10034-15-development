"""pytest 公共夹具：每个用例前把内存仓库重置回种子状态，保证用例间互不污染。"""
from __future__ import annotations

import pytest

from app.seed import SEED_ROWS
from app.store import store


@pytest.fixture(autouse=True)
def reset_store():
    # 直接重建底层表，避免各用例的状态流转影响后续用例。
    store._tables = {  # noqa: SLF001 - 测试夹具需要重置内存仓库
        name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
    }
    yield
