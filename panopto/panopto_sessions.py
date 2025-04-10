#!python3
from typing import Any, List
import aiofiles
import urllib.parse
import logging
import os

from panopto.panopto_client import DEFAULT_SERVER, PanoptoClient
from panopto.panopto_oauth2 import PanoptoOAuth2


class PanoptoSessions(PanoptoClient):
    def __init__(self,
                 oauth2: PanoptoOAuth2,
                 server: str = DEFAULT_SERVER,
                 ssl_verify: bool = True) -> None:
        super().__init__(oauth2=oauth2, server=server, ssl_verify=ssl_verify)
        self.base_url = 'https://{0}/Panopto/api/v1/sessions' \
            .format(self.server)
        self.auth_url = 'https://{0}/Panopto/api/v1/auth/legacyLogin' \
            .format(self.server)

    async def get_session(self,
                          session_id: str) -> dict[str, Any]:
        '''
        Call GET /api/v1/sessions/{id} API and return the response
        '''
        url = '{0}/{1}'.format(self.base_url, session_id)
        return await self.get_single(url)

    async def update_session_name(self,
                                  session_id: str,
                                  new_name: str) -> bool:
        '''
        Call PUT /api/v1/sessions/{id} API to update the name
        Return True if it succeeds, False if it fails.
        '''
        try:
            while True:
                url = 'https://{0}/Panopto/api/v1/sessions/{1}' \
                    .format(self.server, session_id)
                payload = {'Name': new_name}
                headers = {'content-type': 'application/json'}
                async with self.requests_session.put(
                        url=url,
                        json=payload,
                        headers=headers) as resp:
                    if self._inspect_response_is_retry_needed(resp):
                        continue
        except Exception as e:
            logging.error(f'Rename failed: {e}')
            raise e

    async def delete_session(self, session_id: str) -> None:
        '''
        Call DELETE /api/v1/sessions/{id} API to delete a session
        Return True if it succeeds, False if it fails.
        '''
        try:
            while True:
                url = 'https://{0}/Panopto/api/v1/sessions/{1}' \
                    .format(self.server, session_id)
                async with self.requests_session.delete(url=url) as resp:
                    if self._inspect_response_is_retry_needed(resp):
                        continue
        except Exception as e:
            logging.error('Deletion failed. {0}'.format(e))
            raise e

    async def search_sessions(self, query: str) -> List[dict[str, Any]]:
        '''
        Call GET /api/v1/sessions/search API and return the list of entries.
        '''
        url = '{0}/search?searchQuery={1}' \
            .format(self.base_url, urllib.parse.quote_plus(query))
        return await self.get_batch(url)

    async def get_session_headers(self, download_url: str) -> Any:
        async with self.requests_session.get(self.auth_url) as resp:
            if '.ASPXAUTH' in resp.cookies:
                auth_cookie = resp.cookies['.ASPXAUTH']
            else:
                raise PermissionError('Failed to get authentication cookie')

        auth = {'.ASPXAUTH': auth_cookie}
        async with self.requests_session.head(download_url,
                                              cookies=auth,
                                              allow_redirects=True) as resp:
            if resp.status == 403:
                raise PermissionError('403: Forbidden {0}'.format(resp.reason))
            return resp.headers

    async def download_session(self,
                               download_url: str,
                               destination: str,
                               local_size_match: bool = False) -> None:
        async with self.requests_session.get(self.auth_url) as resp:
            if '.ASPXAUTH' in resp.cookies:
                auth_cookie = resp.cookies['.ASPXAUTH']
            else:
                raise PermissionError('Failed to get authentication cookie')

        if local_size_match and os.path.exists(destination):
            logging.info("Checking if local file size matches server file size")  # noqa: E501
            headers = await self.get_session_headers(download_url)
            if 'Content-Length' in headers:
                server_size = int(headers['Content-Length'])
                local_size = os.path.getsize(destination)
                if local_size == server_size:
                    logging.info("File already downloaded (local size == Content-Length), skipping")  # noqa: E501
                    return
                else:
                    logging.info("File size does not match, downloading")

        logging.info(f"Downloading {download_url} to {destination}")
        if logging.root.isEnabledFor(logging.DEBUG):
            logging.debug("(In debug mode, skipping actually downloading)")
            return

        auth = {'.ASPXAUTH': auth_cookie}
        async with self.requests_session.get(download_url, cookies=auth) as r:
            if r.status == 403:
                raise PermissionError('403: Forbidden {0}'.format(resp.reason))

            destination = os.path.expanduser(destination)
            async with aiofiles.open(destination, mode='ab') as f:
                while True:
                    chunk = await r.content.read(1000)
                    if not chunk:
                        break
                    await f.write(chunk)
