#!python3
from typing import List, Any
import urllib.parse
import logging

from panopto.panopto_client import DEFAULT_SERVER, PanoptoClient
from panopto.panopto_oauth2 import PanoptoOAuth2


class PanoptoFolders(PanoptoClient):
    def __init__(self,
                 oauth2: PanoptoOAuth2,
                 server: str = DEFAULT_SERVER,
                 ssl_verify: bool = True) -> None:
        super().__init__(oauth2=oauth2, server=server, ssl_verify=ssl_verify)
        self.base_url = 'https://{0}/Panopto/api/v1/folders' \
            .format(self.server)

    async def get_children(self, folder_id: str) -> List[dict[str, Any]]:
        '''
        Call GET /api/v1/folders/{id}/children API and return the list of
        entries. This code has hard coded sort order of Name / Asc.
        '''
        url = '{0}/{1}/children?sortField=Name&sortOrder=Asc' \
            .format(self.base_url, folder_id)
        return await self.get_batch(url)

    async def get_folder(self, folder_id: str) -> dict[str, Any]:
        '''
        Call GET /api/v1/folders/{id} API and return the response
        '''
        url = '{0}/{1}'.format(
            self.base_url, folder_id)
        return await self.get_single(url)

    async def update_folder_name(self,
                                 folder_id: str,
                                 new_name: str) -> None:
        '''
        Call PUT /api/v1/folders/{id} API to update the name
        Return True if it succeeds, False if it fails.
        '''
        try:
            while True:
                url = self.base_url + '/' + folder_id
                payload = {'Name': new_name}
                headers = {'content-type': 'application/json'}
                async with self.requests_session.put(
                        url=url, json=payload, headers=headers) as resp:
                    if self._inspect_response_is_retry_needed(resp):
                        continue
        except Exception as e:
            logging.error('Rename failed. {0}'.format(e))
            raise e

    async def delete_folder(self, folder_id: str) -> None:
        '''
        Call DELETE /api/v1/folders/{id} API to delete a folder
        Return True if it succeeds, False if it fails.
        '''
        try:
            while True:
                url = self.base_url + '/' + folder_id
                async with self.requests_session.delete(url=url) as resp:
                    if self._inspect_response_is_retry_needed(resp):
                        continue
        except Exception as e:
            logging.error('Deletion failed. {0}'.format(e))
            raise e

    async def search_folders(self, query: str) -> List[dict[str, Any]]:
        '''
        Call GET /api/v1/folders/search API and return the list of entries.
        '''
        url = '{0}/search?searchQuery={1}' \
            .format(self.base_url, urllib.parse.quote_plus(query))
        logging.debug(f'Requesting folder search results via: {url}')
        return await self.get_batch(url)

    async def get_creator_folders(self) -> List[dict[str, Any]]:
        '''
        Call GET /api/v1/folders/creator API and return the list of entries.
        '''
        url = '{0}/creator?sortField=Name'.format(self.base_url)
        logging.debug(f'Requesting folders where authenticated user is "creator" via: {url}')  # noqa: E501
        return await self.get_batch(url)

    async def get_sessions(self, folder_id: str) -> List[dict[str, Any]]:
        '''
        Call GET /api/v1/folders/{id}/sessions API and return the list
        of entries. This code has hard coded sort order of CreatedDate / Desc.
        '''
        url = '{0}/{1}/sessions?sortField=CreatedDate&sortOrder=Desc' \
            .format(self.base_url, folder_id)
        return await self.get_batch(url)
