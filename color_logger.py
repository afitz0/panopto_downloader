import logging
from typing import Final


class ColorFormatter(logging.Formatter):
    """
    Formatter adding colors to console output.
    
    Shamelessly copied https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
    """

    GREY: Final = "38"
    RED: Final = "31"
    GREEN: Final = "32"
    YELLOW: Final = "33"
    BOLD: Final = ";1"
    ESCAPE: Final = "\x1b["
    RESET: Final = "0m"
    INTENSITY: Final = ";20m"

    BASE_FORMAT: Final = "%(asctime)s - %(levelname)s"

    @classmethod
    def get_formats(cls) -> dict[int, str]:
        """Get a dictionary of formats with proper ANSI codes for each logging level."""
        return {
            level: "".join(
                (cls.ESCAPE, color, cls.INTENSITY, cls.BASE_FORMAT, cls.ESCAPE, cls.RESET, ' - %(message)s')
            )
            for level, color in (
                (logging.DEBUG, cls.GREY),
                (logging.INFO, cls.GREEN),
                (logging.WARNING, cls.YELLOW),
                (logging.ERROR, cls.RED),
                (logging.CRITICAL, cls.RED + cls.BOLD),
            )
        }

    def format(self, record: logging.LogRecord) -> str:
        """Overwrite the parent 'format' method to format the specified record as text with
        appropriate color coding."""
        log_fmt = self.get_formats().get(record.levelno, self.BASE_FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
