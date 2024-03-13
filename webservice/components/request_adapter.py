# Copyright 2020 Creu Blanca
# Copyright 2022 Camptocamp SA
# @author Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import time

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from odoo.addons.component.core import Component


class BaseRestRequestsAdapter(Component):
    _name = "base.requests"
    _webservice_protocol = "http"
    _inherit = "base.webservice.adapter"

    # TODO: url and url_params could come from work_ctx
    def _request(self, method, url=None, url_params=None, **kwargs):
        url = self._get_url(url=url, url_params=url_params)
        new_kwargs = kwargs.copy()
        new_kwargs.update(
            {
                "auth": self._get_auth(**kwargs),
                "headers": self._get_headers(**kwargs),
                "timeout": None,
            }
        )
        # pylint: disable=E8106
        request = requests.request(method, url, **new_kwargs)
        request.raise_for_status()
        return request.content

    def get(self, **kwargs):
        return self._request("get", **kwargs)

    def post(self, **kwargs):
        return self._request("post", **kwargs)

    def put(self, **kwargs):
        return self._request("put", **kwargs)

    def _get_auth(self, auth=False, **kwargs):
        if auth:
            return auth
        handler = getattr(self, "_get_auth_for_" + self.collection.auth_type, None)
        return handler(**kwargs) if handler else None

    def _get_auth_for_user_pwd(self, **kw):
        if self.collection.username and self.collection.password:
            return self.collection.username, self.collection.password
        return None

    def _get_headers(self, content_type=False, headers=False, **kwargs):
        headers = headers or {}
        result = {
            "Content-Type": content_type or self.collection.content_type,
        }
        handler = getattr(self, "_get_headers_for_" + self.collection.auth_type, None)
        if handler:
            headers.update(handler(**kwargs))
        result.update(headers)
        return result

    def _get_headers_for_api_key(self, **kw):
        return {self.collection.api_key_header: self.collection.api_key}

    def _get_url(self, url=None, url_params=None, **kwargs):
        if not url:
            url = self.collection.url
        elif not url.startswith(self.collection.url):
            if not url.startswith("http"):
                url = f"{self.collection.url.rstrip('/')}/{url.lstrip('/')}"
            else:
                # TODO: if url is given, we should validate the domain
                # to avoid abusing a webservice backend for different calls.
                pass

        url_params = url_params or kwargs
        return url.format(**url_params)


class OAuth2RestRequestsAdapter(Component):
    _name = "oauth2.requests"
    _webservice_protocol = "http+oauth2"
    _inherit = "base.requests"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        # cached value to avoid hitting the database each time we need the token
        self._token = {}

    def fetch_token(self):
        pass

    def _is_token_valid(self, token):
        """We consider that a token in valid if it has at least 10% of
        its valid duration. So if a token has a validity of 1h, we will
        renew it if we try to use it 6 minutes before its expiration date.
        """
        expires_at = token.get("expires_at", 0)
        expires_in = token.get("expires_in", 3600)  # default to 1h
        now = time.time()
        return now <= (expires_at - 0.1 * expires_in)

    @property
    def token(self):
        """Return a valid oauth2 token.

        The tokens are stored in the database, and we check if they are still
        valid, and renew them if needed.
        """
        if self._is_token_valid(self._token):
            return self._token
        backend = self.collection
        with backend.env.registry.cursor() as cr:
            if backend.env.context.get("test_mode"):
                token_str = backend.oauth2_token or "{}"
            else:
                cr.execute(
                    "SELECT oauth2_token FROM webservice_backend "
                    "WHERE id=%s "
                    "FOR NO KEY UPDATE",  # prevent concurrent token fetching
                    (backend.id,),
                )
                token_str = cr.fetchone()[0] or "{}"
            token = json.loads(token_str)
            if self._is_token_valid(token):
                self._token = token
                return token
            else:
                new_token = self._fetch_new_token(old_token=token)
                if backend.env.context.get("test_mode"):
                    # in test mode we don't want the context manager to
                    # commit the change -> use the normal object and let
                    # the rollback from the test case work
                    backend.oauth2_token = new_token
                else:
                    cr.execute(
                        "UPDATE webservice_backend "
                        "SET oauth2_token=%s "
                        "WHERE id=%s",
                        (json.dumps(new_token), backend.id),
                    )
                self._token = new_token
                return new_token

    def _fetch_new_token(self, old_token):
        # TODO: check if the old token has a refresh_token that can
        # be used (and use it in that case)
        oauth_params = self.collection.sudo().read(
            [
                "oauth2_clientid",
                "oauth2_client_secret",
                "oauth2_token_url",
                "oauth2_audience",
            ]
        )[0]
        client = BackendApplicationClient(client_id=oauth_params["oauth2_clientid"])
        with OAuth2Session(client=client) as session:
            token = session.fetch_token(
                token_url=oauth_params["oauth2_token_url"],
                cliend_id=oauth_params["oauth2_clientid"],
                client_secret=oauth_params["oauth2_client_secret"],
                audience=oauth_params.get("audience") or "",
            )
        return token

    def _request(self, method, url=None, url_params=None, **kwargs):
        url = self._get_url(url=url, url_params=url_params)
        new_kwargs = kwargs.copy()
        new_kwargs.update(
            {
                "headers": self._get_headers(**kwargs),
                "timeout": None,
            }
        )
        client = BackendApplicationClient(client_id=self.collection.oauth2_clientid)
        with OAuth2Session(client=client, token=self.token) as session:
            # pylint: disable=E8106
            request = session.request(method, url, **new_kwargs)
            request.raise_for_status()
            return request.content
