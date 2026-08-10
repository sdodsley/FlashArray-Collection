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

#: What _timestamp() is frozen to where a test predicts a create's creation time,
#: which would otherwise be whatever the clock said
PREDICTED_NOW = "2026-01-01 00:00:00"


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


#: Volume names _mock_volumes_response() reports for the workload by default
WORKLOAD_VOLUMES = ["wl-vol1", "wl-vol2"]


def _mock_volumes_response(names=None, status_code=200):
    """Response for get_volumes(), whose items only need a name"""
    volumes = []
    for name in WORKLOAD_VOLUMES if names is None else names:
        volume = Mock()
        volume.name = name
        volumes.append(volume)
    return Mock(status_code=status_code, items=volumes)


def _mock_connections_response(volume_names, host="host1", status_code=200):
    """Response for get_connections(), keyed off conn.volume.name"""
    connections = []
    for name in volume_names:
        connection = Mock()
        connection.volume = Mock()
        connection.volume.name = name
        connection.host = Mock()
        connection.host.name = host
        connections.append(connection)
    return Mock(status_code=status_code, items=connections)


def _mock_array(volume_names=None, connected=None, host="host1"):
    """A Mock array with the reads every fact-returning path performs stubbed

    volume_names is what get_volumes reports for the workload; connected is every
    volume the host can see, anywhere on the array.

    get_connections honours the volume_names it is asked for, as the real endpoint
    does, so a test cannot accidentally pass by relying on an unscoped read.
    """
    array = Mock()
    array.get_volumes.return_value = _mock_volumes_response(volume_names)
    all_connected = [] if connected is None else connected

    def get_connections(volume_names=None, **kwargs):
        requested = all_connected if volume_names is None else volume_names
        return _mock_connections_response(
            [name for name in all_connected if name in requested], host
        )

    array.get_connections.side_effect = get_connections
    return array


def _mock_recommendation(target="arrayB", status="completed"):
    """A calculated placement recommendation, as get_..._recommendations returns"""
    result = Mock(status=status)
    placement_target = Mock()
    placement_target.name = target
    result.results = [Mock()]
    result.results[0].placements = [Mock()]
    result.results[0].placements[0].targets = [placement_target]
    return result


def _expected_facts(
    name="test-workload",
    context="arrayB",
    preset="test-fleet:test-preset",
    status="ready",
    destroyed=False,
    time_remaining=None,
    status_details=None,
    volumes=None,
    host=None,
    created=CREATED_STR,
):
    """The fact dict _workload_facts() builds for the matching _mock_workload()

    Flat, with the name as a field rather than the key, the module-owned
    completed flag derived from the status, and the volume set and acted-on host.
    Also used for check-mode predictions, where created and volumes are among the
    values that cannot be known in advance.
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
        "created": created,
        "volumes": list(WORKLOAD_VOLUMES) if volumes is None else volumes,
        "host": host,
    }


def _params(**overrides):
    """Module params with the defaults every path reads already filled in"""
    params = {
        "name": "test-workload",
        "context": "arrayB",
        # Fleet-qualified by main() before any action runs
        "preset": None,
        "placement": None,
        "host": "",
        "eradicate": False,
        "recommendation": False,
        # wait is on by default, and host cannot be used without it
        "wait": True,
        "wait_timeout": 300,
    }
    params.update(overrides)
    return params


class TestDeleteWorkload:
    """Test cases for delete_workload function"""

    def test_delete_workload_check_mode(self):
        """Check mode predicts the destroyed workload the run would leave"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = _mock_array()

        delete_workload(mock_module, mock_array, _mock_workload())

        mock_array.patch_workloads.assert_not_called()
        # wait is on, so a real run would settle on destroyed
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="destroyed", destroyed=True)
        )

    def test_delete_workload_check_mode_without_wait(self):
        """Without waiting a real run returns mid-flight, so that is predicted"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(wait=False)
        mock_array = _mock_array()

        delete_workload(mock_module, mock_array, _mock_workload())

        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="destroying", destroyed=True)
        )

    def test_delete_with_eradicate_check_mode_predicts_nothing_left(self):
        """An eradicate leaves no workload, which is what a real run reports"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(eradicate=True)
        mock_array = _mock_array()

        delete_workload(mock_module, mock_array, _mock_workload())

        mock_array.patch_workloads.assert_not_called()
        mock_array.delete_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestEradicateWorkload:
    """Test cases for eradicate_workload function"""

    def test_eradicate_workload_check_mode(self):
        """Test eradicate_workload in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = _mock_array()

        eradicate_workload(mock_module, mock_array)

        mock_array.delete_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


class TestRecoverWorkload:
    """Test cases for recover_workload function"""

    def test_recover_workload_check_mode(self):
        """Check mode predicts the recovered workload, not the destroyed one read"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params()
        mock_array = _mock_array()

        recover_workload(
            mock_module, mock_array, _mock_workload(status="destroyed", destroyed=True)
        )

        mock_array.patch_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="ready", destroyed=False)
        )

    def test_recover_workload_check_mode_without_wait(self):
        """Without waiting a real run returns while still recovering"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(wait=False)
        mock_array = _mock_array()

        recover_workload(
            mock_module, mock_array, _mock_workload(status="destroyed", destroyed=True)
        )

        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(status="recovering", destroyed=False)
        )


class TestRenameWorkload:
    """Test cases for rename_workload function"""

    def test_rename_workload_check_mode(self):
        """Check mode predicts the new name, not the one the workload has now"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(name="old-workload", rename="new-workload")
        mock_array = _mock_array()

        rename_workload(mock_module, mock_array, _mock_workload(name="old-workload"))

        mock_array.patch_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(name="new-workload")
        )
        # The volumes are still read under the name the workload answers to now
        assert (
            mock_array.get_volumes.call_args.kwargs["filter"]
            == "workload.name='old-workload'"
        )


class TestCreateWorkload:
    """Test cases for create_workload function"""

    @patch("plugins.modules.purefa_workload._timestamp", return_value=PREDICTED_NOW)
    def test_create_workload_check_mode(self, mock_timestamp):
        """Check mode predicts the workload the run would create

        Nothing exists to read, so every value is either a parameter, unknowable,
        or - for the creation time - approximately now. Only the volume names stay
        empty, because the array generates those and a guess could be bound to.
        """
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = _mock_array()
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

        mock_array.post_workloads.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True,
            workload=_expected_facts(
                context="pod1",
                preset="test-preset",
                status="ready",
                volumes=[],
                created=PREDICTED_NOW,
            ),
        )

    @patch("plugins.modules.purefa_workload._timestamp", return_value=PREDICTED_NOW)
    def test_create_workload_check_mode_without_wait(self, mock_timestamp):
        """Without waiting a real run returns while the workload is creating"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1", wait=False)
        mock_array = _mock_array()

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        mock_module.exit_json.assert_called_once_with(
            changed=True,
            workload=_expected_facts(
                context="pod1",
                preset="test-preset",
                status="creating",
                volumes=[],
                created=PREDICTED_NOW,
            ),
        )


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

    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_volumes_check_mode(self, mock_wait_for_status):
        """Check mode reports the change without posting a connection"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        # The host sees neither workload volume yet
        mock_array = _mock_array(connected=[])
        mock_wait_for_status.return_value = None

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        mock_array.post_connections.assert_not_called()
        # Only host connections would change, so the workload is described as read
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
        )

    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_disconnect_volumes_check_mode(self, mock_wait_for_status):
        """Check mode reports the change without deleting a connection"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        mock_array.delete_connections.assert_not_called()
        # A disconnect never waits for a status - nothing about it is async
        mock_wait_for_status.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
        )

    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_volumes_no_change(self, mock_wait_for_status):
        """Nothing is posted when the host already sees every workload volume"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)
        mock_wait_for_status.return_value = None

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        mock_array.post_connections.assert_not_called()
        # Nothing changed, but the workload is still described
        mock_module.exit_json.assert_called_once_with(
            changed=False, workload=_expected_facts(host="host1")
        )

    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_disconnect_volumes_no_change(self, mock_wait_for_status):
        """Nothing is deleted when the host sees none of the workload volumes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        mock_array.delete_connections.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=False, workload=_expected_facts(host="host1")
        )

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_waits_for_ready_before_connecting(
        self, mock_wait_for_status, mock_check_response, mock_wait_for_connections
    ):
        """ "All connected" only means something once the volume set has settled"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])
        mock_wait_for_status.return_value = _mock_workload(context="pod1")

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload(context="pod1")
        )

        mock_wait_for_status.assert_called_once_with(
            mock_module, mock_array, "pod1", "ready"
        )
        # ...and only then is the volume set read and the connection posted
        mock_array.post_connections.assert_called_once()
        mock_wait_for_connections.assert_called_once()


class TestDeleteWorkloadSuccess:
    """Additional test cases for delete_workload function"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_workload_success(self, mock_check_response):
        """Test delete_workload successfully deletes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_module.params = _params(preset="test-preset", context="pod1", wait=False)
        mock_array = _mock_array()
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
    @patch("plugins.modules.purefa_workload._wait_for_recommendation")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_workload_passes_parameters_to_recommendation_and_create(
        self,
        mock_check_response,
        mock_wait_for_recommendation,
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
            wait=False,
        )
        mock_array = _mock_array()
        mock_array.post_workloads.return_value = _mock_workload_response(
            context="arrayB", status="creating"
        )
        mock_calc = Mock()
        mock_calc.name = "calc-1"
        mock_array.post_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[mock_calc]
        )
        mock_wait_for_recommendation.return_value = _mock_recommendation("arrayB")
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

    def test_create_workload_check_mode_sends_no_create(self):
        """Test create_workload posts nothing in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = _mock_array()
        mock_preset_config = Mock()
        mock_preset_config.parameters = []

        create_workload(mock_module, mock_array, Mock(), mock_preset_config)

        mock_array.post_workloads.assert_not_called()
        # The contract keeps its shape, so result.workload.context works under --check
        assert set(mock_module.exit_json.call_args.kwargs["workload"]) == set(
            _expected_facts()
        )


class TestExpandWorkloadSuccess:
    """Test cases for expand_workload function success scenarios"""

    @patch("plugins.modules.purefa_workload._wait_for_volumes")
    @patch("plugins.modules.purefa_workload._connect_host")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_workload_success(
        self, mock_create_vol, mock_connect_host, mock_wait_for_volumes
    ):
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
        mock_array = _mock_array()
        mock_wait_for_volumes.return_value = _mock_workload()
        mock_fleet = Mock()
        # Create volume config that matches
        mock_vol_config = Mock()
        mock_vol_config.name = "vol-config1"
        volume_configs = [mock_vol_config]

        expand_workload(
            mock_module, mock_array, mock_fleet, volume_configs, _mock_workload()
        )

        assert mock_create_vol.call_count == 2
        # The host is reconciled against the full volume set, not just the new
        # volumes - only the ones it cannot see get posted, inside _connect_host
        mock_connect_host.assert_called_once_with(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
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

    @patch("plugins.modules.purefa_workload._wait_for_status")
    @patch("plugins.modules.purefa_workload._connect_host")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_recover_workload_with_host(
        self, mock_check_response, mock_connect_host, mock_wait_for_status
    ):
        """Test recover_workload with host connection"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array()
        mock_array.patch_workloads.return_value = _mock_workload_response()
        mock_wait_for_status.return_value = _mock_workload()

        recover_workload(mock_module, mock_array)

        mock_array.patch_workloads.assert_called_once()
        # Recovered volumes may have kept their connections, so the diff inside
        # _connect_host is what stops this reposting and failing
        mock_connect_host.assert_called_once_with(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
        )


class TestConnectOrDisconnectVolumesSuccess:
    """Test cases for connect_or_disconnect_volumes success paths"""

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.ConnectionPost")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_volumes_success(
        self,
        mock_wait_for_status,
        mock_check_response,
        mock_connection_post,
        mock_wait_for_connections,
    ):
        """Test connect_or_disconnect_volumes connects the missing volumes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])
        mock_wait_for_status.return_value = _mock_workload()

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        mock_array.post_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=WORKLOAD_VOLUMES,
            context_names=["pod1"],
            connection=mock_connection_post.return_value,
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
        )

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_disconnect_volumes_success(
        self, mock_check_response, mock_wait_for_connections
    ):
        """Test connect_or_disconnect_volumes disconnects the attached volumes"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        mock_array.delete_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=WORKLOAD_VOLUMES,
            context_names=["pod1"],
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(host="host1")
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
        mock_module.check_mode = False
        mock_module.params = _params(volume_configuration="vol-config", context="pod1")
        mock_array = _mock_array()
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


class TestDisconnectHost:
    """Test cases for _disconnect_host

    The invariant here is the one that destroys data if it regresses: only the
    workload's own volumes may ever be disconnected.
    """

    @patch("plugins.modules.purefa_workload.check_response")
    def test_never_widens_beyond_the_workload(self, mock_check_response):
        """A host's connections outside the workload are left strictly alone"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array()
        # Deliberately make the read over-return a volume that has nothing to do
        # with this workload, so the intersection guard is what is under test
        mock_array.get_connections.side_effect = None
        mock_array.get_connections.return_value = _mock_connections_response(
            WORKLOAD_VOLUMES + ["other-vol"]
        )

        changed = _disconnect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is True
        mock_array.delete_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=WORKLOAD_VOLUMES,
            context_names=["pod1"],
        )
        # volume_names is always sent, and never names a foreign volume
        call_kwargs = mock_array.delete_connections.call_args.kwargs
        assert "other-vol" not in call_kwargs["volume_names"]
        assert call_kwargs["volume_names"]

    @patch("plugins.modules.purefa_workload.check_response")
    def test_deletes_only_what_is_attached(self, mock_check_response):
        """Converges from a partially attached host rather than failing"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array(connected=["wl-vol1"])

        changed = _disconnect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is True
        mock_array.delete_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=["wl-vol1"],
            context_names=["pod1"],
        )

    def test_no_op_when_nothing_is_attached(self):
        """Nothing to remove means no call and no change"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array(connected=[])

        changed = _disconnect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is False
        mock_array.delete_connections.assert_not_called()

    def test_check_mode_reports_without_acting(self):
        """Check mode returns the diff result but touches nothing"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        changed = _disconnect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is True
        mock_array.delete_connections.assert_not_called()

    def test_no_volumes_reads_and_writes_nothing(self):
        """A workload with no volumes yet cannot have connections to remove"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array()

        assert (
            _disconnect_host(mock_module, mock_array, "test-workload", "pod1", [])
            is False
        )
        mock_array.get_connections.assert_not_called()
        mock_array.delete_connections.assert_not_called()


class TestConnectHost:
    """Test cases for _connect_host"""

    @patch("plugins.modules.purefa_workload.ConnectionPost")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_never_reposts_and_never_widens(
        self, mock_check_response, mock_connection_post
    ):
        """Only the volumes the host cannot see are posted

        post_connections has no allow_errors, so reposting wl-vol1 would fail the
        task. This is the regression that makes expand-with-host unusable.
        """
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        # Already on one workload volume, plus one that is none of our business.
        # The read is left unscoped on purpose, so the set difference is what
        # keeps other-vol out of the POST.
        mock_array = _mock_array()
        mock_array.get_connections.side_effect = None
        mock_array.get_connections.return_value = _mock_connections_response(
            ["wl-vol1", "other-vol"]
        )

        changed = _connect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is True
        mock_array.post_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=["wl-vol2"],
            context_names=["pod1"],
            connection=mock_connection_post.return_value,
        )

    @patch("plugins.modules.purefa_workload.check_response")
    def test_no_op_when_fully_connected(self, mock_check_response):
        """Already seeing everything means no call and no change"""
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        changed = _connect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is False
        mock_array.post_connections.assert_not_called()

    def test_check_mode_reports_without_acting(self):
        """Check mode returns the diff result but touches nothing"""
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])

        changed = _connect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        assert changed is True
        mock_array.post_connections.assert_not_called()

    def test_no_volumes_posts_nothing(self):
        """A workload with no volumes yet has nothing to connect

        The old helper reached post_connections with volume_names=[], which the
        array rejects.
        """
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1", wait=False)
        mock_array = _mock_array()

        assert (
            _connect_host(mock_module, mock_array, "test-workload", "pod1", []) is False
        )
        mock_array.get_connections.assert_not_called()
        mock_array.post_connections.assert_not_called()


class TestScopedReads:
    """Test cases for the two shared read helpers"""

    @patch("plugins.modules.purefa_workload.check_response")
    def test_volume_names_are_checked_and_sorted(self, mock_check_response):
        """The volume read goes through check_response, unlike the old helpers"""
        from plugins.modules.purefa_workload import _workload_volume_names

        mock_module = Mock()
        mock_module.params = _params()
        mock_array = _mock_array(volume_names=["wl-vol2", "wl-vol1"])

        result = _workload_volume_names(
            mock_module, mock_array, "test-workload", "pod1"
        )

        assert result == ["wl-vol1", "wl-vol2"]
        mock_array.get_volumes.assert_called_once_with(
            filter="workload.name='test-workload'", context_names=["pod1"]
        )
        mock_check_response.assert_called_once()

    @patch("plugins.modules.purefa_workload.check_response")
    def test_connections_are_scoped_to_one_host_and_many_volumes(
        self, mock_check_response
    ):
        """The SDK rejects multiple names on two objects at once"""
        from plugins.modules.purefa_workload import _connected_volume_names

        mock_module = Mock()
        mock_module.params = _params()
        mock_array = _mock_array(connected=["wl-vol1"])

        result = _connected_volume_names(
            mock_module, mock_array, "pod1", WORKLOAD_VOLUMES, "host1"
        )

        assert result == {"wl-vol1"}
        mock_array.get_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=WORKLOAD_VOLUMES,
            context_names=["pod1"],
        )
        assert len(mock_array.get_connections.call_args.kwargs["host_names"]) == 1
        mock_check_response.assert_called_once()


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
        mock_module.params = {
            "volume_count": None,
            "host": "",
            "wait": True,
            "context": "",
            "placement": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = _mock_array()
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
            "host": "",
            "wait": True,
            "placement": None,
            "state": "present",
            "preset": "test-preset",
            "context": "",
            "name": "test-workload",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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

        mock_array = _mock_array()
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
    """wait: false is the fire-and-forget opt-out, available without a host"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_does_not_poll(self, mock_check_response, mock_wait_for):
        """Test create_workload issues no polls when wait is false"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=False)
        mock_array = _mock_array()
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
    def test_delete_does_not_poll(self, mock_check_response, mock_wait_for):
        """Test delete_workload issues no polls when wait is false"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
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
        mock_array = _mock_array()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            name="new-workload", context="pod1"
        )

        rename_workload(mock_module, mock_array, _mock_workload(name="old-workload"))

        mock_wait_for.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(name="new-workload", context="pod1")
        )

    @patch("plugins.modules.purefa_workload.wait_for", return_value=None)
    @patch("plugins.modules.purefa_workload._create_volume", return_value=None)
    def test_expand_wait_is_a_no_op_in_check_mode(self, mock_create_vol, mock_wait_for):
        """Waiting short-circuits, and the workload falls back to the one given

        wait_for returns None under check mode, so _wait_for_volumes has nothing to
        report and hands back the workload it was passed. Without that fallback the
        caller would be building facts from None.
        """
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=1,
        )
        vol_config = Mock()
        vol_config.name = "vol-config1"
        mock_array = _mock_array()

        expand_workload(mock_module, mock_array, Mock(), [vol_config], _mock_workload())

        # The facts describe the workload handed in, not None
        assert (
            mock_module.exit_json.call_args.kwargs["workload"]["name"]
            == "test-workload"
        )
        mock_array.get_workloads.assert_not_called()

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_host_less_eradicate_does_not_poll(
        self, mock_check_response, mock_wait_for
    ):
        """Test eradicate_workload issues no polls when wait is false"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
        mock_array.delete_workloads.return_value = Mock(status_code=200)

        eradicate_workload(mock_module, mock_array)

        mock_wait_for.assert_not_called()


class TestWaitForCreate:
    """Test cases for waiting on workload provisioning"""

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_waits_for_ready(self, mock_check_response, mock_wait_for):
        """Test create_workload waits for the workload to become ready"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(preset="test-preset", context="pod1", wait=True)
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
    @patch("plugins.modules.purefa_workload._wait_for_recommendation")
    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_create_with_recommendation_polls_the_chosen_target(
        self,
        mock_check_response,
        mock_wait_for,
        mock_wait_for_recommendation,
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
        mock_array = _mock_array()
        mock_calc = Mock()
        mock_calc.name = "calc-1"
        mock_array.post_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[mock_calc]
        )
        mock_wait_for_recommendation.return_value = _mock_recommendation("arrayB")
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_array = _mock_array()
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
        mock_create_vol.side_effect = list(WORKLOAD_VOLUMES)
        vol_config = Mock()
        vol_config.name = "vol-config1"
        mock_wait_for.return_value = {
            "workload": _mock_workload(context="pod1", status="ready"),
            "volumes": set(WORKLOAD_VOLUMES),
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
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_waits_on_volumes_and_workload(self, mock_create_vol, mock_wait_for):
        """Test expand waits for both the new volumes and the workload status"""
        mock_array = _mock_array()
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        mock_module = self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        wait_kwargs = mock_wait_for.call_args.kwargs
        assert wait_kwargs["timeout"] == 300
        assert "test-workload" in wait_kwargs["description"]

        ready = _mock_workload(status="ready")
        is_done = wait_kwargs["is_done"]
        # Both halves satisfied
        assert is_done({"workload": ready, "volumes": set(WORKLOAD_VOLUMES)}) is True
        # A volume this task created has not appeared yet
        assert is_done({"workload": ready, "volumes": {"wl-vol1"}}) is False
        # The volumes exist, but the preset is still deriving configuration
        assert (
            is_done(
                {
                    "workload": _mock_workload(status="creating"),
                    "volumes": set(WORKLOAD_VOLUMES),
                }
            )
            is False
        )
        # The settled workload is what gets reported
        mock_module.exit_json.assert_called_once_with(
            changed=True, workload=_expected_facts(context="pod1", status="ready")
        )

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_probe_targets_the_created_volumes(
        self, mock_create_vol, mock_wait_for
    ):
        """Test the poll names the volumes this task created, not a volume count"""
        mock_array = _mock_array()
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        # The facts read has already happened, so isolate the probe's own call
        mock_array.get_volumes.reset_mock()
        state = mock_wait_for.call_args.kwargs["probe"]()

        mock_array.get_volumes.assert_called_once_with(
            names=WORKLOAD_VOLUMES, context_names=["pod1"]
        )
        assert state["volumes"] == set(WORKLOAD_VOLUMES)
        assert state["workload"].name == "test-workload"

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload._create_volume")
    def test_expand_probe_tolerates_unresolvable_volume_names(
        self, mock_create_vol, mock_wait_for
    ):
        """A name that does not resolve yet means not created, not failed"""
        mock_array = _mock_array()
        mock_array.get_workloads.return_value = _mock_workload_response(context="pod1")

        self._run_expand(mock_wait_for, mock_create_vol, mock_array)

        # Set only now, so the facts read during expand still succeeded
        mock_array.get_volumes.return_value = _mock_volumes_response(
            names=[], status_code=400
        )
        state = mock_wait_for.call_args.kwargs["probe"]()

        assert state["volumes"] == set()
        mock_array.get_workloads.assert_called_once()


class TestHostRequiresWait:
    """host cannot be honoured without waiting, so the combination is rejected

    Connecting means the host sees *every* volume in the workload, which cannot
    be established while the volume set is still growing.
    """

    @pytest.mark.parametrize("state", ["present", "expand", "absent"])
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_host_with_wait_false_fails(
        self, mock_ansible_module, mock_get_array, state
    ):
        """Test main() rejects host with wait: false before touching the array"""
        from plugins.modules.purefa_workload import main

        mock_module = Mock()
        mock_module.params = _params(state=state, host="host1", wait=False)
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once()
        assert "wait" in mock_module.fail_json.call_args.kwargs["msg"]
        # Fails before any API call, so nothing was asked of the array
        mock_get_array.assert_not_called()

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_wait_false_without_host_is_allowed(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Fire-and-forget stays available to tasks that ask for no host work"""
        from plugins.modules.purefa_workload import main

        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0
        mock_module = Mock()
        mock_module.params = _params(
            state="absent", preset="test-preset", volume_count=None, wait=False
        )
        mock_ansible_module.return_value = mock_module
        mock_array = _mock_array()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_array.get_fleets.return_value = Mock(status_code=200, items=[mock_fleet])
        mock_array.get_arrays.return_value = _mock_get_arrays()
        mock_array.get_workloads.return_value = Mock(status_code=404)
        mock_get_array.return_value = mock_array

        main()

        mock_module.fail_json.assert_not_called()

    def test_wait_defaults_to_true_in_the_argument_spec(self):
        """The default has to be true for host to work without being asked for"""
        import plugins.modules.purefa_workload as module_under_test

        source = open(module_under_test.__file__).read()
        assert 'wait=dict(type="bool", default=True)' in source
        assert 'wait_timeout=dict(type="int", default=300)' in source


class TestWaitForConnections:
    """Test cases for waiting on the host operation itself"""

    def _wait_kwargs(self, mock_wait_for, mock_array, connected):
        from plugins.modules.purefa_workload import _wait_for_connections

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")

        _wait_for_connections(
            mock_module, mock_array, "test-workload", "pod1", connected
        )

        return mock_wait_for.call_args.kwargs

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_connect_is_done_only_when_every_volume_is_seen(self, mock_wait_for):
        """Partial attachment is never an acceptable end state"""
        kwargs = self._wait_kwargs(mock_wait_for, _mock_array(), True)

        is_done = kwargs["is_done"]
        assert is_done({"volumes": WORKLOAD_VOLUMES, "seen": {"wl-vol1"}}) is False
        assert (
            is_done({"volumes": WORKLOAD_VOLUMES, "seen": set(WORKLOAD_VOLUMES)})
            is True
        )
        assert kwargs["timeout"] == 300
        assert "connected to" in kwargs["description"]

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_disconnect_is_done_when_none_are_seen(self, mock_wait_for):
        """Done is the host seeing none of *these* volumes"""
        kwargs = self._wait_kwargs(mock_wait_for, _mock_array(), False)

        is_done = kwargs["is_done"]
        assert is_done({"volumes": WORKLOAD_VOLUMES, "seen": {"wl-vol1"}}) is False
        assert is_done({"volumes": WORKLOAD_VOLUMES, "seen": set()}) is True
        assert "disconnected from" in kwargs["description"]

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_probe_never_looks_outside_the_workload(
        self, mock_check_response, mock_wait_for
    ):
        """The connection read is scoped to the workload's volumes

        A host still connected to other-vol must not keep a disconnect spinning,
        which it would if the poll read the host's whole connection list.
        """
        mock_array = _mock_array(connected=["other-vol"])
        kwargs = self._wait_kwargs(mock_wait_for, mock_array, False)

        state = kwargs["probe"]()

        mock_array.get_connections.assert_called_once_with(
            host_names=["host1"],
            volume_names=WORKLOAD_VOLUMES,
            context_names=["pod1"],
        )
        # other-vol is not a workload volume, so it cannot appear in seen
        assert state["seen"] == set()
        assert kwargs["is_done"](state) is True

    @patch("plugins.modules.purefa_workload.wait_for")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_probe_rereads_the_volume_set_each_iteration(
        self, mock_check_response, mock_wait_for
    ):
        """A volume that appears late has to be caught, not missed"""
        mock_array = _mock_array()
        kwargs = self._wait_kwargs(mock_wait_for, mock_array, True)

        mock_array.get_volumes.return_value = _mock_volumes_response(["wl-vol1"])
        first = kwargs["probe"]()
        mock_array.get_volumes.return_value = _mock_volumes_response(
            WORKLOAD_VOLUMES + ["wl-vol3"]
        )
        second = kwargs["probe"]()

        assert first["volumes"] == ["wl-vol1"]
        assert second["volumes"] == WORKLOAD_VOLUMES + ["wl-vol3"]

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_timeout_detail_names_the_outstanding_volumes(self, mock_wait_for):
        """A timeout has to say which volumes are on the wrong side"""
        connect = self._wait_kwargs(mock_wait_for, _mock_array(), True)
        assert (
            connect["detail"]({"volumes": WORKLOAD_VOLUMES, "seen": {"wl-vol1"}})
            == "wl-vol2"
        )

        disconnect = self._wait_kwargs(mock_wait_for, _mock_array(), False)
        assert (
            disconnect["detail"]({"volumes": WORKLOAD_VOLUMES, "seen": {"wl-vol1"}})
            == "wl-vol1"
        )


class TestHostConnectionsAreWaitedOn:
    """The host operation is covered by wait, not just the workload"""

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.ConnectionPost")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_connect_waits_for_the_connections(
        self, mock_check_response, mock_connection_post, mock_wait_for_connections
    ):
        """Test _connect_host waits for the connections it just posted"""
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])

        _connect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        mock_wait_for_connections.assert_called_once_with(
            mock_module, mock_array, "test-workload", "pod1", connected=True
        )

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_disconnect_waits_for_the_connections_to_go(
        self, mock_check_response, mock_wait_for_connections
    ):
        """Test _disconnect_host waits for the connections it just deleted"""
        from plugins.modules.purefa_workload import _disconnect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        _disconnect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        mock_wait_for_connections.assert_called_once_with(
            mock_module, mock_array, "test-workload", "pod1", connected=False
        )

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_no_wait_when_nothing_changed(
        self, mock_check_response, mock_wait_for_connections
    ):
        """Nothing was posted, so there is nothing to wait for"""
        from plugins.modules.purefa_workload import _connect_host

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        _connect_host(
            mock_module, mock_array, "test-workload", "pod1", WORKLOAD_VOLUMES
        )

        mock_wait_for_connections.assert_not_called()


class TestVolumeReadsHappenOnce:
    """The volume list is read at most once per run, not once per consumer"""

    @patch("plugins.modules.purefa_workload._wait_for_connections")
    @patch("plugins.modules.purefa_workload.ConnectionPost")
    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_path_reads_volumes_once(
        self,
        mock_wait_for_status,
        mock_check_response,
        mock_connection_post,
        mock_wait_for_connections,
    ):
        """The diff and the facts share one read, unlike the old helpers"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])
        mock_wait_for_status.return_value = _mock_workload()

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        mock_array.get_volumes.assert_called_once()

    @patch("plugins.modules.purefa_workload.check_response")
    def test_rename_path_reads_volumes_once(self, mock_check_response):
        """Only the facts need them here"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(
            name="old-workload", rename="new-workload", context="pod1"
        )
        mock_array = _mock_array()
        mock_array.patch_workloads.return_value = _mock_workload_response(
            name="new-workload"
        )

        rename_workload(mock_module, mock_array, _mock_workload(name="old-workload"))

        mock_array.get_volumes.assert_called_once()
        # Read under the new name, since that is what the workload is called now
        assert (
            mock_array.get_volumes.call_args.kwargs["filter"]
            == "workload.name='new-workload'"
        )

    @patch("plugins.modules.purefa_workload.check_response")
    def test_eradicate_reads_no_volumes(self, mock_check_response):
        """There is no workload left, so there is nothing to describe or read"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", wait=False)
        mock_array = _mock_array()
        mock_array.delete_workloads.return_value = Mock(status_code=200)

        eradicate_workload(mock_module, mock_array)

        mock_array.get_volumes.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True, workload={})


#: Every way this module can change the array. Asserted as a set so a future
#: unguarded write is caught wherever it is added, not just where one is expected.
WRITE_METHODS = (
    "post_volumes",
    "post_workloads",
    "patch_workloads",
    "delete_workloads",
    "post_connections",
    "delete_connections",
)


def _writes(mock_array):
    """Which write endpoints were called, and how often"""
    return {
        method: getattr(mock_array, method).call_count
        for method in WRITE_METHODS
        if getattr(mock_array, method).call_count
    }


class TestCheckModeMakesNoChanges:
    """--check must not touch the array on any path

    The one deliberate exception is the placement recommendation, which is a
    calculation rather than a change and is covered separately.
    """

    def _module(self, **params):
        module = Mock()
        module.check_mode = True
        module.params = _params(**params)
        return module

    @patch("plugins.modules.purefa_workload.VolumePost")
    @patch("plugins.modules.purefa_workload.WorkloadConfigurationReference")
    def test_expand_creates_no_volumes(self, mock_config_ref, mock_volume_post):
        """Test expand posts no volumes under --check

        The regression: _create_volume had no guard, so a --check run of
        volume_count: 3 created three volumes for real.
        """
        mock_module = self._module(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=3,
        )
        mock_array = _mock_array()
        vol_config = Mock()
        vol_config.name = "vol-config1"

        expand_workload(
            mock_module,
            mock_array,
            Mock(),
            [vol_config],
            _mock_workload(context="pod1"),
        )

        assert _writes(mock_array) == {}
        # The change is still reported, it is just not made
        assert mock_module.exit_json.call_args.kwargs["changed"] is True

    def test_create_writes_nothing(self):
        """Test create posts no workload under --check"""
        mock_module = self._module(preset="test-preset", context="pod1")
        mock_array = _mock_array()

        create_workload(mock_module, mock_array, Mock(), Mock(parameters=[]))

        assert _writes(mock_array) == {}

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    def test_delete_writes_nothing(self, mock_workload_patch):
        """Test delete patches nothing under --check"""
        mock_module = self._module(context="pod1")
        mock_array = _mock_array()

        delete_workload(mock_module, mock_array, _mock_workload())

        assert _writes(mock_array) == {}

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    def test_delete_with_eradicate_writes_nothing(self, mock_workload_patch):
        """Test delete + eradicate neither patches nor deletes under --check"""
        mock_module = self._module(context="pod1", eradicate=True)
        mock_array = _mock_array()

        delete_workload(mock_module, mock_array, _mock_workload())

        assert _writes(mock_array) == {}

    def test_eradicate_writes_nothing(self):
        """Test eradicate deletes nothing under --check"""
        mock_module = self._module(context="pod1")
        mock_array = _mock_array()

        eradicate_workload(mock_module, mock_array)

        assert _writes(mock_array) == {}

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    def test_recover_writes_nothing(self, mock_workload_patch):
        """Test recover patches nothing under --check"""
        mock_module = self._module(context="pod1")
        mock_array = _mock_array()

        recover_workload(
            mock_module, mock_array, _mock_workload(status="destroyed", destroyed=True)
        )

        assert _writes(mock_array) == {}

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    def test_rename_writes_nothing(self, mock_workload_patch):
        """Test rename patches nothing under --check"""
        mock_module = self._module(context="pod1", rename="new-workload")
        mock_array = _mock_array()

        rename_workload(mock_module, mock_array, _mock_workload())

        assert _writes(mock_array) == {}

    @patch("plugins.modules.purefa_workload._wait_for_status")
    def test_connect_writes_nothing(self, mock_wait_for_status):
        """Test connecting a host posts no connections under --check"""
        mock_module = self._module(context="pod1", host="host1")
        mock_array = _mock_array(connected=[])
        mock_wait_for_status.return_value = None

        connect_or_disconnect_volumes(
            mock_module, mock_array, "connect", _mock_workload()
        )

        assert _writes(mock_array) == {}
        assert mock_module.exit_json.call_args.kwargs["changed"] is True

    def test_disconnect_writes_nothing(self):
        """Test disconnecting a host deletes no connections under --check"""
        mock_module = self._module(context="pod1", host="host1")
        mock_array = _mock_array(connected=WORKLOAD_VOLUMES)

        connect_or_disconnect_volumes(
            mock_module, mock_array, "disconnect", _mock_workload()
        )

        assert _writes(mock_array) == {}
        assert mock_module.exit_json.call_args.kwargs["changed"] is True


class TestCreateVolumeCheckMode:
    """Test cases for _create_volume under --check"""

    def test_creates_nothing_and_names_nothing(self):
        """No volume was created, so there is no name to return"""
        from plugins.modules.purefa_workload import _create_volume

        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(volume_configuration="vc1", context="pod1")
        mock_array = _mock_array()

        assert _create_volume(mock_module, mock_array) is None
        mock_array.post_volumes.assert_not_called()

    @patch("plugins.modules.purefa_workload.VolumePost")
    @patch("plugins.modules.purefa_workload.WorkloadConfigurationReference")
    @patch("plugins.modules.purefa_workload._wait_for_volumes")
    def test_expand_collects_no_placeholder_names(
        self, mock_wait_for_volumes, mock_config_ref, mock_volume_post
    ):
        """The volume wait must not be handed a list of Nones"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            volume_configuration="vol-config1",
            volume_count=2,
        )
        mock_array = _mock_array()
        workload = _mock_workload(context="pod1")
        mock_wait_for_volumes.return_value = workload
        vol_config = Mock()
        vol_config.name = "vol-config1"

        expand_workload(mock_module, mock_array, Mock(), [vol_config], workload)

        # Nothing was created, so there are no names to wait on - not two Nones
        mock_wait_for_volumes.assert_called_once_with(
            mock_module, mock_array, "pod1", [], workload
        )
        # Only the volumes that already exist can be reported
        assert (
            mock_module.exit_json.call_args.kwargs["workload"]["volumes"]
            == WORKLOAD_VOLUMES
        )


class TestWaitForRecommendation:
    """Test cases for the placement recommendation poll

    Replaces an unbounded `while result.status != "completed"` loop that had no
    timeout, no response check, and no handling of the failed state.
    """

    def _wait_kwargs(self, mock_wait_for, mock_array, check_mode=False):
        from plugins.modules.purefa_workload import _wait_for_recommendation

        mock_module = Mock()
        mock_module.check_mode = check_mode
        mock_module.params = _params(preset="test-fleet:test-preset", context="pod1")

        _wait_for_recommendation(mock_module, mock_array, "pod1", "calc-1")

        return mock_wait_for.call_args.kwargs

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_done_only_on_completed(self, mock_wait_for):
        """processing is not done; completed is"""
        kwargs = self._wait_kwargs(mock_wait_for, _mock_array())

        is_done = kwargs["is_done"]
        assert is_done(Mock(status="processing")) is False
        assert is_done(Mock(status="completed")) is True
        assert kwargs["timeout"] == 300
        assert "test-fleet:test-preset" in kwargs["description"]

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_failed_is_terminal(self, mock_wait_for):
        """A placement that cannot be satisfied fails rather than spinning

        This endpoint is the reason wait_for has an is_failed hook - a workload has
        no failure state, but a recommendation does.
        """
        kwargs = self._wait_kwargs(mock_wait_for, _mock_array())

        is_failed = kwargs["is_failed"]
        assert is_failed(Mock(status="processing")) is None
        assert is_failed(Mock(status="completed")) is None
        message = is_failed(Mock(status="failed"))
        assert message and "test-fleet:test-preset" in message

    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.wait_for")
    def test_probe_checks_the_response(self, mock_wait_for, mock_check_response):
        """The old loop read .items straight off an unchecked response"""
        mock_array = _mock_array()
        mock_array.get_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[_mock_recommendation()]
        )
        kwargs = self._wait_kwargs(mock_wait_for, mock_array)

        kwargs["probe"]()

        mock_array.get_workloads_placement_recommendations.assert_called_once_with(
            names=["calc-1"], context_names=["pod1"]
        )
        mock_check_response.assert_called_once()

    @patch("plugins.modules.purefa_workload.wait_for")
    def test_runs_under_check_mode(self, mock_wait_for):
        """A calculation changes nothing, so --check may wait on it"""
        kwargs = self._wait_kwargs(mock_wait_for, _mock_array(), check_mode=True)

        assert kwargs["skip_in_check_mode"] is False


class TestCheckModePredictsTheRealRun:
    """--check and a real run must agree on the shape of what they return"""

    @patch("plugins.modules.purefa_workload._build_workload_parameters")
    @patch("plugins.modules.purefa_workload.WorkloadPlacementRecommendation")
    @patch("plugins.modules.purefa_workload._wait_for_recommendation")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_check_mode_create_reports_the_recommended_target(
        self,
        mock_check_response,
        mock_wait_for_recommendation,
        mock_recommendation,
        mock_build_workload_parameters,
    ):
        """The headline case, and only reachable because the calculation still runs"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(
            preset="test-preset",
            context="pod1",
            recommendation=True,
            placement="arrayA",
        )
        mock_array = _mock_array()
        calculation = Mock()
        calculation.name = "calc-1"
        mock_array.post_workloads_placement_recommendations.return_value = Mock(
            status_code=200, items=[calculation]
        )
        mock_wait_for_recommendation.return_value = _mock_recommendation("arrayB")

        create_workload(mock_module, mock_array, Mock(), Mock())

        # The calculation ran, so --check can name the array Fusion would choose
        mock_array.post_workloads_placement_recommendations.assert_called_once()
        mock_array.post_workloads.assert_not_called()
        assert mock_module.exit_json.call_args.kwargs["workload"]["context"] == "arrayB"

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    @patch("plugins.modules.purefa_workload._wait_for_status")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_returns_the_same_keys_either_way(
        self, mock_check_response, mock_wait_for_status, mock_workload_patch
    ):
        """A playbook binding to a key must not find it missing in one mode"""
        settled = _mock_workload(status="destroyed", destroyed=True)
        mock_wait_for_status.return_value = settled

        checked = Mock()
        checked.check_mode = True
        checked.params = _params(context="pod1")
        delete_workload(checked, _mock_array(), _mock_workload())

        real = Mock()
        real.check_mode = False
        real.params = _params(context="pod1")
        real_array = _mock_array()
        real_array.patch_workloads.return_value = Mock(status_code=200, items=[settled])
        delete_workload(real, real_array, _mock_workload())

        predicted = checked.exit_json.call_args.kwargs["workload"]
        actual = real.exit_json.call_args.kwargs["workload"]
        assert set(predicted) == set(actual)
        # And on the fields a prediction can be sure of, they agree outright
        for key in ("name", "context", "status", "completed", "destroyed", "host"):
            assert predicted[key] == actual[key], key

    @patch("plugins.modules.purefa_workload.WorkloadPatch")
    @patch("plugins.modules.purefa_workload.check_response")
    def test_delete_with_eradicate_is_empty_either_way(
        self, mock_check_response, mock_workload_patch
    ):
        """The divergence this fixes: --check used to return facts, a real run {}"""
        checked = Mock()
        checked.check_mode = True
        checked.params = _params(context="pod1", eradicate=True)
        delete_workload(checked, _mock_array(), _mock_workload())

        real = Mock()
        real.check_mode = False
        real.params = _params(context="pod1", eradicate=True)
        # The real exit_json terminates, so eradicate_workload's is the only one
        real.exit_json.side_effect = SystemExit(0)
        real_array = _mock_array()
        real_array.patch_workloads.return_value = Mock(
            status_code=200, items=[_mock_workload(destroyed=True)]
        )
        real_array.delete_workloads.return_value = Mock(status_code=200)
        with pytest.raises(SystemExit):
            delete_workload(real, real_array, _mock_workload())

        assert checked.exit_json.call_args.kwargs["workload"] == {}
        assert real.exit_json.call_args.kwargs["workload"] == {}

    @pytest.mark.parametrize(
        "wait,expected_status",
        [(True, "ready"), (False, "creating")],
    )
    def test_predicted_completed_agrees_with_predicted_status(
        self, wait, expected_status
    ):
        """completed is derived, so it can never contradict the status reported"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = _params(preset="test-preset", context="pod1", wait=wait)

        create_workload(mock_module, _mock_array(), Mock(), Mock(parameters=[]))

        facts = mock_module.exit_json.call_args.kwargs["workload"]
        assert facts["status"] == expected_status
        assert facts["completed"] is (expected_status == "ready")


class TestFactsShapeIsDefinedOnce:
    """A read workload and a predicted one must describe themselves identically"""

    def test_read_and_predicted_return_the_same_keys(self):
        """_facts is the single definition, so the two builders cannot drift"""
        from plugins.modules.purefa_workload import _facts, _workload_facts

        mock_module = Mock()
        mock_module.params = _params(preset="test-preset", context="pod1")
        mock_array = _mock_array()

        read = _workload_facts(mock_module, mock_array, _mock_workload(), "pod1")
        predicted_create = _facts(
            mock_module,
            name=mock_module.params["name"],
            context="pod1",
            preset=mock_module.params["preset"],
            status="ready",
        )
        predicted_change = _workload_facts(
            mock_module, mock_array, _mock_workload(), "pod1", destroyed=True
        )

        assert set(read) == set(predicted_create) == set(predicted_change)
        # ...and it is the documented contract, not just self-consistent
        assert set(read) == set(_expected_facts())


class TestPredictedFacts:
    """Test cases for describing a workload that has not been changed yet

    A prediction is expressed by passing changes, so it goes through the same two
    builders a real run does rather than a separate code path.
    """

    def test_create_knows_only_what_it_was_asked_for(self):
        """With no workload to read, params and the clock are all there is"""
        from plugins.modules.purefa_workload import _facts

        mock_module = Mock()
        mock_module.params = _params(
            name="new-workload", preset="test-fleet:test-preset", host="host1"
        )
        mock_array = _mock_array()

        facts = _facts(
            mock_module,
            name=mock_module.params["name"],
            context="arrayB",
            preset=mock_module.params["preset"],
            status="creating",
        )

        assert facts["name"] == "new-workload"
        assert facts["preset"] == "test-fleet:test-preset"
        assert facts["context"] == "arrayB"
        assert facts["host"] == "host1"
        assert facts["destroyed"] is False
        # The array generates volume names, so none can be offered up front
        assert facts["volumes"] == []
        # Nothing was read to find any of this out
        mock_array.get_volumes.assert_not_called()

    def test_change_carries_over_what_it_is_not_changing(self):
        """A prediction built on a real workload keeps that workload's values"""
        from plugins.modules.purefa_workload import _workload_facts

        mock_module = Mock()
        mock_module.params = _params()
        mock_array = _mock_array()
        workload = _mock_workload(
            preset="test-fleet:other-preset", status_details=["still working"]
        )

        facts = _workload_facts(
            mock_module, mock_array, workload, "arrayB", name="renamed"
        )

        # Only the named change applies
        assert facts["name"] == "renamed"
        # ...everything else is the workload as it stands
        assert facts["preset"] == "test-fleet:other-preset"
        assert facts["created"] == CREATED_STR
        assert facts["status_details"] == ["still working"]
        assert facts["status"] == "ready"

    @patch("plugins.modules.purefa_workload._timestamp", return_value=PREDICTED_NOW)
    def test_a_create_predicts_its_own_creation_time(self, mock_timestamp):
        """A workload created now is created now, so null would be the wrong answer"""
        from plugins.modules.purefa_workload import _facts

        mock_module = Mock()
        mock_module.params = _params()

        facts = _facts(
            mock_module,
            name=mock_module.params["name"],
            context="arrayB",
            preset=mock_module.params["preset"],
            status="ready",
        )

        assert facts["created"] == PREDICTED_NOW
        # Called with no argument, meaning "now" rather than an array timestamp
        mock_timestamp.assert_called_once_with()

    def test_completed_cannot_disagree_with_a_predicted_status(self):
        """completed is derived inside _facts, not passed alongside the status"""
        from plugins.modules.purefa_workload import _facts

        mock_module = Mock()
        mock_module.params = _params()

        for status, completed in (
            ("ready", True),
            ("destroyed", True),
            ("creating", False),
            ("destroying", False),
            ("recovering", False),
        ):
            facts = _facts(
                mock_module,
                name=mock_module.params["name"],
                context="arrayB",
                preset=mock_module.params["preset"],
                status=status,
            )
            assert facts["completed"] is completed, status
        # None of those are unrecognised, so nothing was warned about
        mock_module.warn.assert_not_called()


class TestTimestamp:
    """Test cases for the shared timestamp formatter"""

    def test_formats_array_milliseconds_as_utc(self):
        """The array reports epoch milliseconds"""
        from plugins.modules.purefa_workload import _timestamp

        assert _timestamp(CREATED_MS) == CREATED_STR

    def test_defaults_to_now_in_the_documented_format(self):
        """A prediction needs the current time, in the same shape as a real one"""
        import time as time_module
        from plugins.modules.purefa_workload import _timestamp

        result = _timestamp()

        # Parses as the documented format, without pinning the test to the clock
        parsed = time_module.strptime(result, "%Y-%m-%d %H:%M:%S")
        assert parsed.tm_year >= 2025


class TestPlacementIsIgnoredWarning:
    """context and placement are the same thing, so disagreement needs saying"""

    def _run_main(self, mock_ansible_module, mock_get_array, **params):
        from plugins.modules.purefa_workload import main

        mock_module = Mock()
        mock_module.params = _params(
            state="absent", preset="test-preset", volume_count=None, **params
        )
        mock_ansible_module.return_value = mock_module
        mock_array = _mock_array()
        mock_array.get_rest_version.return_value = "2.40"
        mock_fleet = Mock()
        mock_fleet.name = "test-fleet"
        mock_array.get_fleets.return_value = Mock(status_code=200, items=[mock_fleet])
        mock_array.get_arrays.return_value = _mock_get_arrays()
        mock_array.get_workloads.return_value = Mock(status_code=404)
        mock_get_array.return_value = mock_array

        main()

        return mock_module

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_warns_when_they_disagree(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """The placement loses silently today, which is the thing being fixed"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = self._run_main(
            mock_ansible_module, mock_get_array, context="arrayC", placement="arrayB"
        )

        mock_module.warn.assert_called_once()
        warning = mock_module.warn.call_args[0][0]
        assert "arrayB" in warning and "arrayC" in warning
        # The context still wins, as it always has
        assert mock_module.params["context"] == "arrayC"

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_no_warning_when_only_placement_is_given(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """The documented way to use placement, which must stay quiet"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = self._run_main(
            mock_ansible_module, mock_get_array, context="", placement="arrayB"
        )

        mock_module.warn.assert_not_called()
        assert mock_module.params["context"] == "arrayB"

    @patch("plugins.modules.purefa_workload.LooseVersion")
    @patch("plugins.modules.purefa_workload.get_array")
    @patch("plugins.modules.purefa_workload.AnsibleModule")
    @patch("plugins.modules.purefa_workload.HAS_PURESTORAGE", True)
    def test_no_warning_when_they_agree(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Redundant but not contradictory"""
        mock_loose_version.side_effect = lambda x: float(x) if x else 0.0

        mock_module = self._run_main(
            mock_ansible_module, mock_get_array, context="arrayB", placement="arrayB"
        )

        mock_module.warn.assert_not_called()


class TestWaitForCallsMatchTheRealHelper:
    """The module's wait_for calls must match the real helper's signature

    Every other test in this file runs against a mocked api_helpers, so a
    MagicMock accepts any keyword and a renamed or removed wait_for parameter goes
    unnoticed until a playbook hits it. This checks the calls against the real
    signature instead.
    """

    def _real_wait_for_signature(self):
        import importlib.util
        import inspect
        import sys
        import types

        # Import the real module_utils helper, stubbing only what it imports
        package = "ansible_collections.everpure.flasharray.plugins.module_utils"
        saved = {name: sys.modules.get(name) for name in list(sys.modules)}
        version = types.ModuleType(package + ".version")
        version.LooseVersion = str
        sys.modules[package + ".version"] = version
        try:
            spec = importlib.util.spec_from_file_location(
                "_real_api_helpers", "plugins/module_utils/api_helpers.py"
            )
            real = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(real)
            return inspect.signature(real.wait_for)
        finally:
            for name, was in saved.items():
                if was is not None:
                    sys.modules[name] = was

    @patch("plugins.modules.purefa_workload.check_response")
    @patch("plugins.modules.purefa_workload.wait_for")
    def test_every_wait_for_call_binds_against_the_real_signature(
        self, mock_wait_for, mock_check_response
    ):
        """A renamed or removed parameter would raise here, not on a real array"""
        from plugins.modules.purefa_workload import (
            _wait_for_absent,
            _wait_for_connections,
            _wait_for_recommendation,
            _wait_for_status,
            _wait_for_volumes,
        )

        signature = self._real_wait_for_signature()
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = _params(context="pod1", host="host1")
        mock_array = _mock_array()
        mock_array.get_workloads.return_value = _mock_workload_response()
        mock_wait_for.return_value = None

        waiters = [
            lambda: _wait_for_status(mock_module, mock_array, "pod1", "ready"),
            lambda: _wait_for_absent(mock_module, mock_array, "pod1"),
            lambda: _wait_for_connections(
                mock_module, mock_array, "test-workload", "pod1", True
            ),
            lambda: _wait_for_recommendation(mock_module, mock_array, "pod1", "calc-1"),
            lambda: _wait_for_volumes(
                mock_module, mock_array, "pod1", WORKLOAD_VOLUMES, _mock_workload()
            ),
        ]
        for waiter in waiters:
            mock_wait_for.reset_mock()
            waiter()
            args, kwargs = mock_wait_for.call_args
            # Raises TypeError if a keyword no longer exists on the real helper
            signature.bind(*args, **kwargs)

    def test_the_recommendation_opts_out_of_skipping(self):
        """The one waiter that must poll under check mode, spelled the real way"""
        signature = self._real_wait_for_signature()

        assert "skip_in_check_mode" in signature.parameters
        # Skipping is the default, so only the recommendation says otherwise
        assert signature.parameters["skip_in_check_mode"].default is True


class TestFactsDoesNotSubstituteParameters:
    """_facts reports what the array said, including when that is nothing

    name and preset are both nullable on a real workload - the SDK documents a
    destroyed preset as reporting a null name - so defaulting either to the
    requested value would report a parameter as though the array had said it.
    """

    def test_a_null_name_or_preset_stays_null(self):
        """The requested values must not stand in for what was read"""
        from plugins.modules.purefa_workload import _facts

        mock_module = Mock()
        mock_module.params = _params(
            name="requested-name", preset="test-fleet:requested-preset"
        )

        facts = _facts(
            mock_module, context="arrayB", name=None, preset=None, status="ready"
        )

        assert facts["name"] is None
        assert facts["preset"] is None

    def test_the_array_name_wins_over_the_requested_one(self):
        """A workload renamed outside Ansible reports its own name"""
        from plugins.modules.purefa_workload import _facts

        mock_module = Mock()
        mock_module.params = _params(name="requested-name")

        facts = _facts(mock_module, context="arrayB", name="array-name", status="ready")

        assert facts["name"] == "array-name"
