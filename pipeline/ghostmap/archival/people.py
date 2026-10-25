#!/usr/bin/env python3
"""Detect standing pedestrians in archival photographs (foot and head pixels).

Uses torchvision's COCO-pretrained Keypoint R-CNN. A person is kept only if
detected confidently, upright (box at least 1.8x taller than wide), fully
inside the frame, at least 18 px tall, and with both ankles found: the ankle
midpoint is the ground contact, and the top of the box is the head. Hand-
coloured prints are not what the detector was trained on, so the kept set is
written out for inspection (an image with boxes) and used only as an optional
cue whose effect is reported as an ablation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT


def detect(path, score=0.8, min_height=18, aspect=1.8, margin=4):
    import torch
    from PIL import Image
    from torchvision.models.detection import KeypointRCNN_ResNet50_FPN_Weights, keypointrcnn_resnet50_fpn
    from torchvision.transforms.functional import to_tensor
    weights = KeypointRCNN_ResNet50_FPN_Weights.DEFAULT
    model = keypointrcnn_resnet50_fpn(weights=weights).eval()
    image = Image.open(path).convert('RGB'); w, h = image.size
    with torch.no_grad(): out = model([to_tensor(image)])[0]
    people = []
    for box, s, kp in zip(out['boxes'].numpy(), out['scores'].numpy(), out['keypoints'].numpy()):
        x0, y0, x1, y1 = box
        if s < score or (y1 - y0) < min_height or (y1 - y0) < aspect * (x1 - x0): continue
        if x0 < margin or y0 < margin or x1 > w - margin or y1 > h - margin: continue
        ankles = kp[[15, 16]]
        if (ankles[:, 2] < 0.5).any(): continue
        foot = ankles[:, :2].mean(0); head = np.array([(x0 + x1) / 2, y0])
        people.append({'foot': foot.tolist(), 'head': head.tolist(), 'score': float(s), 'box': box.tolist()})
    return people, (w, h)


def draw(path, people, out):
    from PIL import Image, ImageDraw
    image = Image.open(path).convert('RGB'); d = ImageDraw.Draw(image)
    for p in people:
        d.rectangle(p['box'], outline=(255, 40, 40), width=2)
        d.ellipse([p['foot'][0] - 3, p['foot'][1] - 3, p['foot'][0] + 3, p['foot'][1] + 3], fill=(40, 255, 40))
    image.save(out, quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/archival-people/people.json')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {}
    for path in args.images:
        people, size = detect(path)
        pageid = path.name.split('_')[0]
        result[pageid] = [[p['foot'], p['head']] for p in people]
        draw(path, people, args.output.parent / (pageid + '-people.jpg'))
        print(path.name, len(people), 'standing people kept', flush=True)
    args.output.write_text(json.dumps(result, indent=1) + '\n')


if __name__ == '__main__': main()
