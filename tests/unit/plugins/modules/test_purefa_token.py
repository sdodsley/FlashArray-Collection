# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_token module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
import sys
from unittest.mock import Mock, MagicMock, patch

import pytest

# Mock external dependencies before importing module
sys.modules["grp"] = MagicMock()
sys.modules["pwd"] = MagicMock()
sys.modules["fcntl"] = MagicMock()
sys.modules["ansible"] = MagicMock()
sys.modules["ansible.module_utils"] = MagicMock()
sys.modules["ansible.module_utils.basic"] = MagicMock()
sys.modules["purestorage"] = MagicMock()
sys.modules["distro"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pypureclient"] = MagicMock()
sys.modules["pypureclient.flasharray"] = MagicMock()
sys.modules["ansible_collections"] = MagicMock()
sys.modules["ansible_collections.everpure"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray.plugins"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils"] = (
    MagicMock()
)
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.purefa"] = (
    MagicMock()
)
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.common"] = (
    MagicMock()
)
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers"
] = MagicMock()
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.error_handlers"
] = MagicMock()

# Create a mock version module with real LooseVersion
mock_version_module = MagicMock()
from packaging.version import Version as LooseVersion

mock_version_module.LooseVersion = LooseVersion
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.version"] = (
    mock_version_module
)

from plugins.modules.purefa_token import (
    get_session,
    get_token_array,
    main,
    token_exists,
    token_from,
)


def _admin(created, name="pureuser"):
    """One entry of GET admin?api_token=true as the REST 1.x array returns it"""
    return {"name": name, "api_token": {"created": created, "expires": None}}


def _module(**overrides):
    mock_module = Mock()
    mock_module.params = {
        "fa_url": "10.10.10.2",
        "username": "pureuser",
        "password": "secret",
        "state": "present",
        "recreate": False,
        "timeout": None,
        "disable_warnings": False,
    }
    mock_module.params.update(overrides)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


class TestGetSession:
    """Tests for get_session credential handling"""

    @patch("plugins.modules.purefa_token.HAS_PURESTORAGE", True)
    def test_env_url_without_credentials_fails_clearly(self):
        """PUREFA_URL alone used to leave `system` unbound (UnboundLocalError)"""
        mock_module = _module(fa_url=None, username=None, password=None)

        with patch.dict(os.environ, {"PUREFA_URL": "10.10.10.2"}, clear=True):
            with pytest.raises(SystemExit):
                get_session(mock_module)

        msg = mock_module.fail_json.call_args[1]["msg"]
        assert "PUREFA_USERNAME" in msg


class TestMain:
    """Tests for the create/recreate/delete decision and the changed flag"""

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_create_for_admin_without_token_is_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created=None)]
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )
        mock_get_array.assert_not_called()

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_missing_created_counts_as_absent(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created=None)]
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_existing_token_without_recreate_is_not_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        """This is the normal hardware outcome of state=present: the login
        in get_session (POST auth/apitoken) has already created the token
        of a fresh user, so the listing reports it and the module reads it
        back without a change. The token is still returned.
        """
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_not_called()
        session.delete_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="old-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_is_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(recreate=True)
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_without_token_is_not_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(state="absent")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created=None)]
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False, purefa_token=None)


class TestTimeout:
    """timeout is a REST 2 feature and must be gated on the REST 2 version"""

    @patch("plugins.modules.purefa_token.check_response")
    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_applied_on_current_rest(
        self,
        mock_ansible_module,
        mock_get_session,
        mock_get_array,
        mock_convert,
        mock_check_response,
    ):
        """ "2.2" in [REST 1 versions] was never true, so timeout was ignored"""
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 86400000
        array6 = Mock()
        array6.get_rest_version.return_value = "2.54"
        item = Mock()
        item.api_token.token = "timed-token"
        array6.post_admins_api_tokens.return_value = Mock(status_code=200, items=[item])
        mock_get_array.return_value = array6

        main()

        array6.delete_admins_api_tokens.assert_called_once_with(names=["pureuser"])
        array6.post_admins_api_tokens.assert_called_once_with(
            names=["pureuser"], timeout=86400000
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="timed-token"
        )

    @patch("plugins.modules.purefa_token.check_response")
    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_rest2_login_uses_the_token_only(
        self,
        mock_ansible_module,
        mock_get_session,
        mock_get_array,
        mock_convert,
        mock_check_response,
    ):
        """Hardware: get_array(module) with username/password still in the
        parameters made the REST 2 login fail ("Unable to list user for API
        token"); a login with the user's API token works even for a readonly
        user. get_array therefore sees fa_url, the token read back and
        disable_warnings, and nothing else; its fail_json is the module's.
        """
        mock_module = _module(timeout="1d", disable_warnings=True)
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 86400000
        array6 = Mock()
        array6.get_rest_version.return_value = "2.54"
        item = Mock()
        item.api_token.token = "timed-token"
        array6.post_admins_api_tokens.return_value = Mock(status_code=200, items=[item])
        mock_get_array.return_value = array6

        main()

        mock_get_array.assert_called_once()
        view = mock_get_array.call_args.args[0]
        assert view is not mock_module
        assert view.params == {
            "fa_url": "10.10.10.2",
            "api_token": "old-token",
            "disable_warnings": True,
        }
        assert "username" not in view.params
        assert "password" not in view.params
        assert view.fail_json is mock_module.fail_json
        # the module's own parameters were not rewritten
        assert "api_token" not in mock_module.params

    @patch("plugins.modules.purefa_token.check_response")
    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_with_timeout_logs_in_with_the_new_token(
        self,
        mock_ansible_module,
        mock_get_session,
        mock_get_array,
        mock_convert,
        mock_check_response,
    ):
        """The REST 2 login uses the token recreate just made, not the one
        it replaced, and the lifetime-bearing token is the one returned
        """
        mock_module = _module(timeout="1d", recreate=True)
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 86400000
        array6 = Mock()
        array6.get_rest_version.return_value = "2.54"
        item = Mock()
        item.api_token.token = "timed-token"
        array6.post_admins_api_tokens.return_value = Mock(status_code=200, items=[item])
        mock_get_array.return_value = array6

        main()

        session.get_api_token.assert_not_called()
        assert mock_get_array.call_args.args[0].params["api_token"] == "new-token"
        array6.delete_admins_api_tokens.assert_called_once_with(names=["pureuser"])
        array6.post_admins_api_tokens.assert_called_once_with(
            names=["pureuser"], timeout=86400000
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="timed-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_without_a_readable_token_fails_before_rest2(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {}
        mock_get_session.return_value = session

        with pytest.raises(SystemExit):
            main()

        mock_get_array.assert_not_called()
        assert "pureuser" in mock_module.fail_json.call_args.kwargs["msg"]
        mock_module.exit_json.assert_not_called()

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_warns_below_rest_2_2(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session
        array6 = Mock()
        array6.get_rest_version.return_value = "2.1"
        mock_get_array.return_value = array6

        main()

        array6.delete_admins_api_tokens.assert_not_called()
        array6.post_admins_api_tokens.assert_not_called()
        mock_module.warn.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="old-token"
        )


class TestGetTokenArray:
    """get_token_array hands get_array a token-only view of the module"""

    @patch("plugins.modules.purefa_token.get_array")
    def test_view_carries_url_token_and_warnings_only(self, mock_get_array):
        mock_module = _module(disable_warnings=True)

        result = get_token_array(mock_module, "the-token")

        assert result is mock_get_array.return_value
        view = mock_get_array.call_args.args[0]
        assert view.params == {
            "fa_url": "10.10.10.2",
            "api_token": "the-token",
            "disable_warnings": True,
        }
        assert view.fail_json is mock_module.fail_json
        assert view.warn is mock_module.warn

    @patch("plugins.modules.purefa_token.get_array")
    def test_env_url_is_left_to_get_array(self, mock_get_array):
        """fa_url may come from PUREFA_URL; get_array does that lookup"""
        mock_module = _module(fa_url=None)

        get_token_array(mock_module, "the-token")

        assert mock_get_array.call_args.args[0].params["fa_url"] is None


class TestTokenFrom:
    """token_from reads the api_token out of a REST 1 token response"""

    def test_dict(self):
        assert token_from({"api_token": "t", "name": "pureuser"}) == "t"

    def test_one_item_list(self):
        assert token_from([{"api_token": "t"}]) == "t"

    def test_missing(self):
        assert token_from({}) is None
        assert token_from([]) is None
        assert token_from(None) is None
        assert token_from({"name": "pureuser"}) is None


class TestTokenExists:
    """Existence comes from GET admin?api_token=true, never from get_api_token,
    which creates a token for a user who has none. When the listing cannot
    answer, the token is assumed to exist: the login that opened the session
    created it, and the assumption can only lead to a read or a delete.
    """

    def test_created_null_means_no_token(self):
        array = Mock()
        array.list_admins.return_value = [_admin(created=None)]

        assert token_exists(array, "pureuser") is False
        array.list_admins.assert_called_once_with(api_token=True)
        array.get_api_token.assert_not_called()

    def test_created_set_means_token(self):
        array = Mock()
        array.list_admins.return_value = [
            _admin(created="2026-10-20T10:00:00Z", name="other"),
            _admin(created="2026-10-20T10:00:00Z"),
        ]

        assert token_exists(array, "pureuser") is True

    def test_only_the_named_admin_counts(self):
        array = Mock()
        array.list_admins.return_value = [
            _admin(created="2026-10-20T10:00:00Z", name="other"),
            _admin(created=None),
        ]

        assert token_exists(array, "pureuser") is False

    def test_admin_missing_from_list_is_assumed_to_have_a_token(self):
        """The session user exists and logged in, which created the token;
        a listing that does not show them is not evidence of no token
        """
        array = Mock()
        array.list_admins.return_value = [
            _admin(created="2026-10-20T10:00:00Z", name="other")
        ]

        assert token_exists(array, "pureuser") is True
        array.get_api_token.assert_not_called()

    def test_unreadable_listing_is_assumed_to_have_a_token(self):
        array = Mock()
        array.list_admins.side_effect = Exception("insufficient privileges")

        assert token_exists(array, "pureuser") is True
        array.get_api_token.assert_not_called()

    def test_empty_listing_is_assumed_to_have_a_token(self):
        array = Mock()
        array.list_admins.return_value = []

        assert token_exists(array, "pureuser") is True

    def test_flat_created_field_is_accepted(self):
        array = Mock()
        array.list_admins.return_value = [
            {"name": "pureuser", "created": "2026-10-20T10:00:00Z", "expires": None}
        ]

        assert token_exists(array, "pureuser") is True

    def test_single_dict_response_is_wrapped(self):
        array = Mock()
        array.list_admins.return_value = _admin(created="2026-10-20T10:00:00Z")

        assert token_exists(array, "pureuser") is True

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_admin_listed_without_token_is_created_explicitly(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        """When the listing does report a user without a token, the token is
        created with create_api_token and never read with get_api_token,
        which would create it implicitly and hide the change. On hardware
        this path is not normally reached (the login creates the token).
        """
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created=None)]
        session.get_api_token.return_value = {"api_token": "implicitly-created"}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.get_api_token.assert_not_called()
        session.create_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_existing_token_is_read_back_without_creating(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session

        main()

        session.get_api_token.assert_called_once_with(admin="pureuser")
        session.create_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="old-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_with_token_deletes(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(state="absent")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.delete_api_token.return_value = {"api_token": None}
        mock_get_session.return_value = session

        main()

        session.get_api_token.assert_not_called()
        session.delete_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(changed=True, purefa_token=None)


class TestLoginCreatedToken:
    """The purestorage client obtains its session with POST auth/apitoken,
    which creates the user's token when none exists. The module cannot see
    that creation, so present reads back without a change, recreate forces
    a new token and reports it, and absent deletes and reports it.
    """

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_present_with_unreadable_listing_reads_back_without_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.side_effect = Exception("insufficient privileges")
        session.get_api_token.return_value = {"api_token": "login-created"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_not_called()
        session.get_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="login-created"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_with_unreadable_listing_is_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(recreate=True)
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.side_effect = Exception("insufficient privileges")
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_called_once_with(admin="pureuser")
        session.create_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_with_unreadable_listing_deletes(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(state="absent")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.side_effect = Exception("insufficient privileges")
        session.delete_api_token.return_value = {"api_token": None}
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(changed=True, purefa_token=None)
