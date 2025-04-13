from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class InstagramDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()
        # Базовые опции для Instagram
        # TODO: в будущем можно добавить cookies/cookiefile для доступа к приватным рилсам
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            # 'cookiefile': 'instagram_cookies.txt'
        }

    async def download_video(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Instagram video download: {url}")

                # Получаем информацию для заголовка и ID
                info = await self._get_info(url, {'extract_flat': True})
                video_id = info['id']

                # Instagram часто не имеет title, используем описание или ID
                title = info.get('title') or info.get('description') or video_id
                if len(title) > 100: # Обрезаем длинное описание
                     title = title[:97] + "..."

                # Опции загрузчика
                ydl_opts = {
                    **self.base_opts,
                    # Лучшее качество MP4, не превышающее лимит
                    'format': f'best[ext=mp4][filesize<{self.MAX_FILE_SIZE_BYTES}]/best[ext=mp4]',
                    'outtmpl': '%(id)s.%(ext)s',
                }

                logger.info("Attempting Instagram video download")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"Instagram video downloaded: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                 # Проверяем специфичную ошибку Instagram о логине
                 if "Login required" in str(e):
                     logger.warning(f"Instagram login required for {url}")
                     raise DownloadError("This content requires Instagram login (private or restricted).")
                 raise e
            except Exception as e:
                logger.error(f"Unexpected Instagram video download error: {e}", exc_info=True)
                raise DownloadError(f"Instagram video download failed: {str(e)}")


    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Instagram audio download: {url}")

                # Получаем информацию для заголовка и ID
                info = await self._get_info(url, {'extract_flat': True})
                video_id = info['id']

                # Instagram часто не имеет title, используем описание или ID
                title = info.get('title') or info.get('description') or video_id
                if len(title) > 100: # Обрезаем длинное описание
                     title = title[:97] + "..."

                # Опции загрузчика и настройки для извлечения аудио
                ydl_opts = {
                    **self.base_opts,
                    'format': 'bestaudio/best',
                    'outtmpl': f"{video_id}.%(ext)s",
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'keepvideo': False, # удаляем видео файл после извлечения аудио
                }

                logger.info("Attempting Instagram audio download and extraction")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"Instagram audio extracted: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                # Проверяем специфичную ошибку Instagram о логине
                 if "Login required" in str(e):
                     logger.warning(f"Instagram login required for {url}")
                     raise DownloadError("This content requires Instagram login (private or restricted).")
                 raise e
            except Exception as e:
                logger.error(f"Unexpected Instagram audio extraction error: {e}", exc_info=True)
                raise DownloadError(f"Instagram audio extraction failed: {str(e)}")
