#!/usr/bin/env python3
"""The short video clips the talk's deck embeds (`artifacts/presentation/clips/*.mp4`), cut from the recorded tour
and the splat fly-through with the ffmpeg that imageio-ffmpeg ships, as H.264 so PowerPoint plays them.

Two come from the tour video (`qa/record_tour.py`, 1600x900, 25 fps): the fragment snapping into the lidar campus
(the end of the "lost in space" chapter and the start of the "snap" chapter) and the whole "a photograph it has never
seen" chapter. The cut points are seconds into that recording; re-recording the tour with other dwell times means
checking them again (a contact sheet: `ffmpeg -i tour.webm -vf "fps=0.5,scale=192:-1,tile=10x9" -frames:v 1 sheet.png`).
The third is the fly-through `dense/splat_views.py` renders, re-encoded smaller.

Usage: .venv/bin/python pipeline/ghostmap/package/talk_clips.py [--tour artifacts/presentation/ghostmap-tour.webm]
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from ghostmap.paths import ROOT

PRESENTATION = ROOT / 'artifacts/presentation'
CLIPS = PRESENTATION / 'clips'
TOUR_CUTS = {'snap': (15.0, 19.0), 'photo': (136.0, 35.0)}   # clip name: (start s, duration s) in the tour video
FLY_THROUGH = PRESENTATION / 'splat-walk-plain-vs-lidar-taught.mp4'
WIDTH = 1280


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(source: Path, target: Path, start: float | None = None, duration: float | None = None):
    """H.264 at WIDTH pixels wide, no audio, the index at the front so playback starts at once."""
    cmd = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y']
    if start is not None: cmd += ['-ss', f'{start:.2f}']
    if duration is not None: cmd += ['-t', f'{duration:.2f}']
    cmd += ['-i', str(source), '-vf', f'scale={WIDTH}:-2', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
    subprocess.run(cmd, check=True)
    return target.stat().st_size


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--tour', type=Path, default=PRESENTATION / 'ghostmap-tour.webm')
    a = ap.parse_args()
    CLIPS.mkdir(parents=True, exist_ok=True)
    sizes = {name: encode(a.tour, CLIPS / f'{name}.mp4', start, duration) for name, (start, duration) in TOUR_CUTS.items()}
    sizes['fly-through'] = encode(FLY_THROUGH, CLIPS / 'fly-through.mp4')
    for name, size in sizes.items(): print(f'{CLIPS.relative_to(ROOT)}/{name}.mp4  {size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
