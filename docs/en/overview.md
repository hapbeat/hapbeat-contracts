---
title: Contracts overview
description: Reference for the core concepts needed when using the Hapbeat SDK, including Event IDs, Kits, and Group IDs.
---

This page introduces the main concepts used with the Hapbeat SDK.

## Event ID

An Event ID identifies haptic content. The SDK sends this ID and Hapbeat plays the matching haptic.

**Format:** `<kit-name>.<clip-name>`

```
basic-exam-kit.sine_100hz_1s
my-game.sword-hit
my-game.footstep-grass
```

- `kit-name` is the Kit folder name. Do not use spaces; hyphen-separated names are recommended.
- `clip-name` is the WAV filename within the Kit, without its extension.
- The Unity SDK manages and composes IDs automatically in the EventMap window.

## Kit

A Kit is a package of haptic content: **WAV files plus `manifest.json`**.

```
my-game/               ← Kit folder (= kit-name)
  manifest.json        ← metadata and Event list
  install-clips/
    sword-hit.wav      ← FIRE-mode clip
    footstep-grass.wav
  stream-clips/        ← CLIP-mode clips (placed by Studio)
```

### Main `manifest.json` fields

```json
{
  "name": "my-game",
  "version": "1.0.0",
  "events": [
    {
      "id": "my-game.sword-hit",
      "clip": "sword-hit.wav",
      "mode": "command",
      "intensity": 0.8
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `name` | Kit name; becomes the Event ID prefix. |
| `id` | Event ID in `<kit-name>.<clip-name>` form. |
| `mode` | `command` (FIRE) or `stream_clip` (CLIP). |
| `intensity` | Baseline intensity from 0.0 to 1.0; multiplied by SDK Gain. |

Create and edit Kits in **Studio**, then deploy them to Hapbeat through Helper.

## Playback modes

| Mode | SDK name | Behavior |
| --- | --- | --- |
| FIRE | `command` | Deploy the Kit to the device first, then play it with a short command. Low-latency and stable. |
| CLIP | `stream_clip` | Stream WAV in real time from PC. No deployment needed; supports long content. |

## Group ID and Player number

Use these when multiple players or exhibition booths share one space.

| Concept | Use | Range |
| --- | --- | --- |
| **Group ID** | Logically groups devices. Only devices in the same Group receive a matching command. | 1–99 |
| **Player number** | Identifies an individual within a Group. | 1–99 |

For example, assign Group 1 to player A and Group 2 to player B so commands from A's SDK reach only A's Hapbeat.

Configure this in Studio's Devices tab. Device buttons can also adjust it by ±1.

## Communication protocol

The standard transport is **WifiUdp** (`wifi_udp`). The SDK sends unicast to known devices and uses Wi-Fi UDP broadcast only when it knows no device. Hapbeat processes only packets that match its own Group ID.

```
SDK (PC / Quest / smartphone)
  └─ Wi-Fi UDP unicast (broadcast only with no known device) → Hapbeat device (filters by Group ID)
```

No Bridge or USB connection is required. Devices work when connected to the same Wi-Fi network. Legacy `hapbeat-bridge` is not supported by the current system.
