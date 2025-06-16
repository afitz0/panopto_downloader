import os
import logging

from pathlib import Path
from typing import Any
from pathvalidate import sanitize_filename

from panopto.panopto_folders import PanoptoFolders
from panopto.panopto_sessions import PanoptoSessions
from panopto.panopto_oauth2 import PanoptoOAuth2

DEFAULT_SERVER = 'uw.hosted.panopto.com'
DOWNLOAD_DIR = '~/Downloads/uw_panopto'


class PanoptoDownloader:
    def __init__(self,
                 credentials_file: str,
                 panopto_server: str = DEFAULT_SERVER,
                 download_destination: str = DOWNLOAD_DIR,
                 exclude_folders: list[str] = []) -> None:
        self.download_path = os.path.expanduser(download_destination)
        Path(self.download_path).mkdir(exist_ok=True)

        self.exclude_folders = exclude_folders

        self.panopto_client = PanoptoOAuth2(
            panopto_server,
            client_secrets_file=credentials_file)

        self.panopto_folders = PanoptoFolders(oauth2=self.panopto_client,
                                              server=panopto_server,
                                              ssl_verify=True)
        self.panopto_sessions = PanoptoSessions(oauth2=self.panopto_client,
                                                server=panopto_server,
                                                ssl_verify=True)

    async def get_root_folders(self) -> list[dict[str, Any]]:
        logging.info("Getting root folders for authenticated user.")

        results = await self.panopto_folders.search_folders('*')
        self.root_folders = []
        for f in results:
            if f['ParentFolder'] is None:
                self.root_folders.append(f)

        logging.debug(f"Root folders: {self.root_folders}")
        return self.root_folders

    async def download_all_from_root(self) -> None:
        if not hasattr(self, 'root_folders') or self.root_folders is None:
            await self.get_root_folders()

        for folder in self.root_folders:
            await self.download_sessions_in_folder(folder)

    async def download_sessions_in_folder(self,
                                          folder: dict[str, str]) -> None:
        '''
        Recursively downloads all known video files from the given folder and
        its children folders. A directory tree will be created rooted in
        destination_dir starting with this folder's name and then matching the
        Panopto structure from there.

        Panopto folder names containing slashes will have those slashes
        replaced with dashes in the local directory structure.
        '''
        if folder['Name'] in self.exclude_folders:
            logging.debug(f"Skipping excluded folder '{folder['Name']}'")
            return

        logging.info(f"Downloading all sessions in folder '{folder['Name']}'.")

        folder['Name'] = sanitize_filename(folder['Name'])
        path = os.path.join(self.download_path, folder['Name'])
        Path(path).mkdir(exist_ok=True)

        session_list = await self.panopto_folders.get_sessions(folder['Id'])
        session_count = 0
        for session in session_list:
            session_count += 1
            s = await self.panopto_sessions.get_session(session['Id'])
            download_url = s['Urls']['DownloadUrl']

            logging.info(f"Downloading session: {s['Name']} ({session_count} of {len(session_list)})")  # noqa: E501
            logging.debug(f"Session's download URL: {download_url}")

            session_name = sanitize_filename(s['Name']) + '.mp4'
            full_path = os.path.join(path, session_name)
            try:
                await self.panopto_sessions.download_session(download_url,
                                                             full_path,
                                                             local_size_match=True)
            except PermissionError as e:
                logging.error(f"Permission error: {e}")
                continue

        sub_folders = await self.panopto_folders.get_children(folder['Id'])
        for folder in sub_folders:
            await self.download_sessions_in_folder(folder)
