import os
import yt_dlp
from typing import Tuple
from pathlib import Path
from contextlib import nullcontext
from utils.logger import logger, request_context

class DownloadError(Exception):
    pass

def ensure_temp_dir():
    temp_dir = Path('temp')
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

async def download_youtube_video(url: str, request_id: str = None) -> str:
    with request_context(request_id) if request_id else nullcontext():
        temp_dir = ensure_temp_dir()

        try:
            logger.info(f"Starting video info extraction from: {url}")

            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                # Получаем информацию о форматах
                info = ydl.extract_info(url, download=False)
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


                # Максимальный размер для видео (оставляем место для аудио)
                max_video_size = 45 - audio_size

                # Фильтруем только MP4 видео форматы
                formats_info = [
                    {
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize', 0) / (1024 * 1024),  # MB
                        'height': f.get('height'),
                        'vcodec': f.get('vcodec'),
                    }
                    for f in info.get('formats', [])
                    if (f.get('ext') == 'mp4' and  # только MP4
                        f.get('vcodec') != 'none' and  # только видео форматы
                        f.get('filesize'))  # только с известным размером
                ]

                # Сортируем по высоте (качеству) по убыванию
                formats_info.sort(key=lambda x: (x.get('height', 0) or 0), reverse=True)

                # Выбираем лучший формат с учетом размера аудио
                suitable_format = next(
                    (fmt for fmt in formats_info if fmt['filesize'] <= max_video_size),
                    None
                )

                if not suitable_format:
                    raise DownloadError(f"No suitable MP4 format found under {max_video_size:.1f}MB (audio: {audio_size:.1f}MB)")

                # Создаем новые опции для загрузки конкретного формата
                ydl_opts = {
                    'format': f"{suitable_format['format_id']}+bestaudio[ext=m4a]/best",
                    'outtmpl': str(temp_dir / '%(id)s.%(ext)s'),
                    'quiet': True,
                    'merge_output_format': 'mp4',
                }

                logger.info(f"Selected format: ID {suitable_format['format_id']}, "
                        f"Video Size: {suitable_format['filesize']:.1f}MB, "
                        f"Audio Size: {audio_size:.1f}MB, "
                        f"Total Expected Size: {(suitable_format['filesize'] + audio_size):.1f}MB, "
                        f"Height: {suitable_format['height']}")

                logger.info("Starting video download...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    video_id = info['id']
                    output_path = str(temp_dir / f"{video_id}.mp4")

                    if not os.path.exists(output_path):
                        raise DownloadError("Downloaded file not found")

                    final_size = os.path.getsize(output_path) / (1024 * 1024)
                    logger.info(f"Download completed. Final size: {final_size:.1f}MB")

                    if final_size > 45:
                        logger.error(f"File too large: {final_size:.1f}MB")
                        os.remove(output_path)
                        raise DownloadError(f"Final video size ({final_size:.1f}MB) is too large for Telegram")

                    return output_path

        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            raise DownloadError(f"Error downloading video: {str(e)}")


async def download_youtube_audio(url: str, request_id: str = None) -> Tuple[str, str]:
    with request_context(request_id) if request_id else nullcontext():
        temp_dir = ensure_temp_dir()

        try:
            logger.info(f"Starting audio extraction from: {url}")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(temp_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'keepvideo': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Получаем информацию о видео
                info = ydl.extract_info(url, download=False)
                video_id = info['id']
                video_title = info.get('title', video_id)
                logger.info(f"Processing audio from: {video_title}")

                logger.info("Starting audio download...")
                ydl.download([url])

                output_path = str(temp_dir / f"{video_id}.mp3")

                if not os.path.exists(output_path):
                    raise DownloadError("Downloaded audio file not found")

                file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                logger.info(f"Audio download completed. Size: {file_size:.1f}MB")

                if file_size > 45:
                    logger.error(f"Audio file too large: {file_size:.1f}MB")
                    os.remove(output_path)
                    raise DownloadError(f"Audio file is too large ({file_size:.1f}MB)")

                logger.info(f"Successfully downloaded audio: {output_path} ({file_size:.1f}MB)")
                return output_path, video_title

        except Exception as e:
            logger.error(f"Error downloading audio: {str(e)}")
            raise DownloadError(f"Error downloading audio: {str(e)}")


if __name__ == '__main__':
    # Test the downloader
    import asyncio

    async def test_downloader():
        # Test valid YouTube Shorts URL
        test_url = "https://youtu.be/A69LoPaZOLA?si=EptdTsLIe5O-czSF"
        try:
            file_path = await download_youtube_video(test_url)
            print(f"Success! File downloaded to: {file_path}")

            # Cleanup (uncomment to automatically delete test file)
            # os.remove(file_path)

        except DownloadError as e:
            print(f"Download failed: {e}")

    asyncio.run(test_downloader())
