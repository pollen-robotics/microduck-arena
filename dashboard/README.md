---
title: Microduck Arena usage
emoji: 📈
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Microduck Arena usage

Pollen's private dashboard of how the [Microduck Arena](https://huggingface.co/spaces/pollen-robotics/microduck-arena)
is used: visitors, time spent, clicks to the store, players, voters and runs, by day and week.

It reads two private datasets: `pollen-robotics/microduck-arena-runs`, the run log, and
`pollen-robotics/microduck-arena-usage`, what the Arena's pages report (`arena/usage.py`). Its
`HF_TOKEN` secret needs read access to both.

Deployed from `dashboard/` in [microduck-arena](https://github.com/pollen-robotics/microduck-arena)
on every push to `main` that changes it. Run it locally with `HF_TOKEN=… python app.py` and open
http://localhost:7860; `python -m pytest test_stats.py` tests the counting.
