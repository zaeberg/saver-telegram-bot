from contextlib import redirect_stdout, redirect_stderr
from moviepy import VideoFileClip
from typing import Tuple, Optional
from utils.logger import logger

# Открывает видеофайл и возвращает его ширину и высоту
def get_video_info(fp: str) -> Tuple[Optional[int], Optional[int]]:
    _width, _height = None, None
    try:
        with redirect_stdout(None), redirect_stderr(None):
            with VideoFileClip(fp) as clip:
                _width, _height = clip.w, clip.h
            return _width, _height
    except Exception as e:
        logger.error(f"Error reading video metadata with moviepy for {fp}: {e}", exc_info=True)
        return None, None
