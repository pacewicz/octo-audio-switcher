import subprocess
import re
import logging
from collections import defaultdict

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def parsed_wpctl_status():
    result = subprocess.run(['wpctl', 'status'], stdout=subprocess.PIPE, text=True)
    lines = result.stdout.splitlines()

    data = defaultdict(lambda: defaultdict(lambda: {"list": {}, "current": None}))
    section = None
    category = None

    def parse_entry(line):
        current = False
        if '*' in line:
            current = True
            line = line.replace('*', '', 1)
        line = line.strip(" │")
        match = re.match(r'(\d+)\.\s+(.*)', line)
        if match:
            idx, desc = match.groups()
            return int(idx), desc.strip(), current
        return None, None, False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if re.match(r'^(Audio|Video|Settings)\s*$', line):
            section = line
            continue

        match_cat = re.match(r'[├└]─ ([\w\s]+):', line)
        if match_cat:
            category = match_cat.group(1).strip()
            continue

        if category in ["Sinks", "Sources", "Devices", "Sink endpoints", "Source endpoints", "Streams", "Default Configured Node Names"]:
            idx, desc, is_current = parse_entry(line)
            if idx is not None:
                if category == "Default Configured Node Names":
                    data[section][category][idx] = desc
                else:
                    data[section][category]["list"][idx] = desc
                    if is_current:
                        data[section][category]["current"] = idx

    return data


class SinkSwitcherExtension(Extension):
    def __init__(self):
        super(SinkSwitcherExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        items = []

        try:
            data = parsed_wpctl_status()

            audio_sinks = data.get("Audio", {}).get("Sinks", {})
            sinks_list = audio_sinks.get("list", {})
            current_id = audio_sinks.get("current")

            if not sinks_list:
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name='No audio sinks found',
                    description='No sinks available to switch',
                    on_enter=HideWindowAction()
                ))
                return RenderResultListAction(items)

            for sink_id, sink_desc in sinks_list.items():
                marker = "* " if sink_id == current_id else "  "
                label = f"{marker}{sink_id} → {sink_desc}"
                data = {"sink_id": sink_id, "sink_name": sink_desc}
                items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name=label,
                    description="Switch to this audio sink",
                    on_enter=ExtensionCustomAction(data, keep_app_open=False)
                ))

        except Exception as e:
            logger.exception("Error parsing wpctl status")
            items.append(ExtensionResultItem(
                icon='images/icon.png',
                name='Error retrieving sinks',
                description=str(e),
                on_enter=HideWindowAction()
            ))

        return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        sink_id = data.get("sink_id")
        sink_name = data.get("sink_name")

        try:
            subprocess.run(["wpctl", "set-default", str(sink_id)], check=True)
            success_msg = f"Switched to {sink_id} → {sink_name}"
            logger.info(success_msg)
            return RenderResultListAction([ExtensionResultItem(
                icon='images/icon.png',
                name=success_msg,
                description="Audio sink changed successfully",
                on_enter=HideWindowAction()
            )])
        except Exception as e:
            logger.exception("Failed to switch sink")
            return RenderResultListAction([ExtensionResultItem(
                icon='images/icon.png',
                name="Failed to switch sink",
                description=str(e),
                on_enter=HideWindowAction()
            )])


if __name__ == '__main__':
    SinkSwitcherExtension().run()
