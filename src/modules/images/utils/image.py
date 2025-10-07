from __future__ import annotations

import hashlib
import io
from pathlib import Path
from PIL import Image

from ..domain.models import EmojiGridOption, SuggestedGridPlan


def padding_level_to_pixels(level: int, tile_size: int) -> int:
    level = max(0, level)
    step = max(2, tile_size // 20)
    pixels = level * step
    return min(tile_size // 2, pixels)


def compute_image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.width, image.height


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
        if width == 0 or height == 0:
            return []

        full_width = tile_size * grid.cols
        full_height = tile_size * grid.rows
        total_horizontal_padding = padding_px * 2 if grid.cols > 0 else 0
        total_vertical_padding = padding_px * 2 if grid.rows > 0 else 0
        available_width = max(1, full_width - total_horizontal_padding)
        available_height = max(1, full_height - total_vertical_padding)

        scale_x = available_width / width
        scale_y = available_height / height
        scale = min(scale_x, scale_y)
        scaled_width = max(1, int(round(width * scale)))
        scaled_height = max(1, int(round(height * scale)))
        scaled_image = rgba.resize((scaled_width, scaled_height), Image.LANCZOS)

        full_canvas = Image.new("RGBA", (full_width, full_height), (0, 0, 0, 0))
        offset_x = padding_px + max(0, (available_width - scaled_width) // 2)
        offset_y = padding_px + max(0, (available_height - scaled_height) // 2)
        full_canvas.paste(scaled_image, (offset_x, offset_y), mask=scaled_image)

        paths: list[Path] = []
        for row in range(grid.rows):
            for col in range(grid.cols):
                left = col * tile_size
                upper = row * tile_size
                right = left + tile_size
                lower = upper + tile_size
                tile_image = full_canvas.crop((left, upper, right, lower))
                filename = f"{prefix}_{row}_{col}.png"
                path = temp_dir / filename
                tile_image.save(path, format="PNG")
                paths.append(path)
        return paths
