from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import List

from PIL import Image

from ..domain.models import EmojiGridOption, SuggestedGridPlan


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
    padding = max(0, min(padding, tile_size // 4))
    with Image.open(io.BytesIO(image_bytes)) as source:
        rgba = source.convert("RGBA")
        width, height = rgba.size
        x_edges = _split_edges(width, grid.cols)
        y_edges = _split_edges(height, grid.rows)
        target_size = tile_size - padding * 2
        target_size = max(1, target_size)
        paths: list[Path] = []
        for row in range(grid.rows):
            for col in range(grid.cols):
                left = x_edges[col]
                upper = y_edges[row]
                right = x_edges[col + 1]
                lower = y_edges[row + 1]
                cropped = rgba.crop((left, upper, right, lower))
                resized = cropped.resize((target_size, target_size), Image.LANCZOS)
                canvas = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                offset = ((tile_size - target_size) // 2, (tile_size - target_size) // 2)
                canvas.paste(resized, offset, mask=resized)
                filename = f"{prefix}_{row}_{col}.png"
                path = temp_dir / filename
                canvas.save(path, format="PNG")
                paths.append(path)
        return paths
