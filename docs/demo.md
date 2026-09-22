# Jevidence demo transcript

[Watch or download the 50-second MP4](../assets/jevidence-demo.mp4) · [Back to the README](../README.md)

The video is a silent, captioned terminal walkthrough rendered from real local
CLI output on September 22, 2026. All judgments are constructed fixtures, not
captured Jev responses. Selected output fields are shown for readability.

| Time | What happens |
| --- | --- |
| 0–5 seconds | Jevidence separates typed judgment, code-owned policy, and a proposed next step. No API key is needed for this offline demo. |
| 5–16 seconds | `python3 -m jevidence demo` returns the synthetic choice `runtime`, confidence `0.72`, and reproduction probability `0.95`. Confidence is below the `0.8` route threshold, so the proposed queue is `general-triage`. Nothing is applied. |
| 16–27 seconds | `python3 -m jevidence demo --route-floor 0.7` keeps the evidence unchanged. The route threshold now passes, as does the reproduction threshold (`0.95 >= 0.85`), so the proposal becomes `runtime-investigation`. These thresholds are illustrative. |
| 27–35 seconds | `python3 -m jevidence evaluate` reports eight cases matching their expected decisions at the default thresholds. Constructed cases test code behavior, not model accuracy or calibration. |
| 35–42 seconds | `python3 -m unittest discover -s tests -v` reports 15 passing tests and five skipped optional SDK transport tests in this dependency-free run. The tested paths include threshold boundaries and judgment failure handling. |
| 42–50 seconds | Clone this repository, run `python3 -m jevidence demo`, and read the companion developer guide. |

The capture used Python 3.12.14 and project code at commit
[`69a205a`](https://github.com/peakevergreen/jevidence/tree/69a205ae51fa2d1c5007c4da97e9c6ff1ea972ea).
The optional SDK was not installed for the video. No provider calls or quality
benchmarks were run. See the [developer guide](https://peakevergreen.com/blog/jev-for-developers/)
for the surrounding design, and [WebVTT captions](../assets/jevidence-demo.vtt)
for a separate text track.
