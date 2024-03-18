# Copyright 2023 Camptocamp SA
# @author Alexandre Fayolle <alexandre.fayolle@camptocamp.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import os
import time

import responses

from .common import CommonWebService


class TestWebService(CommonWebService):
    @classmethod
    def _setup_records(cls):

        res = super()._setup_records()
        cls.url = "https://localhost.demo.odoo/"
        os.environ["SERVER_ENV_CONFIG"] = "\n".join(
            [
                "[webservice_backend.test_oauth2]",
                "auth_type = oauth2",
                "oauth2_clientid = some_client_id",
                "oauth2_client_secret = shh_secret",
                f"oauth2_token_url = {cls.url}oauth2/token",
                f"oauth2_audience = {cls.url}",
            ]
        )
        cls.webservice = cls.env["webservice.backend"].create(
            {
                "name": "WebService OAuth2",
                "tech_name": "test_oauth2",
                "auth_type": "oauth2",
                "protocol": "http",
                "url": cls.url,
                "content_type": "application/xml",
                "oauth2_clientid": "some_client_id",
                "oauth2_client_secret": "shh_secret",
                "oauth2_token_url": f"{cls.url}oauth2/token",
                "oauth2_audience": cls.url,
            }
        )
        return res

    def test_get_adapter_protocol(self):
        protocol = self.webservice._get_adapter_protocol()
        self.assertEqual(protocol, "http+oauth2")

    @responses.activate
    def test_fetch_token(self):
        duration = 3600
        expires_timestamp = time.time() + duration
        responses.add(
            responses.POST,
            f"{self.url}oauth2/token",
            json={
                "access_token": "cool_token",
                "expires_at": expires_timestamp,
                "expires_in": duration,
                "token_type": "Bearer",
            },
        )
        responses.add(responses.GET, f"{self.url}endpoint", body="OK")
        result = self.webservice.call("get", url=f"{self.url}endpoint")
        self.assertTrue("cool_token" in self.webservice.oauth2_token)
        self.assertEqual(result, b"OK")
