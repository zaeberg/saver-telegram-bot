from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class TwitterDownloader(BaseDownloader):
    async def download_video(self, url: str, request_id: str = None) -> str:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Twitter video download: {url}")

                # Получаем информацию о видео
                info = self._get_info(url)
                video_id = info['id']

                # Настройки загрузки для Twitter
                ydl_opts = {
                    'format': 'best[ext=mp4]',  # Лучшее качество MP4
                    'outtmpl': str(self.temp_dir / f"{video_id}.%(ext)s"),
                    'quiet': True,
                }

                output_path = self._download_with_options(url, ydl_opts)
                size_mb = self._check_file_size(output_path)

                logger.info(f"Twitter video downloaded: {output_path} ({size_mb:.1f}MB)")
                return output_path

            except Exception as e:
                raise DownloadError(f"Twitter video download error: {str(e)}")

    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Twitter audio extraction: {url}")

                # Получаем информацию о видео
                info = self._get_info(url)
                video_id = info['id']
                title = info.get('title', video_id)

                # Настройки для извлечения аудио
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': str(self.temp_dir / f"{video_id}.%(ext)s"),
                    'quiet': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'keepvideo': False,
                }

                output_path = self._download_with_options(url, ydl_opts)
                size_mb = self._check_file_size(output_path)

                logger.info(f"Twitter audio extracted: {output_path} ({size_mb:.1f}MB)")
                return output_path, title

            except Exception as e:
                raise DownloadError(f"Twitter audio extraction error: {str(e)}")
