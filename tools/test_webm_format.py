#!/usr/bin/env python3
"""
Скрипт для тестирования создания WebM файлов для Telegram стикеров.
Проверяет, что созданные файлы соответствуют требованиям Telegram.
"""

import subprocess
import sys
from pathlib import Path


def check_webm_format(file_path: Path) -> dict:
    """
    Проверяет формат WebM файла с помощью ffprobe.
    
    Требования Telegram для видео-стикеров:
    - Формат: WebM
    - Видео кодек: VP9 (vp9)
    - Без аудио (или аудио кодек: opus/vorbis)
    - Размер: до 512x512
    - FPS: до 30
    - Длительность: до 3 секунд
    """
    try:
        # Получаем информацию о файле
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt",
            "-show_entries", "format=format_name,duration",
            "-of", "json",
            str(file_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        data = json.loads(result.stdout)
        
        info = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Проверяем формат
        format_name = data.get("format", {}).get("format_name", "")
        if "webm" not in format_name.lower():
            info["valid"] = False
            info["errors"].append(f"Неверный формат: {format_name} (ожидается webm)")
        
        # Проверяем видео кодек
        streams = data.get("streams", [])
        if not streams:
            info["valid"] = False
            info["errors"].append("Видео поток не найден")
        else:
            video_codec = streams[0].get("codec_name", "")
            if video_codec != "vp9":
                info["valid"] = False
                info["errors"].append(f"Неверный кодек: {video_codec} (ожидается vp9)")
            
            # Проверяем размер
            width = streams[0].get("width", 0)
            height = streams[0].get("height", 0)
            if width > 512 or height > 512:
                info["warnings"].append(f"Размер {width}x{height} превышает 512x512")
            
            # Проверяем FPS
            fps_str = streams[0].get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = map(int, fps_str.split("/"))
                fps = num / den if den != 0 else 0
                if fps > 30:
                    info["warnings"].append(f"FPS {fps:.2f} превышает 30")
            
            # Проверяем pix_fmt
            pix_fmt = streams[0].get("pix_fmt", "")
            info["pix_fmt"] = pix_fmt
            if pix_fmt not in ["yuv420p", "yuva420p"]:
                info["warnings"].append(f"Формат пикселей {pix_fmt} может не поддерживаться")
        
        # Проверяем длительность
        duration = float(data.get("format", {}).get("duration", 0))
        if duration > 3.0:
            info["warnings"].append(f"Длительность {duration:.2f}с превышает 3 секунды")
        
        info["format"] = format_name
        info["codec"] = video_codec if streams else "unknown"
        info["size"] = f"{width}x{height}" if streams else "unknown"
        info["duration"] = duration
        
        return info
        
    except subprocess.CalledProcessError as e:
        return {
            "valid": False,
            "errors": [f"Ошибка ffprobe: {e.stderr}"]
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Неизвестная ошибка: {e}"]
        }


def main():
    if len(sys.argv) < 2:
        print("Использование: python test_webm_format.py <путь_к_webm_файлу>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    
    if not file_path.exists():
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    print(f"🔍 Проверка файла: {file_path}")
    print("-" * 60)
    
    info = check_webm_format(file_path)
    
    if info["valid"]:
        print("✅ Файл соответствует требованиям Telegram")
    else:
        print("❌ Файл НЕ соответствует требованиям Telegram")
    
    print(f"\n📊 Информация:")
    print(f"  Формат: {info.get('format', 'unknown')}")
    print(f"  Кодек: {info.get('codec', 'unknown')}")
    print(f"  Размер: {info.get('size', 'unknown')}")
    print(f"  Длительность: {info.get('duration', 0):.2f}с")
    print(f"  Pix_fmt: {info.get('pix_fmt', 'unknown')}")
    
    if info.get("errors"):
        print(f"\n❌ Ошибки:")
        for error in info["errors"]:
            print(f"  - {error}")
    
    if info.get("warnings"):
        print(f"\n⚠️ Предупреждения:")
        for warning in info["warnings"]:
            print(f"  - {warning}")
    
    sys.exit(0 if info["valid"] else 1)


if __name__ == "__main__":
    main()
