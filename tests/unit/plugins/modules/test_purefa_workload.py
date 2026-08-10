# Copyright: (c) 2026, Pure Storage Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_workload module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

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
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.version"] = (
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

from plugins.modules.purefa_workload import (
    _build_workload_parameters,
    _workload_completed,
    delete_workload,
    eradicate_workload,
    recover_workload,
    rename_workload,
    create_workload,
    expand_workload,
    connect_or_disconnect_volumes,
)


def _mock_preset_parameter(name, parameter_type):
    preset_parameter = Mock()
    preset_parameter.name = name
    preset_parameter.type = parameter_type
    return preset_parameter


def _mock_get_arrays(name="local-array"):
    """Response for get_arrays(), which returns only the array being addressed"""
    local_array = Mock()
    local_array.name = name
    return Mock(items=[local_array])


# 1754587211000ms is 2025-08-07 17:20:11 UTC, the pair the fact formatting is
# checked against
CREATED_MS = 1754587211000
CREATED_STR = "2025-08-07 17:20:11"


def _mock_workload(
    name="test-workload",
    context="arrayB",
    preset="test-fleet:test-preset",
    status="ready",
    destroyed=False,
    time_remaining=None,
    status_details=None,
):
    """A Workload object as returned by get/post/patch_workloads"""
    workload = Mock()
    # Mock(name=...) sets the mock's own name, so .name must be assigned separately
    workload.name = name
    workload.context = Mock()
    workload.context.name = context
    workload.preset = Mock()
    workload.preset.name = preset
    workload.status = status
    workload.status_details = [] if status_details is None else status_details
    workload.destroyed = destroyed
    workload.created = CREATED_MS
    workload.time_remaining = time_remaining
    return workload


def _mock_workload_response(status_code=200, **kwargs):
    """Response wrapping a single Workload, as post/patch_workloads return"""
    return Mock(status_code=status_code, items=[_mock_workload(**kwargs)])


def _expected_facts(
    name="test-workload",
    context="arrayB",
    preset="test-fleet:test-preset",
    status="ready",
    destroyed=False,
    time_remaining=None,
    status_details=None,
):
    """The fact dict _workload_facts() builds for the matching _mock_workload()

    Flat, with the name as a field rather than the key, and with the
    module-owned completed flag derived from the status.
    """
    return {
        "name": name,
        "context": context,
        "preset": preset,
        "status": status,
        "completed": status in ("ready", "destroyed"),
        "status_details": [] if status_details is None else status_details,
        "destroyed": destroyed,
        "time_remaining": time_remaining,
        "created": CREATED_STR,
    }


def _params(**overrides):
    """Module params with the defaults every path reads already filled in"""
    params = {
        "name": "test-workload",
        "context": "arrayB",
        "host": "",
        "eradicate": False,
        "recommendation": False,
        "wait": False,
        "wait_timeout": 300,
    }
    params.update(overrides)
    return params


class TestDeleteWorkload:
    """Test cases for delete_workload function"""

    def test_delete_workload_check_mode(self):
        """Check mode sends nothing, so the pre-delete state is what is known"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = Mock()

        delete_workload(mock_module, mock_array, _mock_workload())

        mock_array.patch_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )


class TestEradicateWorkload:
    """Test cases for eradicate_workload function"""

    def test_eradicate_workload_check_mode(self):
        """Test eradicate_workload in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = Mock()

        eradicate_workload(mock_module, mock_array)

        mock_array.delete_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestRecoverWorkload:
    """Test cases for recover_workload function"""

    def test_recover_workload_check_mode(self):
        """Check mode sends nothing, so the destroyed state is what is known"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = Mock()

        recover_workload(
            mock_module, mock_array, _mock_workload(status="destroyed", destroyed=True)
        )

        mock_array.patch_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="destroyed", destroyed=True)
        )


class TestRenameWorkload:
    """Test cases for rename_workload function"""

    def test_rename_workload_check_mode(self):
        """Check mode sends nothing, so the workload still has its old name"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(name="old-workload", rename="new-workload")
        mock_array = Mock()

        rename_workload(mock_module, mock_array, _mock_workload(name="old-workload"))

        mock_array.patch_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(name="old-workload")
        )


class TestCreateWorkload:
    """Test cases for create_workload function"""

    def test_create_workload_check_mode(self):
        """A create that has not happened has no workload to describe"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = Mock()
        mock_fleet = Mock()
        mock_preset_config = Mock()
        mock_preset_config.parameters = []
        mock_preset_config.periodic_replication_configurations = []
        mock_preset_config.placement_configurations = []
        mock_preset_config.qos_configurations = []
        mock_preset_config.snapshot_configurations = []
        mock_preset_config.volume_configurations = []
        mock_preset_config.workload_tags = []

        create_workload(mock_module, mock_array, mock_fleet, mock_preset_config)

        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestWorkloadCompleted:
    """Test cases for the lifecycle classification both wait and facts use"""

    @pytest.mark.parametrize("status", ["ready", "destroyed"])
    def test_terminal_statuses_are_complete(self, status):
        """Nothing is in flight for a workload in a terminal status"""
        mock_module = Mock()

        assert _workload_completed(mock_module, _mock_workload(status=status)) is True
        mock_module.warn.assert_not_called()

    @pytest.mark.parametrize(
        "status", ["creating", "destroying", "eradicating", "recovering"]
    )
    def test_transient_statuses_are_incomplete(self, status):
        """A transient status is in flight, and is expected, so does not warn"""
        mock_module = Mock()

        assert _workload_completed(mock_module, _mock_workload(status=status)) is False
        mock_module.warn.assert_not_called()

    def test_unrecognised_status_is_incomplete_and_warns(self):
        """An unknown status can never be mistaken for success"""
        mock_module = Mock()

        result = _workload_completed(mock_module, _mock_workload(status="quiescing"))

        assert result is False
        mock_module.warn.assert_called_once()
        warning = mock_module.warn.call_args[0][0]
        assert "quiescing" in warning
        assert "test-workload" in warning

    def test_missing_status_is_incomplete_and_warns(self):
        """A Workload model without a status at all is still safe"""
        mock_module = Mock()
        workload = _mock_workload()
        del workload.status

        assert _workload_completed(mock_module, workload) is False
        mock_module.warn.assert_called_once()


class TestBuildWorkloadParameters:
    """Test cases for workload parameter normalization"""

    @patch("plugins.modules.purefa_workload.WorkloadParameter")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValue")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValueResourceReference")
    def test_build_workload_parameters_resource_reference(
        self,
        mock_resource_reference,
        mock_parameter_value,
        mock_parameter,
    ):
        """Test resource reference workload parameters are normalized"""
        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [
                {
                    "name": "replication_target",
                    "value": {"resource_reference": {"name": "slcfax2"}},
                }
            ],
        }
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("replication_target", "resource_reference")
        ]

        result = _build_workload_parameters(mock_module, mock_preset_config)

        assert result == [mock_parameter.return_value]
        mock_resource_reference.assert_called_once_with(name="slcfax2")
        mock_parameter_value.assert_called_once_with(
            resource_reference=mock_resource_reference.return_value
        )
        mock_parameter.assert_called_once_with(
            name="replication_target", value=mock_parameter_value.return_value
        )

    @patch("plugins.modules.purefa_workload.WorkloadParameter")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValue")
    def test_build_workload_parameters_boolean_false(
        self, mock_parameter_value, mock_parameter
    ):
        """Test boolean false is treated as a supplied value"""
        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [{"name": "enable_replication", "value": {"boolean": False}}],
        }
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("enable_replication", "boolean")
        ]

        result = _build_workload_parameters(mock_module, mock_preset_config)

        assert result == [mock_parameter.return_value]
        mock_parameter_value.assert_called_once_with(boolean=False)
        mock_parameter.assert_called_once_with(
            name="enable_replication", value=mock_parameter_value.return_value
        )

    @patch("plugins.modules.purefa_workload.WorkloadParameter")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValue")
    def test_build_workload_parameters_boolean_false_ignores_none_value_types(
        self, mock_parameter_value, mock_parameter
    ):
        """Test Ansible-normalized None value types are ignored for booleans"""
        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [
                {
                    "name": "enable_replication",
                    "value": {
                        "string": None,
                        "integer": None,
                        "boolean": False,
                        "resource_reference": None,
                    },
                }
            ],
        }
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("enable_replication", "boolean")
        ]

        result = _build_workload_parameters(mock_module, mock_preset_config)

        assert result == [mock_parameter.return_value]
        mock_parameter_value.assert_called_once_with(boolean=False)
        mock_parameter.assert_called_once_with(
            name="enable_replication", value=mock_parameter_value.return_value
        )

    def test_build_workload_parameters_rejects_multiple_value_types(self):
        """Test multiple parameter value types are rejected"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [
                {
                    "name": "replication_target",
                    "value": {"string": "slcfax2", "integer": 1},
                }
            ],
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("replication_target", "string")
        ]

        with pytest.raises(SystemExit):
            _build_workload_parameters(mock_module, mock_preset_config)

        mock_module.fail_json.assert_called_once()

    @patch("plugins.modules.purefa_workload.WorkloadParameter")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValue")
    @patch("plugins.modules.purefa_workload.WorkloadParameterValueResourceReference")
    def test_build_workload_parameters_resource_reference_ignores_none_fields(
        self,
        mock_resource_reference,
        mock_parameter_value,
        mock_parameter,
    ):
        """Test Ansible-normalized None fields are ignored for resource references"""
        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [
                {
                    "name": "replication_target",
                    "value": {
                        "string": None,
                        "integer": None,
                        "boolean": None,
                        "resource_reference": {
                            "id": None,
                            "name": "slcfax2",
                            "resource_type": None,
                        },
                    },
                }
            ],
        }
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("replication_target", "resource_reference")
        ]

        result = _build_workload_parameters(mock_module, mock_preset_config)

        assert result == [mock_parameter.return_value]
        mock_resource_reference.assert_called_once_with(name="slcfax2")
        mock_parameter_value.assert_called_once_with(
            resource_reference=mock_resource_reference.return_value
        )
        mock_parameter.assert_called_once_with(
            name="replication_target", value=mock_parameter_value.return_value
        )

    def test_build_workload_parameters_rejects_invalid_resource_reference(self):
        """Test invalid resource references are rejected"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "preset": "fleet:Oracle",
            "parameters": [
                {
                    "name": "replication_target",
                    "value": {"resource_reference": {"id": "123", "name": "slcfax2"}},
                }
            ],
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_preset_config = Mock()
        mock_preset_config.parameters = [
            _mock_preset_parameter("replication_target", "resource_reference")
        ]

        with pytest.raises(SystemExit):
            _build_workload_parameters(mock_module, mock_preset_config)

        mock_module.fail_json.assert_called_once()


class TestConnectOrDisconnectVolumes:
    """Test cases for connect_or_disconnect_volumes function"""

    def test_connect_volumes_check_mode(self):
        """Test connect_or_disconnect_volumes in connect mode with check_mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()

        # Mock get_connections - no existing connections
        mock_array.get_connections.return_value = Mock(status_code=200, items=[])

        # Mock get_volumes - workload has volumes
        mock_volume = Mock()
        mock_volume.name = "test-volume"
        mock_array.get_volumes.return_value = Mock(status_code=200, items=[mock_volume])

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        # Only host connections would change, so the workload is described as read
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )

    def test_disconnect_volumes_check_mode(self):
        """Test connect_or_disconnect_volumes in disconnect mode with check_mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()

        # Mock get_connections - volume is connected
        mock_conn = Mock()
        mock_conn.volume = Mock()
        mock_conn.volume.name = "test-volume"
        mock_array.get_connections.return_value = Mock(
            status_code=200, items=[mock_conn]
        )

        # Mock get_volumes - workload has the connected volume
        mock_volume = Mock()
        mock_volume.name = "test-volume"
        mock_array.get_volumes.return_value = Mock(status_code=200, items=[mock_volume])

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        # Only host connections would change, so the workload is described as read
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )

    def test_connect_volumes_no_change(self):
        """Test connect_or_disconnect_volumes when volume is already connected"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()

        # Mock get_connections - volume is already connected
        mock_conn = Mock()
        mock_conn.volume = Mock()
        mock_conn.volume.name = "test-volume"
        mock_array.get_connections.return_value = Mock(
            status_code=200, items=[mock_conn]
        )

        # Mock get_volumes - workload has the same volume
        mock_volume = Mock()
        mock_volume.name = "test-volume"
        mock_array.get_volumes.return_value = Mock(status_code=200, items=[mock_volume])

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        # Nothing changed, but the workload is still described
        mock_module.exit_json.assert_called_once_with(
            changed=False, workload=_expected_facts()
        )


class TestDeleteWorkloadSuccess:
    """Additional test cases for delete_workload function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_workload_success(self, mock_check_response):
        """Test delete_workload successfully deletes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1")
        mock_array = Mock()
        # The PATCH response reports the post-delete state
        mock_array.patch_workloads.return_value = _mock_workload_response(
            status="destroying", destroyed=True, time_remaining=86400000
        )

        delete_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True,
            workload=_expected_facts(
                status="destroying", destroyed=True, time_remaining=86400000
            ),
        )


class TestEradicateWorkloadSuccess:
    """Additional test cases for eradicate_workload function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_eradicate_workload_success(self, mock_check_response):
        """Test eradicate_workload successfully eradicates"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1")
        mock_array = Mock()
        mock_array.delete_workloads.return_value = Mock(status_code=200)

        eradicate_workload(mock_module, mock_array)

        mock_array.delete_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestRecoverWorkloadSuccess:
    """Additional test cases for recover_workload function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_recover_workload_success(self, mock_check_response):
        """Test recover_workload successfully recovers without host"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1")
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            status="recovering"
        )

        recover_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="recovering")
        )


class TestRenameWorkloadSuccess:
    """Additional test cases for rename_workload function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_rename_workload_success(self, mock_check_response):
        """Test rename_workload successfully renames"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            name="old-workload", rename="new-workload", context="pod1"
        )
        mock_array = Mock()
        # The PATCH response is keyed by the new name
        mock_array.patch_workloads.return_value = _mock_workload_response(
            name="new-workload"
        )

        rename_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(name="new-workload")
        )
        assert "old-workload" not in mock_module.exit_json.call_args.kwargs["workload"]


class TestCreateWorkloadSuccess:
    """Test cases for create_workload function success scenarios"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_workload_success(self, mock_check_response):
        """Test create_workload successfully creates"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = Mock()
        # A freshly created workload is still provisioning
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="pod1", status="creating"
        )
        mock_fleet = Mock()
        mock_preset_config = Mock()
        mock_preset_config.parameters = []
        mock_preset_config.periodic_replication_configurations = Mock()
        mock_preset_config.placement_configurations = Mock()
        mock_preset_config.qos_configurations = Mock()
        mock_preset_config.snapshot_configurations = Mock()
        mock_preset_config.volume_configurations = Mock()
        mock_preset_config.workload_tags = Mock()

        create_workload(mock_module, mock_array, mock_fleet, mock_preset_config)

        mock_array.post_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="creating")
        )

    @patch("plugins.modules.purefa_workload._build_workload_parameters")
    @patch("plugins.modules.purefa_workload.WorkloadPlacementRecommendation")
    @patch("plugins.modules.purefa_workload.WorkloadPost")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_workload_passes_parameters_to_recommendation_and_create(
        self,
        mock_check_response,
        mock_workload_post,
        mock_recommendation,
        mock_build_workload_parameters,
    ):
        """Test create_workload passes parameters into recommendation and create APIs"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            recommendation=True,
            # Fusion's recommendation replaces this requested placement
            placement="arrayA",
        )
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="arrayB", status="creating"
        )
        mock_calc = Mock()
        mock_calc.name = "calc-1"
        mock_array.post_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[mock_calc]
        )
        recommendation_result = Mock(status="completed")
        placement_target = Mock()
        placement_target.name = "arrayB"
        recommendation_result.results = [Mock()]
        recommendation_result.results[0].placements = [Mock()]
        recommendation_result.results[0].placements[0].targets = [placement_target]
        mock_array.get_workloads_placement_recommendations.return_value = Mock(
            items=[recommendation_result]
        )
        mock_build_workload_parameters.return_value = [Mock(name="param-1")]
        mock_preset_config = Mock()

        create_workload(mock_module, mock_array, Mock(), mock_preset_config)

        mock_build_workload_parameters.assert_called_once_with(
            mock_module, mock_preset_config
        )
        mock_recommendation.assert_called_once_with(
            parameters=mock_build_workload_parameters.return_value
        )
        mock_workload_post.assert_called_once_with(
            parameters=mock_build_workload_parameters.return_value
        )
        mock_array.post_workloads.assert_called_once_with(
            names=["test-workload"],
            preset_names=["test-preset"],
            workload=mock_workload_post.return_value,
            context_names=["arrayB"],
        )
        # The fact names the array Fusion chose, not the requested placement
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="arrayB", status="creating")
        )
        assert mock_module.exit_json.call_args.kwargs["workload"]["context"] == "arrayB"

    def test_create_workload_check_mode(self):
        """Test create_workload in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = Mock()
        mock_fleet = Mock()
        mock_preset_config = Mock()
        mock_preset_config.parameters = []
        mock_preset_config.periodic_replication_configurations = Mock()
        mock_preset_config.placement_configurations = Mock()
        mock_preset_config.qos_configurations = Mock()
        mock_preset_config.snapshot_configurations = Mock()
        mock_preset_config.volume_configurations = Mock()
        mock_preset_config.workload_tags = Mock()

        create_workload(mock_module, mock_array, mock_fleet, mock_preset_config)

        mock_array.post_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestExpandWorkloadSuccess:
    """Test cases for expand_workload function success scenarios"""

    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_workload_success(self, mock_create_vol, mock_connect_vols):
        """Test expand_workload successfully expands"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=2,
            host="host1",
        )
        mock_array = Mock()
        mock_fleet = Mock()
        # Create volume config that matches
        mock_vol_config = Mock()
        mock_vol_config.name = "vol-config1"
        volume_configs = [mock_vol_config]

        expand_workload(
            mock_module, mock_array, mock_fleet, volume_configs, _mock_workload()
        )

        assert mock_create_vol.call_count == 2
        mock_connect_vols.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )

    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_workload_no_match_fails(self, mock_create_vol):
        """Test expand_workload fails when no volume config matches"""
        import pytest

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="nonexistent-config",
            volume_count=2,
        )
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_array = Mock()
        mock_fleet = Mock()
        # Create volume config with different name
        mock_vol_config = Mock()
        mock_vol_config.name = "other-config"
        volume_configs = [mock_vol_config]

        with pytest.raises(SystemExit):
            expand_workload(
                mock_module, mock_array, mock_fleet, volume_configs, _mock_workload()
            )

        mock_create_vol.assert_not_called()
        mock_module.fail_json.assert_called_once()


class TestDeleteWorkloadWithEradicate:
    """Test cases for delete_workload with eradicate option"""

    @patch("plugins.modules.purefa_workload.eradicate_workload")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_workload_with_eradicate(
        self, mock_check_response, mock_eradicate_workload
    ):
        """Test delete_workload with eradicate flag"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", eradicate=True)
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            destroyed=True
        )

        delete_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_eradicate_workload.assert_called_once_with(mock_module, mock_array)

    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_workload_with_eradicate_returns_empty_fact(
        self, mock_check_response
    ):
        """delete+eradicate exits via eradicate_workload, so nothing is described"""
        import pytest

        mock_module = Mock()
        mock_module.check_mode = False
        # The real exit_json terminates the module, so eradicate_workload's exit
        # is the only one that ever runs on this path
        mock_module.exit_json.side_effect = SystemExit(0)
        mock_module.params = _params(context="pod1", eradicate=True)
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            destroyed=True
        )
        mock_array.delete_workloads.return_value = Mock(status_code=200)

        with pytest.raises(SystemExit):
            delete_workload(mock_module, mock_array)

        mock_array.delete_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})

    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_workload_without_eradicate(self, mock_check_response):
        """Test delete_workload without eradicate flag"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1")
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            destroyed=True
        )

        delete_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(destroyed=True)
        )


class TestRecoverWorkloadWithHost:
    """Test cases for recover_workload with host option"""

    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_recover_workload_with_host(
        self, mock_check_response, mock_connect_volumes
    ):
        """Test recover_workload with host connection"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response()

        recover_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        mock_connect_volumes.assert_called_once_with(mock_module, mock_array)
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )


class TestConnectOrDisconnectVolumesSuccess:
    """Test cases for connect_or_disconnect_volumes success paths"""

    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_connect_volumes_success(self, mock_check_response, mock_connect_volumes):
        """Test connect_or_disconnect_volumes connects volumes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()
        # Mock no existing connections
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.items = []
        mock_array.get_connections.return_value = mock_response
        # Mock workload volumes exist
        mock_vol_response = Mock()
        mock_vol_response.status_code = 200
        mock_vol_response.items = [Mock(name="vol1")]
        mock_array.get_volumes.return_value = mock_vol_response

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        mock_connect_volumes.assert_called_once_with(mock_module, mock_array)
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )

    @patch("plugins.modules.purefa_workload._disconnect_volumes")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_disconnect_volumes_success(
        self, mock_check_response, mock_disconnect_volumes
    ):
        """Test connect_or_disconnect_volumes disconnects volumes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()
        # Mock existing connections - volume name must be accessible via conn.volume.name
        mock_response = Mock()
        mock_response.status_code = 200
        mock_conn = Mock()
        mock_conn.volume = Mock()
        mock_conn.volume.name = "vol1"  # Set as attribute, not constructor arg
        mock_response.items = [mock_conn]
        mock_array.get_connections.return_value = mock_response
        # Mock workload volumes exist - must match connection volume name
        mock_vol_response = Mock()
        mock_vol_response.status_code = 200
        mock_vol = Mock()
        mock_vol.name = "vol1"  # Must match the connection volume name
        mock_vol_response.items = [mock_vol]
        mock_array.get_volumes.return_value = mock_vol_response

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        mock_disconnect_volumes.assert_called_once_with(mock_module, mock_array)
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts()
        )


class TestCreateVolume:
    """Test cases for _create_volume helper function"""

    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.VolumePost")
    @patch("plugins.modules.purefa_workload.WorkloadConfigurationReference")
    def test_create_volume_success(
        self, mock_workload_config, mock_volume_post, mock_check_response
    ):
        """Test _create_volume creates a volume"""
        from plugins.modules.purefa_workload import _create_volume

        mock_module = Mock()
        mock_module.params = _params(volume_configuration="vol-config", context="pod1")
        mock_array = Mock()
        created_volume = Mock()
        created_volume.name = "test-workload-vol1"
        mock_array.post_volumes.return_value = Mock(
            status_code=200, items=[created_volume]
        )

        result = _create_volume(mock_module, mock_array)

        mock_array.post_volumes.assert_called_once()
        mock_check_response.assert_called_once()
        # The array generates the name, so it has to come back for a wait to use
        assert result == "test-workload-vol1"


class TestDisconnectVolumes:
    """Test cases for _disconnect_volumes helper function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_disconnect_volumes_success(self, mock_check_response):
        """Test _disconnect_volumes disconnects all workload volumes"""
        from plugins.modules.purefa_workload import _disconnect_volumes

        mock_module = Mock()
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()
        mock_vol = Mock()
        mock_vol.name = "vol1"
        mock_array.get_volumes.return_value = Mock(items=[mock_vol])
        mock_array.delete_connections.return_value = Mock(status_code=200)

        _disconnect_volumes(mock_module, mock_array)

        mock_array.get_volumes.assert_called_once()
        mock_array.delete_connections.assert_called_once_with(
            host_names=["host1"],
            context_names=["pod1"],
            volume_names=["vol1"],
        )


class TestConnectVolumes:
    """Test cases for _connect_volumes helper function"""

    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.ConnectionPost")
    def test_connect_volumes_success(self, mock_connection_post, mock_check_response):
        """Test _connect_volumes connects all workload volumes"""
        from plugins.modules.purefa_workload import _connect_volumes

        mock_module = Mock()
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = Mock()
        mock_vol = Mock()
        mock_vol.name = "vol1"
        mock_array.get_volumes.return_value = Mock(items=[mock_vol])
        mock_array.post_connections.return_value = Mock(status_code=200)

        _connect_volumes(mock_module, mock_array)

        mock_array.get_volumes.assert_called_once()
        mock_array.post_connections.assert_called_once()


class TestMain:
    """Test cases for main() function"""

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_no_purestorage_sdk(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() fails when purestorage SDK not available"""
        import pytest
        from plugins.modules.purefa_workload import main

        # Need to patch at module level to override HAS_PURESTORAGE
        with patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", False):
            mock_module = Mock()
            mock_module.fail_json.side_effect = SystemExit(1)
            mock_ansible_module.return_value = mock_module

            with pytest.raises(SystemExit):
                main()

            mock_module.fail_json.assert_called_once()

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_api_version_too_old(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() fails when API version is too old"""
        import pytest
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {"volume_count": None}
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.0"  # Too old (needs 2.40)
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_invalid_volume_count(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() fails when volume_count is not positive"""
        import pytest
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {
            "volume_count": -1,
            "state": "present",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_workload.create_workload")
    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_fleet_check_fails(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_check_response,
        mock_loose_version,
        mock_create_workload,
    ):
        """Test main() calls check_response for fleet"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {
            "volume_count": None,
            "state": "present",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
            "rename": None,
            "host": "",
            "recommendation": False,
            "placement": None,
            "eradicate": False,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet_response = Mock(status_code=200)
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_fleet_response.items = [mock_fleet]
        mock_array.get_fleets.return_value = mock_fleet_response
        mock_array.get_arrays.return_value = _mock_get_arrays()
        mock_array.get_workloads.return_value = Mock(status_code=404)
        mock_preset_config = Mock()
        mock_array.get_presets_workload.return_value = Mock(
            status_code=200, items=[mock_preset_config]
        )
        mock_get_array.return_value = mock_array

        main()

        mock_check_response.assert_called()

    @patch("plugins.modules.purefa_workload.delete_workload")
    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_state_absent_delete(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_check_response,
        mock_loose_version,
        mock_delete_workload,
    ):
        """Test main() calls delete_workload when state=absent"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {
            "volume_count": None,
            "state": "absent",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
            "host": "",
            "placement": None,
            "eradicate": False,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet_response = Mock(status_code=200)
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_fleet_response.items = [mock_fleet]
        mock_array.get_fleets.return_value = mock_fleet_response
        mock_array.get_arrays.return_value = _mock_get_arrays()
        # Workload exists and not destroyed
        mock_workload = Mock()
        mock_workload.destroyed = False
        mock_array.get_workloads.return_value = Mock(
            status_code=200, items=[mock_workload]
        )
        mock_get_array.return_value = mock_array

        main()

        mock_delete_workload.assert_called_once()

    @patch("plugins.modules.purefa_workload.eradicate_workload")
    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_state_absent_eradicate(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_check_response,
        mock_loose_version,
        mock_eradicate_workload,
    ):
        """Test main() calls eradicate_workload when state=absent and eradicate=true"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {
            "volume_count": None,
            "state": "absent",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
            "host": "",
            "placement": None,
            "eradicate": True,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet_response = Mock(status_code=200)
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_fleet_response.items = [mock_fleet]
        mock_array.get_fleets.return_value = mock_fleet_response
        mock_array.get_arrays.return_value = _mock_get_arrays()
        # Workload exists and is destroyed
        mock_workload = Mock()
        mock_workload.destroyed = True
        mock_array.get_workloads.return_value = Mock(
            status_code=200, items=[mock_workload]
        )
        mock_get_array.return_value = mock_array

        main()

        mock_eradicate_workload.assert_called_once()

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_no_change(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_check_response,
        mock_loose_version,
    ):
        """Test main() exits with no change when no action needed"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.params = {
            "volume_count": None,
            "state": "absent",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
            "host": "",
            "placement": None,
            "eradicate": False,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet_response = Mock(status_code=200)
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_fleet_response.items = [mock_fleet]
        mock_array.get_fleets.return_value = mock_fleet_response
        mock_array.get_arrays.return_value = _mock_get_arrays()
        # Workload does not exist - nothing to delete, nothing to describe
        mock_array.get_workloads.return_value = Mock(status_code=404)
        mock_get_array.return_value = mock_array

        main()

        mock_module.exit_json.assert_called_once_with(changed=False, workload={})

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_main_no_change_existing_workload_returns_fact(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_check_response,
        mock_loose_version,
    ):
        """An unchanged existing workload is still described on the no-change exit"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "volume_count": None,
            "state": "present",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
            "host": "",
            "placement": None,
            "eradicate": False,
            "rename": None,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet_response = Mock(status_code=200)
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_fleet_response.items = [mock_fleet]
        mock_array.get_fleets.return_value = mock_fleet_response
        mock_array.get_arrays.return_value = _mock_get_arrays()
        # Workload exists, is healthy, and no action applies to it
        mock_array.get_workloads.return_value = _mock_workload_response(
            context="local-array"
        )
        mock_get_array.return_value = mock_array

        main()

        mock_module.exit_json.assert_called_once_with(
            changed=False, workload=_expected_facts(context="local-array")
        )


class TestMainContextDefault:
    """Test cases for defaulting an empty context in main()

    An empty context is sent to the array as context_names=[""], which the
    Fusion backend rejects with an unhelpful internal error.
    """

    def _run_main(self, mock_ansible_module, mock_get_array, params):
        from plugins.modules.purefa_workload import main

        mock_module = Mock()
        mock_module.params = {
            "volume_count": None,
            "state": "absent",
            "preset": "test-preset",
            "name": "test-workload",
            "host": "",
            "eradicate": False,
            "placement": None,
            "context": "",
        }
        mock_module.params.update(params)
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_array.get_fleets.return_value = Mock(status_code=200, items=[mock_fleet])
        mock_array.get_arrays.return_value = _mock_get_arrays("MUCFA21")
        # Workload does not exist, so main() exits without acting on it
        mock_array.get_workloads.return_value = Mock(status_code=404)
        mock_get_array.return_value = mock_array

        main()

        return mock_module, mock_array

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_empty_context_defaults_to_local_array(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() defaults an empty context to the local array name"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module, mock_array = self._run_main(
            mock_ansible_module, mock_get_array, {}
        )

        assert mock_module.params["context"] == "MUCFA21"
        mock_array.get_workloads.assert_called_once_with(
            names=["test-workload"], context_names=["MUCFA21"]
        )

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_empty_context_defaults_to_placement(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() prefers the placement target over the local array name"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module, mock_array = self._run_main(
            mock_ansible_module, mock_get_array, {"placement": "arrayB"}
        )

        assert mock_module.params["context"] == "arrayB"
        mock_array.get_arrays.assert_not_called()

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_explicit_context_is_preserved(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test main() leaves an explicitly supplied context untouched"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module, mock_array = self._run_main(
            mock_ansible_module,
            mock_get_array,
            {"context": "arrayC", "placement": "arrayB"},
        )

        assert mock_module.params["context"] == "arrayC"
        mock_array.get_arrays.assert_not_called()


class TestWaitDisabled:
    """The default must preserve the pre-wait behaviour exactly"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_does_not_poll_by_default(self, mock_check_response, mock_wait_for):
        """Test create_workload issues no polls when wait is false"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="pod1", status="creating"
        )

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        mock_wait_for.assert_not_called()
        mock_array.get_workloads.assert_not_called()
        # The immediate POST response is what gets reported
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="creating")
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_does_not_poll_by_default(self, mock_check_response, mock_wait_for):
        """Test delete_workload issues no polls when wait is false"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1")
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            context="pod1", status="destroying", destroyed=True
        )

        delete_workload(mock_module, mock_array, _mock_workload())

        mock_wait_for.assert_not_called()

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_rename_never_waits(self, mock_check_response, mock_wait_for):
        """A rename is not asynchronous, so it does not wait even when asked"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            name="old-workload", rename="new-workload", context="pod1", wait=True
        )
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            name="new-workload", context="pod1"
        )

        rename_workload(mock_module, mock_array, _mock_workload(name="old-workload"))

        mock_wait_for.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(name="new-workload", context="pod1")
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_does_not_wait_in_check_mode(
        self, mock_create_vol, mock_connect_vols, mock_wait_for
    ):
        """Waiting is a complete no-op under check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=1,
            wait=True,
        )
        vol_config = Mock()
        vol_config.name = "vol-config1"

        mock_array = Mock()

        expand_workload(mock_module, mock_array, Mock(), [vol_config], _mock_workload())

        mock_wait_for.assert_not_called()
        mock_array.get_workloads.assert_not_called()


class TestWaitForCreate:
    """Test cases for waiting on workload provisioning"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_waits_for_ready(self, mock_check_response, mock_wait_for):
        """Test create_workload waits for the workload to become ready"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=True)
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="pod1", status="creating"
        )
        # The settled state the wait resolves to
        mock_wait_for.return_value = _mock_workload(context="pod1", status="ready")

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        wait_kwargs = mock_wait_for.call_args.kwargs
        assert wait_kwargs["timeout"] == 300
        assert wait_kwargs["description"] == "workload test-workload to become ready"
        # The facts describe the settled workload, not the immediate POST response
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="ready")
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_probe_reads_workload_in_action_context(
        self, mock_check_response, mock_wait_for
    ):
        """Test the poll reads the workload through the context of the action"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=True)
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(context="pod1")
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")
        mock_wait_for.return_value = _mock_workload(context="pod1")

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        probe = mock_wait_for.call_args.kwargs["probe"]
        probe()

        mock_array.get_workloads.assert_called_once_with(
            names=["test-workload"], context_names=["pod1"]
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_is_done_only_when_ready(self, mock_check_response, mock_wait_for):
        """Test the wait predicate accepts ready and nothing else"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=True)
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(context="pod1")
        mock_wait_for.return_value = _mock_workload(context="pod1")

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        is_done = mock_wait_for.call_args.kwargs["is_done"]
        assert is_done(_mock_workload(status="ready")) is True
        assert is_done(_mock_workload(status="creating")) is False
        # Terminal, but not the state a create is waiting for
        assert is_done(_mock_workload(status="destroyed")) is False
        # A workload that has gone missing mid-provision is not done
        assert is_done(None) is False

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_timeout_detail_quotes_array_diagnostics(
        self, mock_check_response, mock_wait_for
    ):
        """Test the timeout message can quote status_details verbatim"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=True)
        mock_array = Mock()
        mock_array.post_workloads.return_value = _mock_workload_response(context="pod1")
        mock_wait_for.return_value = _mock_workload(context="pod1")

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        detail = mock_wait_for.call_args.kwargs["detail"]
        workload = _mock_workload(status_details=["creating volume foo-vol1"])
        assert detail(workload) == "creating volume foo-vol1"
        assert detail(None) == ""

    @patch("plugins.modules.purefa_workload._build_workload_parameters")
    @patch("plugins.modules.purefa_workload.WorkloadPlacementRecommendation")
    @patch("plugins.modules.purefa_workload.WorkloadPost")
    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_with_recommendation_polls_the_chosen_target(
        self,
        mock_check_response,
        mock_wait_for,
        mock_workload_post,
        mock_recommendation,
        mock_build_workload_parameters,
    ):
        """Test the poll follows the placement Fusion chose, not the requested one"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            recommendation=True,
            placement="arrayA",
            wait=True,
        )
        mock_array = Mock()
        mock_calc = Mock()
        mock_calc.name = "calc-1"
        mock_array.post_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[mock_calc]
        )
        recommendation_result = Mock(status="completed")
        placement_target = Mock()
        placement_target.name = "arrayB"
        recommendation_result.results = [Mock()]
        recommendation_result.results[0].placements = [Mock()]
        recommendation_result.results[0].placements[0].targets = [placement_target]
        mock_array.get_workloads_placement_recommendations.return_value = Mock(
            items=[recommendation_result]
        )
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="arrayB", status="creating"
        )
        mock_array.get_workloads.return_value = _mock_workload_response(
            context="arrayB"
        )
        mock_wait_for.return_value = _mock_workload(context="arrayB", status="ready")

        create_workload(mock_module, mock_array, Mock(), Mock())

        mock_wait_for.call_args.kwargs["probe"]()
        mock_array.get_workloads.assert_called_once_with(
            names=["test-workload"], context_names=["arrayB"]
        )
        # The headline case: the caller learns where Fusion put the workload
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="arrayB", status="ready")
        )


class TestWaitForRecover:
    """Test cases for waiting on workload recovery"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_recover_waits_for_ready(self, mock_check_response, mock_wait_for):
        """Test recover_workload waits for the workload to become ready"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=True)
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            context="pod1", status="recovering"
        )
        mock_wait_for.return_value = _mock_workload(context="pod1", status="ready")

        recover_workload(
            mock_module, mock_array, _mock_workload(status="destroyed", destroyed=True)
        )

        assert (
            mock_wait_for.call_args.kwargs["description"]
            == "workload test-workload to become ready"
        )
        is_done = mock_wait_for.call_args.kwargs["is_done"]
        assert is_done(_mock_workload(status="recovering")) is False
        assert is_done(_mock_workload(status="ready")) is True
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="ready")
        )


class TestWaitForDelete:
    """Test cases for waiting on workload deletion"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_waits_for_destroyed(self, mock_check_response, mock_wait_for):
        """Test delete_workload waits for the workload to reach destroyed"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=True)
        mock_array = Mock()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            context="pod1", status="destroying", destroyed=True
        )
        mock_wait_for.return_value = _mock_workload(
            context="pod1",
            status="destroyed",
            destroyed=True,
            time_remaining=86400000,
        )

        delete_workload(mock_module, mock_array, _mock_workload())

        assert (
            mock_wait_for.call_args.kwargs["description"]
            == "workload test-workload to become destroyed"
        )
        is_done = mock_wait_for.call_args.kwargs["is_done"]
        assert is_done(_mock_workload(status="destroying", destroyed=True)) is False
        assert is_done(_mock_workload(status="destroyed", destroyed=True)) is True
        # A destroyed workload is complete but still counting down to eradication,
        # and time_remaining stays in raw milliseconds
        mock_module.exit_json.assert_called_once_with(
            changed=True,
            workload=_expected_facts(
                context="pod1",
                status="destroyed",
                destroyed=True,
                time_remaining=86400000,
            ),
        )


class TestWaitForEradicate:
    """Test cases for waiting on workload eradication"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_eradicate_waits_for_absence(self, mock_check_response, mock_wait_for):
        """Eradication is done when the workload is gone, not when a status says so"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=True)
        mock_array = Mock()
        mock_array.delete_workloads.return_value = Mock(status_code=200)

        eradicate_workload(mock_module, mock_array)

        assert (
            mock_wait_for.call_args.kwargs["description"]
            == "workload test-workload to be eradicated"
        )
        is_done = mock_wait_for.call_args.kwargs["is_done"]
        assert is_done(None) is True
        assert is_done(_mock_workload(status="eradicating")) is False
        # Nothing remains to describe either way
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_eradicate_probe_treats_404_as_absent(
        self, mock_check_response, mock_wait_for
    ):
        """Test a 404 from the poll is the success condition, not an error"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=True)
        mock_array = Mock()
        mock_array.delete_workloads.return_value = Mock(status_code=200)
        mock_array.get_workloads.return_value = Mock(status_code=404)

        eradicate_workload(mock_module, mock_array)

        probe = mock_wait_for.call_args.kwargs["probe"]
        assert probe() is None
        mock_check_response.assert_called_once()  # only the DELETE was checked

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_eradicate_probe_checks_failed_reads(
        self, mock_check_response, mock_wait_for
    ):
        """Test a non-200, non-404 read is reported rather than tracebacked over"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=True)
        mock_array = Mock()
        mock_array.delete_workloads.return_value = Mock(status_code=200)
        mock_array.get_workloads.return_value = Mock(status_code=500, items=[])

        eradicate_workload(mock_module, mock_array)
        mock_check_response.reset_mock()

        probe = mock_wait_for.call_args.kwargs["probe"]
        try:
            probe()
        except IndexError:
            # check_response is stubbed here, so the real fail_json exit is absent
            pass

        mock_check_response.assert_called_once()


class TestWaitForExpand:
    """Test cases for waiting on workload expansion"""

    def _run_expand(self, mock_wait_for, mock_create_vol, mock_array):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=2,
            wait=True,
        )
        mock_create_vol.side_effect = ["wl-vol1", "wl-vol2"]
        vol_config = Mock()
        vol_config.name = "vol-config1"
        mock_wait_for.return_value = {
            "workload": _mock_workload(context="pod1", status="ready"),
            "volumes": {"wl-vol1", "wl-vol2"},
        }

        expand_workload(
            mock_module,
            mock_array,
            Mock(),
            [vol_config],
            _mock_workload(context="pod1"),
        )

        return mock_module

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_waits_on_volumes_and_workload(
        self, mock_create_vol, mock_connect_vols, mock_wait_for
    ):
        """Test expand waits for both the new volumes and the workload status"""
        mock_array = Mock()
        mock_array.get_volumes.return_value = Mock(status_code=200, items=[])
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        mock_module = self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        wait_kwargs = mock_wait_for.call_args.kwargs
        assert wait_kwargs["timeout"] == 300
        assert "test-workload" in wait_kwargs["description"]

        ready = _mock_workload(status="ready")
        is_done = wait_kwargs["is_done"]
        # Both halves satisfied
        assert is_done({"workload": ready, "volumes": {"wl-vol1", "wl-vol2"}}) is True
        # A volume this task created has not appeared yet
        assert is_done({"workload": ready, "volumes": {"wl-vol1"}}) is False
        # The volumes exist, but the preset is still deriving configuration
        assert (
            is_done(
                {
                    "workload": _mock_workload(status="creating"),
                    "volumes": {"wl-vol1", "wl-vol2"},
                }
            )
            is False
        )
        # The settled workload is what gets reported
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="ready")
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_probe_targets_the_created_volumes(
        self, mock_create_vol, mock_connect_vols, mock_wait_for
    ):
        """Test the poll names the volumes this task created, not a volume count"""
        mock_array = Mock()
        created = [Mock(), Mock()]
        created[0].name = "wl-vol1"
        created[1].name = "wl-vol2"
        mock_array.get_volumes.return_value = Mock(status_code=200, items=created)
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        state = mock_wait_for.call_args.kwargs["probe"]()

        mock_array.get_volumes.assert_called_once_with(
            names=["wl-vol1", "wl-vol2"], context_names=["pod1"]
        )
        assert state["volumes"] == {"wl-vol1", "wl-vol2"}
        assert state["workload"].name == "test-workload"

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._connect_volumes")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_probe_tolerates_unresolvable_volume_names(
        self, mock_create_vol, mock_connect_vols, mock_wait_for
    ):
        """A name that does not resolve yet means not created, not failed"""
        mock_array = Mock()
        mock_array.get_volumes.return_value = Mock(status_code=400, items=[])
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        state = mock_wait_for.call_args.kwargs["probe"]()

        assert state["volumes"] == set()
        mock_array.get_workloads.assert_called_once()
