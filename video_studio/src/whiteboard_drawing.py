"""Trace raster artwork with a moving pen, then brush in flat illustration colors.

Added for photographic drawing-hand whiteboard videos; uses Pillow/NumPy already
available in the video renderer, with no OpenCV runtime dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

Point = Tuple[float, float]


@dataclass
class StrokePlan:
    strokes: List[List[Point]]
    distances: List[np.ndarray]
    total_length: float
    width: int


def make_plan(strokes: List[List[Point]], width: int) -> StrokePlan:
    distances = []
    for stroke in strokes:
        xy = np.asarray(stroke, dtype=float)
        lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
        distances.append(np.concatenate(([0.], np.cumsum(lengths))))
    return StrokePlan(strokes, distances, sum(max(1., float(d[-1])) for d in distances), width)


def trace_outline(layer: Image.Image) -> Tuple[Image.Image, StrokePlan]:
    """Derive connected short pen strokes from visible dark lines and color edges."""
    w, h = layer.size
    scale = min(1., 240. / max(w, h))
    small = layer.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    rgba = np.asarray(small)
    alpha = rgba[:, :, 3] / 255.
    rgb = rgba[:, :, :3] * alpha[:, :, None] + 255 * (1 - alpha[:, :, None])
    gray = rgb.mean(axis=2)
    edge = np.zeros_like(gray, dtype=bool)
    edge[:, 1:] |= np.max(np.abs(rgb[:, 1:] - rgb[:, :-1]), axis=2) > 38
    edge[1:, :] |= np.max(np.abs(rgb[1:] - rgb[:-1]), axis=2) > 38
    visible = (alpha > .25) & ((gray < 155) | edge)
    cells = set(zip(*np.nonzero(visible)))
    sx, sy = w / small.width, h / small.height
    strokes = []
    previous = (0, 0)
    directions = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
    while cells:
        current = min(cells, key=lambda cell: (cell[0] - previous[0]) ** 2 + (cell[1] - previous[1]) ** 2)
        chain = []
        while current in cells:
            cells.remove(current)
            y, x = current
            chain.append(((x + .5) * sx, (y + .5) * sy))
            neighbours = [(y + dy, x + dx) for dy, dx in directions if (y + dy, x + dx) in cells]
            if not neighbours:
                break
            current = neighbours[0]
        previous = current
        strokes.append(chain if len(chain) > 1 else chain * 2)
    width = max(2, round(max(sx, sy) * 1.7))
    # Keep the outline thin at native size, including internal boundaries of color fills.
    full = np.asarray(layer)
    fa = full[:, :, 3] / 255.
    frgb = full[:, :, :3] * fa[:, :, None] + 255 * (1 - fa[:, :, None])
    edges = np.zeros((h, w), dtype=bool)
    edges[:, 1:] |= np.max(np.abs(frgb[:, 1:] - frgb[:, :-1]), axis=2) > 22
    edges[1:, :] |= np.max(np.abs(frgb[1:] - frgb[:-1]), axis=2) > 22
    ink = (fa > .3) & ((frgb.mean(axis=2) < 115) | edges)
    outline = Image.new("RGBA", (w, h), (43, 48, 54, 0))
    outline.putalpha(Image.fromarray((ink * 255).astype("uint8")))
    return outline, make_plan(strokes, width)


def brush_plan(size: Tuple[int, int], width: int) -> StrokePlan:
    """Connected alternating brush rows; the tip follows the actual reveal frontier."""
    w, h = size
    width = max(4, width)
    rows = []
    ys = list(range(0, h, max(2, width // 2))) + [h - 1]
    for i, y in enumerate(ys):
        ends = (0., float(w - 1)) if i % 2 == 0 else (float(w - 1), 0.)
        rows.append([(ends[0], float(y)), (ends[1], float(y))])
    return make_plan(rows, width)


def draw_progress(plan: StrokePlan, progress: float, size: Tuple[int, int]) -> Tuple[Image.Image, Point]:
    """Return a monotone reveal mask and the exact last point touched by the pen."""
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    remaining = max(0., min(1., progress)) * plan.total_length
    tip = plan.strokes[0][0] if plan.strokes else (0., 0.)
    if progress <= 0 or not plan.strokes:
        return mask, tip
    for stroke, distances in zip(plan.strokes, plan.distances):
        length = max(1., float(distances[-1]))
        if remaining >= length:
            d.line(stroke, fill=255, width=plan.width, joint="curve")
            tip = stroke[-1]
            remaining -= length
            continue
        idx = min(len(stroke) - 1, int(np.searchsorted(distances, remaining, side="right")))
        if idx <= 0:
            tip = stroke[0]
            points = [tip, tip]
        else:
            span = distances[idx] - distances[idx - 1]
            fraction = (remaining - distances[idx - 1]) / span if span > 0 else 0.
            a, b = stroke[idx - 1], stroke[idx]
            tip = (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
            points = stroke[:idx] + [tip]
        d.line(points, fill=255, width=plan.width, joint="curve")
        break
    return mask, tip
