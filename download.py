#!/usr/bin/env python3
#  type: ignore

import asyncio
import logging
from color_logger import ColorFormatter
from panopto.panopto_downloader import PanoptoDownloader

DOWNLOAD_DESTINATION = '../uw_cse/downloads'
CREDS_FILE = '~/.panopto_tokens'
SERVER = 'uw.hosted.panopto.com'
SKIP_FOLDERS = ['Panopto Workshop - 9/15/2014']


async def main():
    init_logger()

    logging.info("Starting Panopto downloader.")
    downloader = PanoptoDownloader(credentials_file=CREDS_FILE,
                                   panopto_server=SERVER,
                                   download_destination=DOWNLOAD_DESTINATION,
                                   exclude_folders=SKIP_FOLDERS)

    try:
        await downloader.download_all_from_root()
    except asyncio.exceptions.CancelledError:
        logging.warning("Download interrupted by user.")
    finally:
        logging.debug("Closing panopto downloader client.")
        await downloader.close()


def init_logger(level: int = logging.INFO) -> None:
    logger = logging.getLogger()
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)


if __name__ == "__main__":
    asyncio.run(main())
