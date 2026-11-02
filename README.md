# Android Power Meter (30W Scale, 100ms Sampling, 60 FPS Display)

Real-time power monitoring for Android devices with an animated 30W speedometer dial.

## Features
- Speedometer Meter: 72x32 sub-pixel Braille dial with physics-damped rotating needle (0 to 30W scale).
- High-Resolution Sub-Block Gauge: 47-character bar with 8th-step Unicode fractional precision.
- 100ms Hardware Polling: Samples battery current at 10 Hz via persistent Android Binder service calls.
- Clock-Paced 60 FPS Display: 60 FPS render loop with critically damped spring needle physics.
- Power Waveform: Scrolling history graph tracking recent fluctuations.
- Power Metrics:
  - Battery Inflow: Net electrical power entering the battery cell ($P = V \times I_{\text{charge}}$).
  - Total Input Draw: Estimated total power drawn from adapter/cable.
  - Active Draw: Power consumed by the phone when running on battery.
  - Battery state: Level percentage, remaining mAh, and terminal voltage.

## Usage

```bash
cd ~/Android

# Launch live 60 FPS monitor (0 - 30W scale)
./power_draw.sh

# Explicitly set 60 FPS and 30W max
./power_draw.sh -f 60 -m 30

# Single measurement snapshot
./power_draw.sh -s

# Output JSON
./power_draw.sh -j
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

