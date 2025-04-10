import time
import logging
from typing import List, Any

from aiolimiter import AsyncLimiter
from aiohttp import ClientSession, ClientResponse
from panopto.panopto_oauth2 import PanoptoOAuth2

DEFAULT_SERVER = 'uw.hosted.panopto.com'

# UW Panopto's API throttles at 100 per minute, so we set default to 80
# for safety. Override at your own peril.
REQUESTS_PER_MINUTE = 80


class ThrottledClientSession(ClientSession):
    def __init__(self,
                 requests_per_minute: int = REQUESTS_PER_MINUTE,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.limiter = AsyncLimiter(requests_per_minute)

    async def _request(self, *args, **kwargs) -> ClientResponse:
        """Throttled _request()"""
        await self.limiter.acquire()
        return await super()._request(*args, **kwargs)


class PanoptoClient:
    def __init__(self,
                 oauth2: PanoptoOAuth2,
                 server: str = DEFAULT_SERVER,
                 rate_limit_per_minute: int = REQUESTS_PER_MINUTE,
                 ssl_verify: bool = True) -> None:
        '''
        Constructor of sessions API handler instance.
        This goes through authorization step of the target server.
        '''
        self.server: str = server
        self.ssl_verify: bool = ssl_verify
        self.oauth2: PanoptoOAuth2 = oauth2

        self.requests_session: ThrottledClientSession = \
            ThrottledClientSession(requests_per_minute=rate_limit_per_minute)
        self.requests_session.verify = self.ssl_verify

        self._setup_or_refresh_access_token()

    async def get_batch(self, url: str) -> List[dict[str, Any]]:
        result: List[dict[str, Any]] = []
        page_number = 0
        while True:
            logging.debug('Getting page {0} of {1}'.format(page_number, url))
            request_url = '{0}&pageNumber={1}'.format(url, page_number)

            async with self.requests_session.get(url=request_url) as resp:
                if self._inspect_response_is_retry_needed(resp):
                    continue
                data = await resp.json()

            entries = data['Results']
            logging.debug('Got {0} entries'.format(len(entries)))
            if len(entries) > 0:
                logging.debug('First entry: {0}'.format(entries[0]))
            if len(entries) == 0:
                break
            for entry in entries:
                result.append(entry)
            page_number += 1

        return result

    async def get_single(self, url: str) -> dict[str, Any]:
        while True:
            async with self.requests_session.get(url=url) as resp:
                if self._inspect_response_is_retry_needed(resp):
                    continue
                data: dict[str, Any] = await resp.json()
                break
        return data

    def _setup_or_refresh_access_token(self) -> None:
        '''
        This method invokes OAuth2 Authorization Code Grant authorization flow.
        It goes through browser UI for the first time.
        It refreshes the access token after that and no user interaction is
        requested. This is called at the initialization of the class, as well
        as when 401 (Unauthorized) is returned.
        '''
        access_token: str = self.oauth2.refresh_access_token()
        self.requests_session.headers.update(
            {'Authorization': 'Bearer ' + access_token})

    def _inspect_response_is_retry_needed(self,
                                          response: ClientResponse) -> bool:
        '''
        Inspect the response of a requests' call.
        True indicates the retry needed, False indicates success. Otherwise an
        exception is thrown.
        Reference: https://stackoverflow.com/a/24519419

        This method detects 401 (Unauthorized), refresh the access token, and
        returns as "is retry needed". This method also detects 429 (Too many
        request) which means API throttling by the server. Wait a sec and
        return as "is retry needed". Production code should handle other
        failure cases and errors as appropriate.
        '''
        if response.status // 100 == 2:
            # Success on 2xx response.
            return False

        if response.status == 401:
            logging.info('Unauthorized. Attempting to refresh access token.')
            self._setup_or_refresh_access_token()
            return True

        if response.status == 429:
            logging.info('Too many requests. Waiting one sec, and retry.')
            time.sleep(1)
            return True

        # Throw unhandled cases.
        response.raise_for_status()
        return False

    async def close(self) -> None:
        '''
        Close the requests session.
        '''
        await self.requests_session.close()
