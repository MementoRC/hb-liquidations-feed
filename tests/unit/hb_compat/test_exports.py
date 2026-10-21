"""hb_compat must expose the upstream-compatible public names."""

import importlib

import pytest

import liquidations_feed.hb_compat as compat
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.hb_compat.factory import (
    UnsupportedConnectorError,
    UnsupportedConnectorException,
)

EXPECTED = [
    "Liquidation",
    "LiquidationSide",
    "LiquidationsConfig",
    "LiquidationsFactory",
    "UnsupportedConnectorException",
    "get_logger",
]


def test_all_matches_expected():
    assert sorted(compat.__all__) == sorted(EXPECTED)


@pytest.mark.parametrize("name", EXPECTED)
def test_name_importable(name):
    module = importlib.import_module("liquidations_feed.hb_compat")
    assert getattr(module, name) is not None


def test_data_types_are_core_objects():
    assert compat.Liquidation is Liquidation
    assert compat.LiquidationSide is LiquidationSide


def test_exception_alias_is_identical_object():
    assert UnsupportedConnectorException is UnsupportedConnectorError
    assert compat.UnsupportedConnectorException is UnsupportedConnectorError


def test_factory_raises_upstream_named_exception():
    config = compat.LiquidationsConfig(connector="nope")
    with pytest.raises(compat.UnsupportedConnectorException):
        compat.LiquidationsFactory.get_liquidations_feed(config)
