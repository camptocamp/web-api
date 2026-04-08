# Copyright 2026 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import contextlib

from odoo import Command
from odoo.tools import DotDict

from odoo.addons.base.tests.common import TransactionCaseWithUserDemo
from odoo.addons.http_routing.tests.common import MockRequest


def _setup_demo_api_keys(env, demo_user):
    """Create demo API keys for tests."""
    api_key_model = env["auth.api.key"]

    api_key_1 = api_key_model.create(
        {
            "name": "Endpoint API key demo",
            "key": "cZ6dF2UQwNcm",
            "user_id": demo_user.id,
        }
    )
    api_key_2 = api_key_model.create(
        {
            "name": "Endpoint API key demo 2",
            "key": "kV47QyOTC5mS",
            "user_id": demo_user.id,
        }
    )
    return api_key_1, api_key_2


def _setup_demo_api_key_group(env, api_key_1):
    """Create demo API key group for tests."""
    return env["auth.api.key.group"].create(
        {
            "name": "Demo Group 1",
            "code": "demo_group1",
            "auth_api_key_ids": [Command.set(api_key_1.ids)],
        }
    )


def _setup_demo_endpoint(env, api_key_group):
    """Create demo endpoint for tests."""
    return env["endpoint.endpoint"].create(
        {
            "name": "Demo Endpoint - auth api key",
            "route": "/demo/api/key",
            "request_method": "GET",
            "auth_type": "api_key",
            "auth_api_key_group_ids": [Command.set(api_key_group.ids)],
            "exec_mode": "code",
            "code_snippet": 'result = {"response": Response("ok")}',
        }
    )


class CommonEndpointAuthAPIKey(TransactionCaseWithUserDemo):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_env()
        cls._setup_records()

    @classmethod
    def _setup_env(cls):
        cls.env = cls.env(context=cls._setup_context())

    @classmethod
    def _setup_context(cls):
        return dict(
            cls.env.context,
            tracking_disable=True,
        )

    @classmethod
    def _setup_records(cls):
        cls.api_key, cls.api_key2 = _setup_demo_api_keys(
            cls.env,
            cls.user_demo,
        )
        cls.key_group = _setup_demo_api_key_group(
            cls.env,
            cls.api_key,
        )
        cls.endpoint = _setup_demo_endpoint(
            cls.env,
            cls.key_group,
        )

    @contextlib.contextmanager
    def _get_mocked_request(
        self, httprequest=None, extra_headers=None, request_attrs=None
    ):
        with MockRequest(self.env) as mocked_request:
            mocked_request.httprequest = (
                DotDict(httprequest) if httprequest else mocked_request.httprequest
            )
            headers = {}
            headers.update(extra_headers or {})
            mocked_request.httprequest.headers = headers
            request_attrs = request_attrs or {}
            for k, v in request_attrs.items():
                setattr(mocked_request, k, v)
            mocked_request.make_response = lambda data, **kw: data
            yield mocked_request
