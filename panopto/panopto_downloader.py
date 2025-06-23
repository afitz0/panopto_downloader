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
        self.root_folders: list[dict[Any, Any]] = []
        for f in results:
            if f['ParentFolder'] is None:
                self.root_folders.append(f)

        logging.debug(f"Root folders: {self.root_folders}")
        return self.root_folders

    async def download_all_from_root(self) -> None:
        if not hasattr(self, 'root_folders'):
            await self.get_root_folders()

        for folder in self.root_folders:
            await self.download_sessions_in_folder(folder, self.download_path)
            
    async def print_folder_structure(self) -> None:
        '''
        Prints the folder structure of the authenticated user's Panopto account.
        This is useful for debugging and understanding the hierarchy of folders.
        '''
        if not hasattr(self, 'root_folders'):
            await self.get_root_folders()

        for folder in self.root_folders:
            logging.info(f"Folder: {folder['Name']} (ID: {folder['Id']})")
            await self.print_subfolders(folder, 1)
            
    async def print_subfolders(self, folder: dict[str, str], level: int) -> None:
        '''
        Recursively prints the subfolders of a given folder.
        This is used by print_folder_structure to display the hierarchy.
        '''
        sub_folders = await self.panopto_folders.get_children(folder['Id'])
        for child in sub_folders:
            logging.info(f"{' ' * (level * 2)}- {child['Name']} (ID: {child['Id']})")
            await self.print_subfolders(child, level + 1)

    async def download_sessions_in_folder(self,
                                          folder: dict[str, str],
                                          root_path: str) -> None:
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

        folder['Name'] = sanitize_filename(folder['Name'])
        path = os.path.join(root_path, folder['Name'])
        Path(path).mkdir(exist_ok=True)

        logging.info("Downloading all sessions in folder " +
                     f"'{folder['Name']}' to '{path}'.")

        session_list = await self.panopto_folders.get_sessions(folder['Id'])
        session_count = 0
        for session in session_list:
            session_count += 1
            s = await self.panopto_sessions.get_session(session['Id'])
            download_url = s['Urls']['DownloadUrl']

            logging.info(f"Downloading session: {s['Name']} " +
                         f"({session_count} of {len(session_list)}).")
            logging.debug(f"Session's download URL: {download_url}")

            session_name = sanitize_filename(s['Name']) + '.mp4'
            full_path = os.path.join(path, session_name)
            try:
                await self.panopto_sessions.download_session(
                    download_url,
                    full_path,
                    local_size_match=True
                )
            except PermissionError as e:
                logging.error(f"Permission error: {e}")
                continue

        sub_folders = await self.panopto_folders.get_children(folder['Id'])
        for child in sub_folders:
            await self.download_sessions_in_folder(child, path)

    async def close(self) -> None:
        """Close the Panopto client connection."""
        if self.panopto_client:
            await self.panopto_folders.close()
            await self.panopto_sessions.close()
            logging.debug("Panopto client connection closed.")
        else:
            logging.warning("No Panopto client to close.")
