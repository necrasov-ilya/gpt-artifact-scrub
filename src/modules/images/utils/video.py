from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

from moviepy import VideoFileClip, VideoClip
from PIL import Image


class VideoInfo(NamedTuple):
    """Информация о видео файле."""
    width: int
    height: int
    duration: float
    fps: float


def compute_video_hash(video_path: Path) -> str:
    """Вычисляет SHA256 хеш видео файла."""
    hasher = hashlib.sha256()
    with open(video_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_video_info(video_path: Path) -> VideoInfo:
    """
    Получает информацию о видео файле.
    
    Args:
        video_path: Путь к видео файлу
        
    Returns:
        VideoInfo с размерами, длительностью и FPS
    """
    with VideoFileClip(str(video_path)) as clip:
        return VideoInfo(
            width=clip.w,
            height=clip.h,
            duration=clip.duration,
            fps=clip.fps,
        )


def trim_video(
    video_path: Path,
    output_path: Path,
    max_duration: float,
) -> Path:
    """
    Обрезает видео до заданной максимальной длительности.
    
    Args:
        video_path: Путь к исходному видео
        output_path: Путь для сохранения обрезанного видео
        max_duration: Максимальная длительность в секундах
        
    Returns:
        Путь к обрезанному видео
    """
    with VideoFileClip(str(video_path)) as clip:
        if clip.duration <= max_duration:
            # Если видео уже короче, просто копируем
            return video_path
        
        trimmed = clip.subclipped(0, max_duration)
        trimmed.write_videofile(
            str(output_path),
            codec="libvpx-vp9",
            audio=False,
            fps=clip.fps,
            logger=None,
            preset="ultrafast",
            ffmpeg_params=[
                "-pix_fmt", "yuva420p",  # Формат пикселей для WebM с прозрачностью
            ],
        )
    
    return output_path


def slice_video_into_tiles(
    *,
    video_path: Path,
    rows: int,
    cols: int,
    padding: int,
    tile_size: int,
    target_fps: int,
    max_duration: float,
    temp_dir: Path,
    prefix: str,
) -> list[Path]:
    """
    Нарезает видео на анимированные тайлы в формате WebM.
    
    Args:
        video_path: Путь к видео файлу
        rows: Количество строк в сетке
        cols: Количество столбцов в сетке
        padding: Отступы в пикселях
        tile_size: Размер одного тайла
        target_fps: Целевой FPS для выходных видео
        max_duration: Максимальная длительность видео
        temp_dir: Директория для временных файлов
        prefix: Префикс для имён файлов
        
    Returns:
        Список путей к созданным анимированным тайлам
    """
    with VideoFileClip(str(video_path)) as clip:
        # Обрезаем по длительности если нужно
        if clip.duration > max_duration:
            clip = clip.subclipped(0, max_duration)
        
        # Устанавливаем целевой FPS
        if clip.fps != target_fps:
            clip = clip.with_fps(target_fps)
        
        width, height = clip.size
        
        # Вычисляем размеры canvas
        full_width = tile_size * cols
        full_height = tile_size * rows
        total_horizontal_padding = padding * 2 if cols > 0 else 0
        total_vertical_padding = padding * 2 if rows > 0 else 0
        available_width = max(1, full_width - total_horizontal_padding)
        available_height = max(1, full_height - total_vertical_padding)
        
        # Масштабируем с сохранением пропорций
        scale_x = available_width / width
        scale_y = available_height / height
        scale = min(scale_x, scale_y)
        scaled_width = max(1, int(round(width * scale)))
        scaled_height = max(1, int(round(height * scale)))
        
        # Изменяем размер видео
        resized_clip = clip.resized((scaled_width, scaled_height))
        
        # Вычисляем центрирование
        offset_x = padding + max(0, (available_width - scaled_width) // 2)
        offset_y = padding + max(0, (available_height - scaled_height) // 2)
        
        paths: list[Path] = []
        
        # Создаём тайлы для каждой ячейки сетки
        for row in range(rows):
            for col in range(cols):
                # Вычисляем область для кропа
                left = col * tile_size
                upper = row * tile_size
                right = left + tile_size
                lower = upper + tile_size
                
                # Создаём функцию для обработки каждого кадра
                def make_frame(t):
                    # Получаем кадр из resized_clip
                    frame = resized_clip.get_frame(t)
                    
                    # Создаём пустой canvas
                    canvas = Image.new("RGB", (full_width, full_height), (0, 0, 0))
                    
                    # Конвертируем frame в PIL Image
                    frame_img = Image.fromarray(frame)
                    
                    # Вставляем кадр на canvas с учётом offset
                    canvas.paste(frame_img, (offset_x, offset_y))
                    
                    # Вырезаем нужный тайл
                    tile = canvas.crop((left, upper, right, lower))
                    
                    # Конвертируем обратно в numpy array
                    import numpy as np
                    return np.array(tile)
                
                # Создаём новый клип с этой функцией
                tile_clip = VideoClip(make_frame, duration=resized_clip.duration)
                tile_clip = tile_clip.with_fps(target_fps)
                
                # Сохраняем в WebM
                filename = f"{prefix}_{row}_{col}.webm"
                path = temp_dir / filename
                
                tile_clip.write_videofile(
                    str(path),
                    codec="libvpx-vp9",
                    audio=False,
                    fps=target_fps,
                    logger=None,
                    preset="ultrafast",
                    ffmpeg_params=[
                        "-pix_fmt", "yuva420p",  # Формат пикселей для WebM
                        "-auto-alt-ref", "0",     # Отключаем auto-alt-ref для совместимости
                    ],
                )
                
                paths.append(path)
                tile_clip.close()
        
        resized_clip.close()
    
    return paths
