from typing import Tuple
from contextlib import nullcontext
from utils.logger import logger, request_context
from utils.downloader_base import BaseDownloader, DownloadError

class YouTubeDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()
        # Базовые опции для Youtube
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
        }

    async def download_video(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting YouTube video download: {url}")

                # Получаем информацию
                info = await self._get_info(url)
                video_id = info['id']
                title = info.get('title', 'Unknown Title')

                 # Получаем размер аудио
                audio_formats = [
                    f for f in info.get('formats', [])
                    if f.get('vcodec') == 'none' and f.get('ext') == 'm4a' and f.get('filesize')
                ]
                audio_size_bytes = min(
                    (f.get('filesize', float('inf')) for f in audio_formats),
                    default=float('inf')
                )
                audio_size_mb = audio_size_bytes / (1024 * 1024)
                logger.debug(f"Found audio track size: {audio_size_mb:.1f}MB")

                # Получаем размер видео по формуле (лимит телеграма - размер аудио)
                max_video_size = self.MAX_FILE_SIZE_BYTES - audio_size_bytes
                max_video_size_mb = max_video_size / (1024 * 1024)

                # Фильтруем форматы оставляем только mp4 и с явным кодеком и с явным размером
                formats_info = [
                    {
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize', 0),
                        'height': f.get('height'),
                        'vcodec': f.get('vcodec'),
                    }
                    for f in info.get('formats', [])
                    if (f.get('ext') == 'mp4' and
                        f.get('vcodec') != 'none' and
                        f.get('filesize'))
                ]

                # Сортируем форматы по качеству (сверху самые тяжелые/качественные)
                formats_info.sort(key=lambda x: (x.get('height', 0) or 0), reverse=True)

                # Выбираем подходящий формат
                # Из-за сортировки выберется лучшее качество подходящее под оставшийся после аудио размер в рамках лимита телеги
                selected_format = next((fmt for fmt in formats_info if fmt['filesize'] <= max_video_size), None)

                # Нет ни одного подходящего формата
                if not selected_format:
                    size_mb = (formats_info[-1]['filesize'] / (1024 * 1024)) + audio_size_mb
                    raise DownloadError(f"File is too large: {size_mb:.1f}MB")

                selected_format_video_size_mb = selected_format['filesize'] / (1024 * 1024)
                logger.debug(
                    f"Selected format: ID {selected_format['format_id']}, "
                    f"Video Size: {selected_format_video_size_mb:.1f}MB, "
                    f"Audio Size: {audio_size_mb:.1f}MB, "
                    f"Total Expected: {(selected_format_video_size_mb + audio_size_mb):.1f}MB, "
                    f"Height: {selected_format['height']}"
                )

                # Загружаем видео
                ydl_opts = {
                    **self.base_opts,
                    'format': f"{selected_format['format_id']}+bestaudio[ext=m4a]/best",
                    'outtmpl': f"{video_id}.mp4",
                    'merge_output_format': 'mp4',
                    # на всякий случай явно указываем что бы телеграм схавал файл
                    'postprocessor_args': {'ffmpeg': ['-movflags', '+faststart']}
                }

                logger.info(f"Attempting YouTube video download (format: {ydl_opts['format']})")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"YouTube video downloaded: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                raise e
            except Exception as e:
                logger.error(f"Unexpected YouTube video download error: {e}", exc_info=True)
                raise DownloadError(f"YouTube video download failed: {str(e)}")

    async def download_audio(self, url: str, request_id: str = None) -> Tuple[str, str]:
        with request_context(request_id) if request_id else nullcontext():
            try:
                logger.info(f"Starting YouTube audio extraction: {url}")

                # Получаем базовую информацию для заголовка и ID
                info = await self._get_info(url, options={'extract_flat': True})
                video_id = info['id']
                title = info.get('title', video_id)

                # Настройки для извлечения аудио
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

                logger.info("Attempting YouTube audio download and extraction")
                output_path = await self._download_with_options(url, ydl_opts)
                size_mb = await self._check_file_size(output_path)
                logger.info(f"YouTube audio extracted: {output_path} ({size_mb:.1f}MB)")

                return output_path, title

            except DownloadError as e:
                 raise e
            except Exception as e:
                logger.error(f"Unexpected YouTube audio extraction error: {e}", exc_info=True)
                raise DownloadError(f"YouTube audio extraction failed: {str(e)}")
