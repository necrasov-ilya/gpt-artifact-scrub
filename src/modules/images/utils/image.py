from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import List

from PIL import Image

from ..domain.models import EmojiGridOption, SuggestedGridPlan


def padding_level_to_pixels(level: int, tile_size: int) -> int:
    level = max(0, level)
    step = max(2, tile_size // 16)
    pixels = level * step
    return min(tile_size // 2, pixels)


def compute_image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.width, image.height


def _split_edges(length: int, parts: int) -> List[int]:
    edges = [0]
    for i in range(1, parts):
        edges.append(round(i * length / parts))
    edges.append(length)
    edges[0] = 0
    edges[-1] = length
    return edges


def suggest_grids(width: int, height: int, *, max_tiles: int, limit: int = 5) -> SuggestedGridPlan:
    candidates: list[tuple[float, EmojiGridOption]] = []
    for rows in range(1, min(10, max_tiles) + 1):
        for cols in range(1, min(10, max_tiles) + 1):
            tiles = rows * cols
            if tiles > max_tiles:
                continue
            cell_ratio = (width / cols) / (height / rows)
            score = abs(cell_ratio - 1.0)
            candidates.append((score, EmojiGridOption(rows=rows, cols=cols)))
    candidates.sort(key=lambda item: (item[0], item[1].tiles))
    unique: list[EmojiGridOption] = []
    for _score, option in candidates:
        if option not in unique:
            unique.append(option)
        if len(unique) >= limit:
            break
    if not unique:
        fallback = EmojiGridOption(rows=1, cols=1)
        unique = [fallback]
    else:
        fallback = unique[0]
    return SuggestedGridPlan(options=unique, fallback=fallback)


def slice_into_tiles(
    *,
    image_bytes: bytes,
    grid: EmojiGridOption,
    padding: int,
    tile_size: int,
    temp_dir: Path,
    prefix: str,
) -> list[Path]:
    padding_px = padding_level_to_pixels(padding, tile_size)
    with Image.open(io.BytesIO(image_bytes)) as source:
        rgba = source.convert("RGBA")
        width, height = rgba.size
        x_edges = _split_edges(width, grid.cols)
        y_edges = _split_edges(height, grid.rows)
        paths: list[Path] = []
        for row in range(grid.rows):
            for col in range(grid.cols):
                left = x_edges[col]
                upper = y_edges[row]
                right = x_edges[col + 1]
                lower = y_edges[row + 1]
                cropped = rgba.crop((left, upper, right, lower))
                left_pad = padding_px if col == 0 else 0
                right_pad = padding_px if col == grid.cols - 1 else 0
                top_pad = padding_px if row == 0 else 0
                bottom_pad = padding_px if row == grid.rows - 1 else 0
                target_width = max(1, tile_size - left_pad - right_pad)
                target_height = max(1, tile_size - top_pad - bottom_pad)
                resized = cropped.resize((target_width, target_height), Image.LANCZOS)
                canvas = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                canvas.paste(resized, (left_pad, top_pad), mask=resized)
                filename = f"{prefix}_{row}_{col}.png"
                path = temp_dir / filename
                canvas.save(path, format="PNG")
                paths.append(path)
        return paths
