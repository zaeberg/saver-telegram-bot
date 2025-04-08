from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Tuple, Dict
import yt_dlp

class DownloadError(Exception):
    pass

class BaseDownloader(ABC):
    def __init__(self, temp_dir: Path = Path('temp')):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True)
        self.MAX_FILE_SIZE_MB = 45

    def _get_info(self, url: str, options: Dict = None) -> dict:
        # Получение информации о медиафайле
        ydl_opts = {'quiet': True, **(options or {})}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _download_with_options(self, url: str, options: Dict) -> str:
        # Загрузка с указанными опциями
        with yt_dlp.YoutubeDL(options) as ydl:
            # Скачиваем файл
            info = ydl.extract_info(url, download=True)
            video_id = info['id']

            # Определяем расширение файла
            if any(pp.get('key') == 'FFmpegExtractAudio' for pp in options.get('postprocessors', [])):
                # Если это аудио с конвертацией в mp3
                ext = 'mp3'
            else:
                # Для видео используем mp4 (так как мы указываем merge_output_format='mp4')
                ext = 'mp4'

            # Формируем реальный путь к файлу
            actual_path = str(self.temp_dir / f"{video_id}.{ext}")

            return actual_path

    def _check_file_size(self, filepath: str) -> float:
        # Проверка размера файла
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > self.MAX_FILE_SIZE_MB:
            os.remove(filepath)
            raise DownloadError(f"File is too large: {size_mb:.1f}MB")
        return size_mb

    @abstractmethod
    async def download_video(self, url: str, request_id: str = None) -> str:
        pass

    @abstractmethod
    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        pass
