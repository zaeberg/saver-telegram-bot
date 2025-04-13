from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class TwitterDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()
        # Базовые опции для Twitter
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
        }

    async def download_video(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Twitter video download: {url}")

                # Получаем информацию для заголовка и ID
                info = await self._get_info(url, options={'extract_flat': True})
                video_id = info['id']

                # Твиты часто не имеют title, используем ID как fallback
                title = info.get('title') or info.get('full_text') or video_id
                # Обрезаем длинный текст твита, если он используется как title
                if len(title) > 100:
                    title = title[:97] + "..."

                # Опции загрузчика
                ydl_opts = {
                    **self.base_opts,
                     # Лучшее качество MP4, не превышающее лимит
                    'format': f'best[ext=mp4][filesize<{self.MAX_FILE_SIZE_BYTES}]/best[ext=mp4]',
                    'outtmpl': '%(id)s.%(ext)s',
                }

                logger.info("Attempting Twitter video download")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"Twitter video downloaded: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                 raise e
            except Exception as e:
                logger.error(f"Unexpected Twitter video download error: {e}", exc_info=True)
                raise DownloadError(f"Twitter video download failed: {str(e)}")

    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Twitter audio extraction: {url}")

                # Получаем информацию для заголовка
                info = await self._get_info(url, {'extract_flat': True})
                video_id = info['id']

                # Твиты часто не имеют title, используем ID как fallback
                title = info.get('title') or info.get('full_text') or video_id
                # Обрезаем длинный текст твита, если он используется как title
                if len(title) > 100:
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

                logger.info("Attempting Twitter audio download and extraction")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"Twitter audio extracted: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                 raise e
            except Exception as e:
                logger.error(f"Unexpected Twitter audio extraction error: {e}", exc_info=True)
                raise DownloadError(f"Twitter audio extraction failed: {str(e)}")
