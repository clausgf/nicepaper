import logging
import re

logger = logging.getLogger('uvicorn.error')


filename_regex_str = r'^[a-zA-Z0-9_\-+]+.[a-zA-Z0-9]+$'


def check_filename(filename: str) -> bool:
    """
    Check if the filename consists of alphanumeric characters, underscores, hyphens, and plus signs.
    """
    return re.match(filename_regex_str, filename) is not None


def clean_path_parameter(path_element: str) -> str:
    """
    Clean the path_element to prevent path traversal.
    """
    return path_element.replace('/', '').replace('..', '')
