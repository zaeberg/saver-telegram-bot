import asyncio
import functools
import os
import yt_dlp
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Dict
from utils.logger import logger

class DownloadError(Exception):
    pass

class BaseDownloader(ABC):
    def __init__(self, temp_dir: Path = Path('temp')):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True) # на всякий случай создаем директорию
        self.MAX_FILE_SIZE_BYTES = 49 * 1024 * 1024 # 49 MB (лимит телеграма 50mb)

    # Вспомогательный метод для запуска синхронных функций в отдельном потоке
    async def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        partial_func = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, partial_func)

    # Асинхронно получает информацию о медиафайле с помощью yt-dlp.
    async def _get_info(self, url: str, options: Dict = None) -> dict:
        ydl_opts = {'quiet': True, 'no_warnings': True, **(options or {})}

        def extract_info_sync():
            # Эта функция будет выполняться в другом потоке
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    return ydl.extract_info(url, download=False)
                except yt_dlp.utils.DownloadError as e:
                    # Преобразуем ошибку yt-dlp в нашу ошибку
                    raise DownloadError(f"yt-dlp info extraction failed: {e}")
                except Exception as e:
                     raise DownloadError(f"Unexpected error during info extraction: {e}")

        return await self._run_sync(extract_info_sync)

    # Асинхронно скачивает файл с указанными опциями yt-dlp.
    async def _download_with_options(self, url: str, options: Dict) -> str:
        # Сохраняем исходный шаблон и формируем полный путь
        original_outtmpl_pattern = options.get('outtmpl', '%(id)s.%(ext)s')

        # Проверка что исходный tmpl это строка или Path
        if not isinstance(original_outtmpl_pattern, (str, Path)):
             logger.warning(f"Received non-string outtmpl pattern: {original_outtmpl_pattern}. Using default.")
             original_outtmpl_pattern = '%(id)s.%(ext)s'

        # Формируем строку полного пути которую будем использовать дальше
        full_path_tmpl_str = str(self.temp_dir / original_outtmpl_pattern)
        logger.debug(f"Setting full_path_tmpl_str for yt-dlp: {full_path_tmpl_str}")

        # Обновляем шаблон имени выходного файла для передачи в yt-dlp
        options['outtmpl'] = full_path_tmpl_str

        def download_sync():
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    # Скачиваем
                    info = ydl.extract_info(url, download=True)

                    # yt-dlp может изменить имя файла (например, при постпроцессинге)
                    # Получаем реальный путь из информации после скачивания
                    downloaded_path = ydl.prepare_filename(info)

                    # Если при постпроцессинге имя файла изменилось, то пробуем подобрать новое с правильным разрешением
                    # Обычно такое происходит при загрузке аудио потому скачивается mp4 видео и из него извлекается mp3 аудио
                    # И старый файл удаляется, поэтому тут внутри ищем этот фоллбек и используем его как новый путь до файла
                    if not os.path.exists(downloaded_path):
                        # Попробуем стандартный путь если prepare_filename не сработал
                        standard_path_base = os.path.splitext(full_path_tmpl_str)[0]

                        # смотрим на расширения скачанного файла
                        possible_exts = [info.get('ext')]

                        # Проверяем, был ли постпроцессор для аудио
                        # И добавляем кодек из постпроцессора, если да
                        postprocessor = next((pp for pp in options.get('postprocessors', []) if pp.get('key') == 'FFmpegExtractAudio'), None)
                        if postprocessor:
                            possible_exts.append(postprocessor.get('preferredcodec', 'mp3'))

                        # Ищем запасной вариант для имени скачанного файла
                        found_fallback = False
                        for ext in possible_exts:
                             if ext:
                                 fallback_path = f"{standard_path_base}.{ext}"
                                 if os.path.exists(fallback_path):
                                     downloaded_path = fallback_path
                                     found_fallback = True
                                     logger.debug(f"Fallback successful. Using path: {downloaded_path}")
                                     break

                        # Если и запасной вариант не найден то харкаем ошибкой
                        if not found_fallback:
                            raise DownloadError(f"Downloaded file path detection failed. Expected: '{downloaded_path}'")

                    # Возвращаем найденный путь
                    return downloaded_path

            except yt_dlp.utils.DownloadError as e:
                 # Проверяем специфичные ошибки yt-dlp
                 if "File is larger than max-filesize" in str(e):
                     raise DownloadError(f"File is too large (yt-dlp check): {e}")
                 elif "Login required" in str(e):
                     raise DownloadError("Content requires login (private or restricted).")
                 raise DownloadError(f"yt-dlp download failed: {e}")
            except Exception as e:
                 raise DownloadError(f"Unexpected error during download: {e}")

        actual_path = await self._run_sync(download_sync)
        logger.debug(f"Download successful. Actual path: {actual_path}")
        return actual_path

    # Асинхронно проверяет размер файла и удаляет его, если он слишком большой.
    async def _check_file_size(self, filepath: str) -> float:
        try:
            size_bytes = await self._run_sync(os.path.getsize, filepath)
        except FileNotFoundError:
             raise DownloadError(f"File not found for size check: {filepath}")
        except Exception as e:
             raise DownloadError(f"Could not get file size for {filepath}: {e}")

        size_mb = size_bytes / (1024 * 1024)
        if size_bytes > self.MAX_FILE_SIZE_BYTES:
            try:
                await self._run_sync(os.remove, filepath)
            except Exception as e:
                # Логгируем все ошибки но наверх выбрасываем основную ошибку про размер файла
                # Используем print, логгер может быть тут недоступен
                print(f"[WARN] Could not remove oversized file {filepath}: {e}")

            raise DownloadError(f"File is too large: {size_mb:.1f}MB")
        return size_mb

    @abstractmethod
    async def download_video(self, url: str, request_id: str = None) -> Tuple[str, str]:
        pass

    @abstractmethod
    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        pass
