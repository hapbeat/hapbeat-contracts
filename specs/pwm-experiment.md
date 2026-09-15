# BandWL v4 MCU-PWM experiment — bias return configuration

Status: experimental device configuration for the `band_v4_pwm` firmware only.

The MCU-direct haptic path has two persisted signed DC-bias profiles:

- `idle`: standing bias while no playback source owns the motor.
- `play`: bias while local FIRE/PLAY, streamed CLIP, or a diagnostic tone is active.

The two profile values have the same sign. A playback stop first keeps `play`
for `post_play_hold_ms`, then transitions to `idle` over
`post_play_return_ms`. A new playback before or during the return cancels the
return and immediately selects `play`, so consecutive clips never dip to the
standing profile between them.

`bias_enabled` is a separately persisted global gate for both profiles. When
it is `false`, normal standing bias, playback bias, diagnostic tones, and
manual-bias tests resolve to exactly zero without overwriting either saved
profile. Re-enabling it restores the normal lifecycle (`idle` at rest, `play`
while playback is active). An explicit bounded `pwm_rewind` remains available
as a separate operator command.

## TCP / serial commands

| Command | Request | Persisted result |
| --- | --- | --- |
| `set_pwm_post_play_hold` | `{ "ms": 0..2000 }` | Delay before leaving the playback profile. Default: `500`. |
| `set_pwm_post_play_return` | `{ "ms": 0..2000 }` | Linear time for the playback-to-standing bias return. Default: `500`. `0` preserves the legacy fast (~20 ms full-scale) slew. |
| `set_pwm_bias_enabled` | `{ "enabled": boolean }` | Persistently enable or disable the configured profiles. `false` immediately targets zero without changing either saved duty. |

Both commands reply `{ "status": "ok" }` with the corresponding field. A
write affects the next playback stop; it does not alter an already-running
hold or return transition.

## `pwm_status` fields

- `post_play_hold_ms`, `post_play_hold_active`
- `post_play_return_ms`, `post_play_return_active`
- `bias_enabled`: whether the configured profiles are currently allowed to
  drive the motor. `false` means the effective normal target is zero.
- `bias_q15`: selected target; `bias_current_q15`: ISR-applied instantaneous
  bias. During a return these intentionally differ.

The Studio and Helper forward these commands unchanged; the device owns the
timer and NVS persistence, so no host-side timer participates in this
lifecycle.
