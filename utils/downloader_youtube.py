from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class YouTubeDownloader(BaseDownloader):
    async def download_video(self, url: str, request_id: str = None) -> str:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting YouTube video info extraction from: {url}")

                # Получаем информацию о форматах
                info = self._get_info(url)
                video_id = info['id']
                video_title = info.get('title', 'Unknown Title')
                logger.info(f"Processing video: {video_title}")

                # Получаем размер аудио
                audio_formats = [
                    f for f in info.get('formats', [])
                    if f.get('vcodec') == 'none' and f.get('ext') == 'm4a' and f.get('filesize')
                ]
                audio_size = min(
                    (f.get('filesize', float('inf')) for f in audio_formats),
                    default=float('inf')
                ) / (1024 * 1024)  # MB

                logger.info(f"Found audio track size: {audio_size:.1f}MB")
                max_video_size = self.MAX_FILE_SIZE_MB - audio_size

                # Фильтруем MP4 форматы
                formats_info = [
                    {
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize', 0) / (1024 * 1024),  # MB
                        'height': f.get('height'),
                        'vcodec': f.get('vcodec'),
                    }
                    for f in info.get('formats', [])
                    if (f.get('ext') == 'mp4' and
                        f.get('vcodec') != 'none' and
                        f.get('filesize'))
                ]

                # Сортируем по качеству
                formats_info.sort(key=lambda x: (x.get('height', 0) or 0), reverse=True)

                # Выбираем подходящий формат
                suitable_format = next(
                    (fmt for fmt in formats_info if fmt['filesize'] <= max_video_size),
                    None
                )

                if not suitable_format:
                    raise DownloadError(
                        f"No suitable MP4 format found under {max_video_size:.1f}MB "
                        f"(audio: {audio_size:.1f}MB)"
                    )

                logger.info(
                    f"Selected format: ID {suitable_format['format_id']}, "
                    f"Video Size: {suitable_format['filesize']:.1f}MB, "
                    f"Audio Size: {audio_size:.1f}MB, "
                    f"Total Expected: {(suitable_format['filesize'] + audio_size):.1f}MB, "
                    f"Height: {suitable_format['height']}"
                )

                # Загружаем видео
                ydl_opts = {
                    'format': f"{suitable_format['format_id']}+bestaudio[ext=m4a]/best",
                    'outtmpl': str(self.temp_dir / f"{video_id}.%(ext)s"),
                    'quiet': True,
                    'merge_output_format': 'mp4',
                }

                logger.info("Starting video download...")
                output_path = self._download_with_options(url, ydl_opts)

                # Проверяем размер
                size_mb = self._check_file_size(output_path)
                logger.info(f"Download completed. Final size: {size_mb:.1f}MB")

                return output_path

            except Exception as e:
                raise DownloadError(f"YouTube video download error: {str(e)}")

    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting YouTube audio extraction from: {url}")

                # Получаем информацию о видео
                info = self._get_info(url)
                video_id = info['id']
                video_title = info.get('title', video_id)
                logger.info(f"Processing audio from: {video_title}")

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

                logger.info("Starting audio download...")
                output_path = self._download_with_options(url, ydl_opts)

                # Проверяем размер
                size_mb = self._check_file_size(output_path)
                logger.info(f"Audio extraction completed. Size: {size_mb:.1f}MB")

                return output_path, video_title

            except Exception as e:
                raise DownloadError(f"YouTube audio extraction error: {str(e)}")
