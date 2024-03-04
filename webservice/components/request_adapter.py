# Copyright 2020 Creu Blanca
# Copyright 2022 Camptocamp SA
# @author Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from odoo.addons.component.core import Component


def build_session_oauth2(token_url, client_id, client_secret, audience=None):
    """helper function get an authenticated OAuth2Session"""
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    # TODO: handle token renewal
    oauth.fetch_token(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        audience=audience,
    )
    return oauth


class BaseRestRequestsAdapter(Component):
    _name = "base.requests"
    _webservice_protocol = "http"
    _inherit = "base.webservice.adapter"

    # TODO: url and url_params could come from work_ctx
    def _request(self, method, url=None, url_params=None, **kwargs):
        Session = self._get_session_class()
        url = self._get_url(url=url, url_params=url_params)
        new_kwargs = kwargs.copy()
        auth_info = self._get_auth(**kwargs)
        if auth_info is not None:
            session_kwargs = auth_info.get("session_auth", {})
            auth = auth_info.get("auth", None)
        else:
            session_kwargs = {}
            auth = None
        new_kwargs.update(
            {"headers": self._get_headers(**kwargs), "timeout": None, "auth": auth}
        )
        with Session(**session_kwargs) as session:
            # pylint: disable=E8106
            resp = session.request(method, url, **new_kwargs)
            resp.raise_for_status()
            return resp.content

    def get(self, **kwargs):
        return self._request("get", **kwargs)

    def post(self, **kwargs):
        return self._request("post", **kwargs)

    def put(self, **kwargs):
        return self._request("put", **kwargs)

    def _get_auth(self, auth=False, **kwargs):
        if auth:
            return {"auth": auth}
        handler = getattr(self, "_get_auth_for_" + self.collection.auth_type, None)
        return handler(**kwargs) if handler else None

    def _get_session_class(self):
        handler = getattr(
            self, "_get_session_class_for_" + self.collection.auth_type, None
        )
        if handler is None:
            return requests.Session
        else:
            return handler()

    def _get_session_class_for_oauth2(self):
        return build_session_oauth2

    def _get_auth_for_user_pwd(self, **kw):
        if self.collection.username and self.collection.password:
            return {"auth": (self.collection.username, self.collection.password)}
        return None

    def _get_auth_for_oauth2(self, **kwargs):
        return {
            "session_auth": {
                "client_id": self.collection.oauth2_clientid,
                "client_secret": self.collection.oauth2_client_secret,
                "token_url": self.collection.oauth2_token_url,
                "audience": self.collection.oauth2_audience,
            }
        }

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
                url = self.collection.url + url
            else:
                # TODO: if url is given, we should validate the domain
                # to avoid abusing a webservice backend for different calls.
                pass

        url_params = url_params or kwargs
        return url.format(**url_params)
