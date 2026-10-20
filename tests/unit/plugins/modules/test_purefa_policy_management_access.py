# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_policy_management_access module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import Mock, patch, MagicMock

# Mock external dependencies before importing module
sys.modules["grp"] = MagicMock()
sys.modules["pwd"] = MagicMock()
sys.modules["fcntl"] = MagicMock()
sys.modules["ansible"] = MagicMock()
sys.modules["ansible.module_utils"] = MagicMock()
sys.modules["ansible.module_utils.basic"] = MagicMock()
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

from plugins.modules.purefa_policy_management_access import (
    get_policy,
    create_policy,
    update_policy,
    delete_policy,
    main,
)

MODULE_PATH = "plugins.modules.purefa_policy_management_access"


def _rule_obj(role, scope, resource_type):
    """Build a mock existing-policy rule object with .role/.scope attributes."""
    rule = Mock()
    rule.role = Mock()
    rule.role.name = role
    rule.scope = Mock()
    rule.scope.name = scope
    rule.scope.resource_type = resource_type
    return rule


class TestGetPolicy:
    """Tests for get_policy"""

    @patch("plugins.modules.purefa_policy_management_access.get_with_context")
    def test_get_policy_exists(self, mock_get):
        mock_module = Mock()
        mock_module.params = {"name": "mypolicy", "context": ""}
        policy = Mock()
        mock_get.return_value = Mock(status_code=200, items=[policy])

        assert get_policy(mock_module, Mock()) is policy

    @patch("plugins.modules.purefa_policy_management_access.get_with_context")
    def test_get_policy_missing(self, mock_get):
        mock_module = Mock()
        mock_module.params = {"name": "mypolicy", "context": ""}
        mock_get.return_value = Mock(status_code=400, items=[])

        assert get_policy(mock_module, Mock()) is None


class TestCreatePolicy:
    """Tests for create_policy"""

    def test_create_policy_check_mode(self):
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "mypolicy",
            "context": "",
            "enabled": True,
            "aggregation_strategy": "least-common-permissions",
            "rules": [
                {"role": "storage", "scope": "myrealm", "resource_type": "realms"}
            ],
        }
        mock_array = Mock()

        create_policy(mock_module, mock_array)

        mock_array.post_policies_management_access.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_policy_management_access.check_response")
    @patch("plugins.modules.purefa_policy_management_access.PolicyManagementAccessPost")
    @patch("plugins.modules.purefa_policy_management_access.post_with_context")
    def test_create_policy_success(self, mock_post, mock_post_model, mock_check):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "mypolicy",
            "context": "",
            "enabled": True,
            "aggregation_strategy": "least-common-permissions",
            "rules": [
                {"role": "storage", "scope": "myrealm", "resource_type": "realms"}
            ],
        }
        mock_post.return_value = Mock(status_code=200)

        create_policy(mock_module, Mock())

        mock_post.assert_called_once()
        model_kwargs = mock_post_model.call_args.kwargs
        assert model_kwargs["aggregation_strategy"] == "least-common-permissions"
        assert len(model_kwargs["rules"]) == 1
        mock_module.exit_json.assert_called_once_with(changed=True)


class TestUpdatePolicy:
    """Tests for update_policy"""

    def test_update_policy_no_change(self):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "mypolicy",
            "context": "",
            "enabled": True,
            "aggregation_strategy": "least-common-permissions",
            "rename": None,
            "rules": [
                {"role": "storage", "scope": "myrealm", "resource_type": "realms"}
            ],
        }
        policy = Mock()
        policy.enabled = True
        policy.aggregation_strategy = "least-common-permissions"
        policy.rules = [_rule_obj("storage", "myrealm", "realms")]

        update_policy(mock_module, Mock(), policy)

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_policy_management_access.check_response")
    @patch(
        "plugins.modules.purefa_policy_management_access.PolicyManagementAccessPatch"
    )
    @patch("plugins.modules.purefa_policy_management_access.patch_with_context")
    def test_update_policy_enabled_change(
        self, mock_patch, mock_patch_model, mock_check
    ):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "mypolicy",
            "context": "",
            "enabled": False,
            "aggregation_strategy": "least-common-permissions",
            "rename": None,
            "rules": None,
        }
        policy = Mock()
        policy.enabled = True
        policy.aggregation_strategy = "least-common-permissions"
        policy.rules = []
        mock_patch.return_value = Mock(status_code=200)

        update_policy(mock_module, Mock(), policy)

        mock_patch.assert_called_once()
        assert mock_patch_model.call_args.kwargs["enabled"] is False
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_policy_management_access.check_response")
    @patch(
        "plugins.modules.purefa_policy_management_access.PolicyManagementAccessPatch"
    )
    @patch("plugins.modules.purefa_policy_management_access.patch_with_context")
    def test_update_policy_rules_change(self, mock_patch, mock_patch_model, mock_check):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "mypolicy",
            "context": "",
            "enabled": True,
            "aggregation_strategy": "least-common-permissions",
            "rename": None,
            "rules": [
                {"role": "storage", "scope": "newrealm", "resource_type": "realms"}
            ],
        }
        policy = Mock()
        policy.enabled = True
        policy.aggregation_strategy = "least-common-permissions"
        policy.rules = [_rule_obj("storage", "oldrealm", "realms")]
        mock_patch.return_value = Mock(status_code=200)

        update_policy(mock_module, Mock(), policy)

        mock_patch.assert_called_once()
        assert "rules" in mock_patch_model.call_args.kwargs
        mock_module.exit_json.assert_called_once_with(changed=True)


class TestDeletePolicy:
    """Tests for delete_policy"""

    def test_delete_policy_check_mode(self):
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {"name": "mypolicy", "context": ""}
        mock_array = Mock()

        delete_policy(mock_module, mock_array)

        mock_array.delete_policies_management_access.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_policy_management_access.check_response")
    @patch("plugins.modules.purefa_policy_management_access.delete_with_context")
    def test_delete_policy_success(self, mock_delete, mock_check):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "mypolicy", "context": ""}
        mock_delete.return_value = Mock(status_code=200)

        delete_policy(mock_module, Mock())

        mock_delete.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)


def _params(**overrides):
    """Params as the module sees them when only name is given"""
    params = {
        "name": "mypolicy",
        "state": "present",
        "context": "",
        "enabled": None,
        "aggregation_strategy": None,
        "rename": None,
        "rules": None,
    }
    params.update(overrides)
    return params


class TestOmittedSettingsAreLeftAlone:
    """enabled and aggregation_strategy have no default on an update"""

    @patch(f"{MODULE_PATH}.check_response")
    @patch(f"{MODULE_PATH}.PolicyManagementAccessPatch")
    @patch(f"{MODULE_PATH}.patch_with_context")
    def test_rename_only_does_not_reenable_or_reset_strategy(
        self, mock_patch, mock_patch_model, mock_check
    ):
        """A rename-only task re-enabled a disabled policy and reset its
        strategy because the documented defaults were applied on update
        """
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(rename="newname")
        policy = Mock()
        policy.enabled = False
        policy.aggregation_strategy = "least-common-permissions"
        policy.rules = []
        mock_patch.return_value = Mock(status_code=200)

        update_policy(mock_module, Mock(), policy)

        mock_patch.assert_called_once()
        mock_patch_model.assert_called_once_with(name="newname")
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_nothing_given_is_no_change(self):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params()
        policy = Mock()
        policy.enabled = False
        policy.aggregation_strategy = "least-common-permissions"
        policy.rules = []

        update_policy(mock_module, Mock(), policy)

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch(f"{MODULE_PATH}.check_response")
    @patch(f"{MODULE_PATH}.PolicyManagementAccessPost")
    @patch(f"{MODULE_PATH}.post_with_context")
    def test_create_applies_documented_defaults(
        self, mock_post, mock_post_model, mock_check
    ):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            rules=[{"role": "storage", "scope": "myrealm", "resource_type": "realms"}]
        )
        mock_post.return_value = Mock(status_code=200)

        create_policy(mock_module, Mock())

        sent = mock_post_model.call_args.kwargs
        assert sent["enabled"] is True
        assert sent["aggregation_strategy"] == "all-permissions"

    @patch(f"{MODULE_PATH}.check_response")
    @patch(f"{MODULE_PATH}.PolicyManagementAccessPost")
    @patch(f"{MODULE_PATH}.post_with_context")
    def test_create_keeps_given_settings(self, mock_post, mock_post_model, mock_check):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            enabled=False, aggregation_strategy="least-common-permissions"
        )
        mock_post.return_value = Mock(status_code=200)

        create_policy(mock_module, Mock())

        sent = mock_post_model.call_args.kwargs
        assert sent["enabled"] is False
        assert sent["aggregation_strategy"] == "least-common-permissions"


def _run_main(params, policies):
    """Run main() with get_policies_management_access answering from a dict"""
    mock_module = Mock()
    mock_module.check_mode = False
    mock_module.params = params
    mock_module.fail_json.side_effect = SystemExit(1)
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_array = Mock()
    mock_array.get_rest_version.return_value = "2.38"

    def lookup(array, method, version, module, names):
        if names[0] in policies:
            return Mock(status_code=200, items=[policies[names[0]]])
        return Mock(status_code=400, items=[])

    with patch(f"{MODULE_PATH}.AnsibleModule", return_value=mock_module), patch(
        f"{MODULE_PATH}.get_array", return_value=mock_array
    ), patch(f"{MODULE_PATH}.LooseVersion", side_effect=float), patch(
        f"{MODULE_PATH}.get_with_context", side_effect=lookup
    ), patch(
        f"{MODULE_PATH}.create_policy"
    ) as mock_create, patch(
        f"{MODULE_PATH}.update_policy"
    ) as mock_update:
        try:
            main()
        except SystemExit:
            pass
    return mock_module, mock_create, mock_update


class TestMainRoleValidation:
    """Only viewer, support, admin and storage are accepted by the array"""

    def test_unsupported_role_fails_before_any_array_call(self):
        params = _params(
            rules=[
                {"role": "storage_admin", "scope": "myrealm", "resource_type": "realms"}
            ]
        )
        mock_module, mock_create, dummy = _run_main(params, {})

        mock_module.fail_json.assert_called_once()
        msg = mock_module.fail_json.call_args.kwargs["msg"]
        assert "unsupported role [storage_admin]" in msg
        assert "viewer, support, admin, storage" in msg
        mock_create.assert_not_called()

    def test_supported_roles_pass(self):
        rules = [
            {"role": role, "scope": "myrealm", "resource_type": "realms"}
            for role in ("viewer", "support", "admin", "storage")
        ]
        mock_module, mock_create, dummy = _run_main(_params(rules=rules), {})

        mock_module.fail_json.assert_not_called()
        mock_create.assert_called_once()


class TestMainRenameIdempotent:
    """Re-running a rename after it has happened reports no change"""

    def test_renamed_target_present_reports_no_change(self):
        params = _params(rename="newname")
        mock_module, mock_create, mock_update = _run_main(params, {"newname": Mock()})

        mock_module.exit_json.assert_called_once_with(changed=False)
        mock_create.assert_not_called()
        mock_update.assert_not_called()

    def test_neither_name_present_fails(self):
        params = _params(rename="newname")
        mock_module, mock_create, dummy = _run_main(params, {})

        mock_module.fail_json.assert_called_once()
        assert "not found to rename" in mock_module.fail_json.call_args.kwargs["msg"]
        mock_create.assert_not_called()

    def test_source_present_is_updated(self):
        params = _params(rename="newname")
        mock_module, mock_create, mock_update = _run_main(params, {"mypolicy": Mock()})

        mock_update.assert_called_once()
        mock_create.assert_not_called()
