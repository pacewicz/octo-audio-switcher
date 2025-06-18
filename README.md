# Octo Audio Sink Switcher

Switch PipeWire audio output (sink) easily from Ulauncher.

![alt text](images/icon.png)

## Description

This Ulauncher extension lets you quickly view and switch the active audio sink in **PipeWire** (via `wpctl`) using Ulauncher’s fuzzy finder interface.
**Note:** This extension only works with PipeWire and its `wpctl` CLI tool. It does not support PulseAudio or other audio systems.

Ideal for users who want fast audio output switching without opening a full audio settings app.

## Features

* Lists all available audio sinks
* Highlights the current default sink
* Switches the default sink instantly when selected
* Uses native Ulauncher UI (no external tools like `fzf`)
* Lightweight and fast

## Requirements

* [Ulauncher](https://ulauncher.io) (with API v2 support)
* PipeWire with `wpctl` CLI tool available in your PATH

## Installation

### Manual

1. Clone or download this repository
2. In Ulauncher Preferences → Extensions → Add Extension → Install from ZIP file
3. Select the downloaded zip or folder

### From GitHub (if published)

1. In Ulauncher Preferences → Extensions → Add Extension → Install from GitHub
2. Paste the repo URL
3. Follow the prompts to install

## Usage

1. Activate Ulauncher (default Ctrl+Space)
2. Type the keyword (default: `sink`)
3. Select the desired audio sink from the list
4. The audio output will switch immediately

## Configuration

* The activation keyword can be changed in the extension preferences.

## Troubleshooting

* Make sure `wpctl` is installed and working (`wpctl status` shows your sinks)
* Verify your PipeWire setup is active
* Check Ulauncher logs for errors (`ulauncher -v` or system logs)

## License

[MIT License](LICENSE) © Christian Camacho
