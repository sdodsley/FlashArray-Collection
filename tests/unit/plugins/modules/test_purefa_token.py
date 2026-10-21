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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_create_for_admin_without_token_is_a_change(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_missing_created_counts_as_absent(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_existing_token_without_recreate_is_not_a_change(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_is_a_change(self, mock_ansible_module, mock_get_session):
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_without_token_is_not_a_change(
        self, mock_ansible_module, mock_get_session
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
    """The lifetime goes into the REST 1.x create call (POST
    admin/<user>/apitoken with {"timeout": <ms>}, Purity 6.x) through the
    purestorage client already in hand; the REST 2 token endpoints are not
    used because deleting the session user's token there invalidated the
    session ("Invalid session"). A timeout replaces the token like recreate.
    """

    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_recreates_the_token_with_a_lifetime(
        self, mock_ansible_module, mock_get_session, mock_convert
    ):
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.get_api_token.return_value = {"api_token": "old-token"}
        session.create_api_token.return_value = {"api_token": "timed-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 86400000

        main()

        mock_convert.assert_called_once_with("1d")
        session.delete_api_token.assert_called_once_with(admin="pureuser")
        session.create_api_token.assert_called_once_with(
            admin="pureuser", timeout=86400000
        )
        session.get_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="timed-token"
        )

    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_for_admin_without_token_creates_once(
        self, mock_ansible_module, mock_get_session, mock_convert
    ):
        """No delete when there is nothing to delete; the lifetime still goes
        into the one create call
        """
        mock_module = _module(timeout="2w")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created=None)]
        session.create_api_token.return_value = {"api_token": "timed-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 1209600000

        main()

        session.delete_api_token.assert_not_called()
        session.create_api_token.assert_called_once_with(
            admin="pureuser", timeout=1209600000
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="timed-token"
        )

    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_invalid_timeout_fails_before_touching_the_token(
        self, mock_ansible_module, mock_get_session, mock_convert
    ):
        """convert_time_to_millisecs answers 0 for a bad unit or number; the
        old code silently ignored that and left the token alone
        """
        mock_module = _module(timeout="1x")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        mock_get_session.return_value = session
        mock_convert.return_value = 0

        with pytest.raises(SystemExit):
            main()

        assert "1x" in mock_module.fail_json.call_args.kwargs["msg"]
        session.delete_api_token.assert_not_called()
        session.create_api_token.assert_not_called()
        mock_module.exit_json.assert_not_called()

    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_is_ignored_for_absent(
        self, mock_ansible_module, mock_get_session, mock_convert
    ):
        mock_module = _module(state="absent", timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.list_admins.return_value = [_admin(created="2026-10-20T10:00:00Z")]
        session.delete_api_token.return_value = {"api_token": None}
        mock_get_session.return_value = session

        main()

        mock_convert.assert_not_called()
        session.delete_api_token.assert_called_once_with(admin="pureuser")
        session.create_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, purefa_token=None)


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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_admin_listed_without_token_is_created_explicitly(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_existing_token_is_read_back_without_creating(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_with_token_deletes(self, mock_ansible_module, mock_get_session):
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_present_with_unreadable_listing_reads_back_without_change(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_with_unreadable_listing_is_a_change(
        self, mock_ansible_module, mock_get_session
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

    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_with_unreadable_listing_deletes(
        self, mock_ansible_module, mock_get_session
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
