"""Tests for BehaviorEngine — registry fields and activity tracking."""
import time
import types
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import master.registry as reg


def test_registry_has_last_activity():
    assert hasattr(reg, 'last_activity'), "reg.last_activity not defined"
    assert isinstance(reg.last_activity, float)


def test_registry_has_behavior_engine():
    assert hasattr(reg, 'behavior_engine'), "reg.behavior_engine not defined"
    assert reg.behavior_engine is None
