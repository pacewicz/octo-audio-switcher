import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _stub_ulauncher():
    """`ulauncher` is only importable inside the Ulauncher runtime, not via
    pip. Stub just enough of its API surface for `main` to import cleanly."""
    class _Stub:
        def __init__(self, *args, **kwargs):
            pass

    modules = {
        "ulauncher": types.ModuleType("ulauncher"),
        "ulauncher.api": types.ModuleType("ulauncher.api"),
        "ulauncher.api.client": types.ModuleType("ulauncher.api.client"),
        "ulauncher.api.client.Extension": types.ModuleType("ulauncher.api.client.Extension"),
        "ulauncher.api.client.EventListener": types.ModuleType("ulauncher.api.client.EventListener"),
        "ulauncher.api.shared": types.ModuleType("ulauncher.api.shared"),
        "ulauncher.api.shared.event": types.ModuleType("ulauncher.api.shared.event"),
        "ulauncher.api.shared.item": types.ModuleType("ulauncher.api.shared.item"),
        "ulauncher.api.shared.item.ExtensionResultItem": types.ModuleType(
            "ulauncher.api.shared.item.ExtensionResultItem"),
        "ulauncher.api.shared.action": types.ModuleType("ulauncher.api.shared.action"),
        "ulauncher.api.shared.action.RenderResultListAction": types.ModuleType(
            "ulauncher.api.shared.action.RenderResultListAction"),
        "ulauncher.api.shared.action.ExtensionCustomAction": types.ModuleType(
            "ulauncher.api.shared.action.ExtensionCustomAction"),
        "ulauncher.api.shared.action.HideWindowAction": types.ModuleType(
            "ulauncher.api.shared.action.HideWindowAction"),
    }
    modules["ulauncher.api.client.Extension"].Extension = _Stub
    modules["ulauncher.api.client.EventListener"].EventListener = _Stub
    modules["ulauncher.api.shared.event"].KeywordQueryEvent = _Stub
    modules["ulauncher.api.shared.event"].ItemEnterEvent = _Stub
    modules["ulauncher.api.shared.item.ExtensionResultItem"].ExtensionResultItem = _Stub
    modules["ulauncher.api.shared.action.RenderResultListAction"].RenderResultListAction = _Stub
    modules["ulauncher.api.shared.action.ExtensionCustomAction"].ExtensionCustomAction = _Stub
    modules["ulauncher.api.shared.action.HideWindowAction"].HideWindowAction = _Stub
    sys.modules.update(modules)


_stub_ulauncher()

import main


# Captured from `pactl list cards` for a real connected Bluetooth headset
# (Sennheiser MOMENTUM 4, card bluez_card.80_C3_BA_1F_73_9E).
REAL_CARD_PROFILES_OUTPUT = """\
Card #1550
\tName: bluez_card.80_C3_BA_1F_73_9E
\tDriver: module-bluez5-device.c
\tOwner Module: n/a
\tProperties:
\t\tdevice.description = "MOMENTUM 4"
\tProfiles:
\t\toff: Off (sinks: 0, sources: 0, priority: 0, available: yes)
\t\theadset-head-unit: Headset Head Unit (HSP/HFP) (sinks: 1, sources: 1, priority: 1, available: yes)
\t\ta2dp-sink-sbc: High Fidelity Playback (A2DP Sink, codec SBC) (sinks: 1, sources: 0, priority: 18, available: yes)
\t\ta2dp-sink-sbc_xq: High Fidelity Playback (A2DP Sink, codec SBC-XQ) (sinks: 1, sources: 0, priority: 17, available: yes)
\t\ta2dp-sink-aptx: High Fidelity Playback (A2DP Sink, codec aptX) (sinks: 1, sources: 0, priority: 19, available: yes)
\t\ta2dp-sink: High Fidelity Playback (A2DP Sink, codec aptX HD) (sinks: 1, sources: 0, priority: 20, available: yes)
\tActive Profile: a2dp-sink-sbc_xq
\tPorts:
\t\theadset-output: Headset (type: Headset, priority: 0, latency offset: 0 usec, available)
"""


def _fake_run(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, stdout=REAL_CARD_PROFILES_OUTPUT, stderr="")


class ListCardProfilesTest(unittest.TestCase):
    def test_parses_priority_per_profile(self):
        with patch("main.subprocess.run", side_effect=_fake_run):
            profiles = main.list_card_profiles("bluez_card.80_C3_BA_1F_73_9E")
        self.assertEqual(profiles, {
            "off": 0,
            "headset-head-unit": 1,
            "a2dp-sink-sbc": 18,
            "a2dp-sink-sbc_xq": 17,
            "a2dp-sink-aptx": 19,
            "a2dp-sink": 20,
        })

    def test_missing_pactl_returns_empty_dict(self):
        with patch("main.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(main.list_card_profiles("bluez_card.x"), {})


class ChooseA2dpTargetTest(unittest.TestCase):
    def test_prefers_saved_profile_when_still_available(self):
        available = {"a2dp-sink": 20, "a2dp-sink-aptx": 19}
        self.assertEqual(
            main.choose_a2dp_target(available, saved="a2dp-sink-aptx"),
            "a2dp-sink-aptx",
        )

    def test_ignores_saved_profile_if_no_longer_available(self):
        available = {"a2dp-sink": 20}
        self.assertEqual(
            main.choose_a2dp_target(available, saved="a2dp-sink-ldac"),
            "a2dp-sink",
        )

    def test_prefers_generic_a2dp_sink_when_present(self):
        available = {
            "a2dp-sink-sbc": 18, "a2dp-sink-aptx": 19, "a2dp-sink": 20,
        }
        self.assertEqual(main.choose_a2dp_target(available), "a2dp-sink")

    def test_falls_back_to_highest_priority_variant_when_generic_absent(self):
        available = {"a2dp-sink-sbc": 18, "a2dp-sink-aptx": 19}
        self.assertEqual(main.choose_a2dp_target(available), "a2dp-sink-aptx")

    def test_returns_none_when_no_a2dp_profile_available(self):
        available = {"off": 0, "headset-head-unit": 1}
        self.assertIsNone(main.choose_a2dp_target(available))


class EnsureHighQualityProfileTimeoutTest(unittest.TestCase):
    def test_timeout_after_successful_switch_returns_none_but_reports_switched(self):
        bluez_props = {
            "node.name": "bluez_output.80_C3_BA_1F_73_9E.1",
            "api.bluez5.profile": "headset-head-unit",
            "device.id": "117",
        }
        card_props = {"device.name": "bluez_card.80_C3_BA_1F_73_9E"}

        def fake_get_node_properties(node_id):
            return card_props if node_id == "117" else bluez_props

        with patch("main.get_node_properties", side_effect=fake_get_node_properties), \
             patch("main.list_card_profiles", return_value={"a2dp-sink": 20}), \
             patch("main.get_saved_card_profile", return_value=None), \
             patch("main.subprocess.run") as mock_run, \
             patch("main.find_a2dp_sink", return_value=None) as mock_find:
            sink_id, profile_switched = main.ensure_high_quality_profile(55)

        mock_run.assert_called_once_with(
            ["pactl", "set-card-profile", "bluez_card.80_C3_BA_1F_73_9E", "a2dp-sink"],
            check=True,
        )
        mock_find.assert_called_once_with("117")
        self.assertIsNone(sink_id)
        self.assertTrue(profile_switched)


class FindA2dpSinkTest(unittest.TestCase):
    def test_prefers_a2dp_node_and_skips_hfp_via_snapshot(self):
        snapshot = {
            70: {"device.id": "117", "node.name": "bluez_output.80_C3_BA_1F_73_9E.1",
                 "api.bluez5.profile": "headset-head-unit"},   # HFP — must skip
            71: {"device.id": "117", "node.name": "bluez_output.80_C3_BA_1F_73_9E.2",
                 "api.bluez5.profile": "a2dp-sink"},            # A2DP — want this
        }
        with patch("main.get_all_node_properties", return_value=snapshot), \
             patch("main.time.sleep"):
            self.assertEqual(main.find_a2dp_sink("117"), 71)

    def test_returns_none_when_no_a2dp_appears(self):
        with patch("main.get_all_node_properties", return_value={}), \
             patch("main.time.sleep"):
            self.assertIsNone(main.find_a2dp_sink("117", tries=2))

    def test_falls_back_to_per_sink_inspect_without_pw_dump(self):
        status = {"Audio": {"Sinks": {"list": {88: "desc"}}}}
        props = {"device.id": "117", "node.name": "bluez_output.x",
                 "api.bluez5.profile": "a2dp-sink"}
        with patch("main.get_all_node_properties", return_value=None), \
             patch("main.parsed_wpctl_status", return_value=status), \
             patch("main.get_node_properties", return_value=props), \
             patch("main.time.sleep"):
            self.assertEqual(main.find_a2dp_sink("117"), 88)


if __name__ == "__main__":
    unittest.main()
