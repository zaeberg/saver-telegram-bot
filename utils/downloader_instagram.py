from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class InstagramDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()

        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'no_color': True,
            'ignoreerrors': True,
            'extractor_args': {
                'instagram': {
                    'skip_download': False,
                    'extract_metadata': False,
                    'get_likes': False,
                }
            }
        }


    async def download_video(self, url: str, request_id: str = None) -> str:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Instagram Reel download: {url}")

                info = self._get_info(url)
                video_id = info['id']
                title = info.get('title', 'Instagram Reel')

                logger.info(f"Processing Reel: {title}")

                # Настройки загрузки для Instagram
                ydl_opts = {
                    **self.base_opts,
                    'format': 'best[ext=mp4]',
                    'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s')
                }

                try:
                    output_path = self._download_with_options(url, ydl_opts)
                except Exception as e:
                    if "Login required" in str(e):
                        raise DownloadError("This Reel requires Instagram login (private content)")
                    raise

                size_mb = self._check_file_size(output_path)
                logger.info(f"Instagram Reel downloaded: {output_path} ({size_mb:.1f}MB)")

                return output_path

            except Exception as e:
                raise DownloadError(f"Instagram Reel download error: {str(e)}")

    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting Instagram Reel audio extraction: {url}")

                # Получаем информацию о видео
                info = self._get_info(url)
                video_id = info['id']
                title = info.get('title', video_id)

                # Настройки для извлечения аудио
                ydl_opts = {
                    **self.base_opts,
                    'format': 'bestaudio/best',
                    'outtmpl': {'default': str(self.temp_dir / '%(id)s.%(ext)s')},
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'keepvideo': False,
                }

                try:
                    output_path = self._download_with_options(url, ydl_opts)
                except Exception as e:
                    if "Login required" in str(e):
                        raise DownloadError("This Reel requires Instagram login (private content)")
                    raise

                size_mb = self._check_file_size(output_path)
                logger.info(f"Instagram audio extracted: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except Exception as e:
                raise DownloadError(f"Instagram audio extraction error: {str(e)}")
