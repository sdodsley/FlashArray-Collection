#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2025, Simon Dodsley (simon@everpuredata.com)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: purefa_workload
version_added: '1.33.0'
short_description: Manage Fusion Fleet Workloads
description:
- Apply/Rename/Delete Fusion fleet workloads
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  context:
    description:
    - Name of fleet member on which to perform the workload operation.
    - This requires the array receiving the request is a member of a fleet
      and the context name to be a member of the same fleet.
    - If not specified, defaults to I(placement) when that is set, otherwise
      to the name of the array receiving the request.
    type: str
    default: ""
  host:
    type: str
    description:
    - Host to connect to the workload after provisioning
    default: ""
  name:
    description:
    - Name of the workload.
    type: str
    required: true
  state:
    description:
    - Define whether to create or delete a fleet workload.
    - Using the expand option will add volume(s) to the workload.
    - If absent is specified together with a host, rather than deleting the workload, the host will be disconnected from the workload
    default: present
    choices: [ absent, present, expand]
    type: str
  preset:
    description:
    - name of existing preset to use as the basis of the workload
    type: str
  rename:
    description:
    - new name for a workload
    type: str
  eradicate:
    description:
    - whether to eradicate a workload
    type: bool
    default: false
  placement:
    description:
    - name of target on which the workload will be deployed
    - Also used as the request context when I(context) is not specified.
    - Ignored when I(recommendation) is true, as the recommended target
      replaces it.
    type: str
  recommendation:
    description:
    - whether to use the Fusion placement recommendation based
      on the workload preset definitions.
    - This will use the first recommended placement if more than
      one is available
    default: false
    type: bool
  parameters:
    description:
    - Parameter values to apply when creating a workload from the preset.
    - Parameters are only applied on the create path and are not applied
      when recovering an existing destroyed workload.
    type: list
    elements: dict
    suboptions:
      name:
        description:
        - Name of the preset parameter to set.
        type: str
        required: true
      value:
        description:
        - Value for the preset parameter.
        - Exactly one of C(string), C(integer), C(boolean), or
          C(resource_reference) must be provided.
        type: dict
        required: true
        suboptions:
          string:
            description:
            - String parameter value.
            type: str
          integer:
            description:
            - Integer parameter value.
            type: int
          boolean:
            description:
            - Boolean parameter value.
            type: bool
          resource_reference:
            description:
            - Reference to another resource.
            type: dict
            suboptions:
              id:
                description:
                - ID of the referenced resource.
                type: str
              name:
                description:
                - Name of the referenced resource.
                type: str
              resource_type:
                description:
                - Optional resource type for the reference.
                type: str
  volume_count:
    description:
    - Number of additional volumes to add to an existing workload
    type: int
  volume_configuration:
    description:
    - Name of the volume configuration to use for adding volumes
      to a workload
    type: str
  wait:
    description:
    - Whether to wait for the array to finish provisioning before returning.
    type: bool
    default: false
    version_added: '1.45.0'
  wait_timeout:
    description:
    - Maximum number of seconds to wait when I(wait) is true.
    - The task fails if the array has not finished within this time.
    type: int
    default: 300
    version_added: '1.45.0'
extends_documentation_fragment:
- everpure.flasharray.everpure.fa
"""

EXAMPLES = r"""
- name: Create a workload using an existing preset on a specific placement target and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    host: myhost
    placement: arrayB
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Create a workload using an existing preset using the recommended target and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    host: myhost
    recommendation: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Create a workload on the recommended target, waiting for it to be ready
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    recommendation: true
    wait: true
    wait_timeout: 600
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
  register: new_workload

- name: Report the fleet member Fusion placed the workload on
  ansible.builtin.debug:
    msg: "{{ new_workload.workload.name }} placed on {{ new_workload.workload.context }}"

- name: Create a workload using preset parameters
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    context: arr1
    parameters:
      - name: replication_target
        value:
          resource_reference:
            name: arr2
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Add volumes to workload foo based on volume configuration fin and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    volume_configuration: fin
    volume_count: 3
    host: myhost
    state: expand
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Rename an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    rename: bar
    state: rename
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Disconnect an existing workload from host
  everpure.flasharray.purefa_workload:
    name: foo
    host: myhost
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Delete an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Eradicate an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: absent
    eradicate: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Recover a deleted workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: present
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Reconnect an existing workload to a host
  everpure.flasharray.purefa_workload:
    name: foo
    host: myhost
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
workload:
    description: A dictionary describing the workload. Returned on every action
        that leaves a workload in place. Empty only when there is genuinely no
        workload to describe - after eradication, or in check mode for a create
        that has not happened.
    type: dict
    returned: success
    contains:
        name:
            description: Name of the workload. This is the new name after a
                rename.
            type: str
            sample: 'foo'
        context:
            description: Name of the fleet member the workload is placed on.
                When I(recommendation) is used this is the target chosen by
                Fusion, which is not knowable before the task runs.
            type: str
            sample: 'arrayB'
        preset:
            description: Fleet-qualified name of the preset the workload was
                deployed from. The name is null if the preset has since been
                destroyed.
            type: str
            sample: 'fleet1:bar'
        status:
            description: Status of the workload, as reported by the array.
                Normally one of C(creating), C(ready), C(destroying),
                C(destroyed), C(eradicating) or C(recovering). Passed through
                unmodified, so a future Purity release may report a value not in
                this list. Use I(completed) to test for completion rather than
                comparing this field.
            type: str
            sample: 'ready'
        completed:
            description: Whether the array has finished the operation in flight
                for this workload. A destroyed workload is complete but still pending
                eradication - see I(time_remaining).
            type: bool
            sample: false
        status_details:
            description: Human-readable diagnostics from the array, such as
                which resources are still being created. Free-form, with no
                stable format. Do not parse.
            type: list
            elements: str
            sample: ['creating volume foo-vol1']
        destroyed:
            description: Whether deletion of the workload has been requested.
                This says nothing about whether the deletion has finished - see
                I(completed).
            type: bool
            sample: false
        created:
            description: Workload creation time, in UTC.
            type: str
            sample: '2025-08-07 17:20:11'
        time_remaining:
            description: Milliseconds until a destroyed workload is eradicated.
                Null unless I(destroyed) is true.
            type: int
            sample: 86400000
"""

HAS_PURESTORAGE = True
try:
    from pypureclient.flasharray import (
        WorkloadConfigurationReference,
        WorkloadParameter,
        WorkloadParameterValue,
        WorkloadParameterValueResourceReference,
        WorkloadPatch,
        WorkloadPost,
        WorkloadPlacementRecommendation,
        VolumePost,
        ConnectionPost,
    )
except ImportError:
    HAS_PURESTORAGE = False

import time
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.everpure.flasharray.plugins.module_utils.purefa import (
    get_array,
    purefa_argument_spec,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.version import (
    LooseVersion,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers import (
    check_response,
    wait_for,
)

VERSION = 1.5
USER_AGENT_BASE = "Ansible"
MIN_REQUIRED_API_VERSION = "2.40"
SUPPORTED_PARAMETER_VALUE_TYPES = (
    "string",
    "integer",
    "boolean",
    "resource_reference",
)

# The API reports exactly these six statuses. Only two are terminal. There is NO
# failure state, so a broken provision is indistinguishable from a slow one and
# is caught by wait_timeout rather than reported as a failure.
TERMINAL_STATUSES = frozenset({"ready", "destroyed"})
TRANSIENT_STATUSES = frozenset({"creating", "destroying", "eradicating", "recovering"})


def _parameter_fail(module, parameter_name, message):
    module.fail_json(msg=f"Invalid workload parameter '{parameter_name}': {message}")


def _coerce_parameter_list(parameter_items):
    if parameter_items is None:
        return []
    try:
        return list(parameter_items)
    except TypeError:
        return []


def _supplied_option_keys(value_definition, allowed_keys):
    return [
        key
        for key in allowed_keys
        if key in value_definition and value_definition[key] is not None
    ]


def _build_resource_reference(module, parameter_name, resource_reference):
    if not isinstance(resource_reference, dict):
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference must be a dictionary",
        )
    unknown_keys = set(resource_reference) - {"id", "name", "resource_type"}
    if unknown_keys:
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference contains unsupported keys: {0}".format(
                ", ".join(sorted(unknown_keys))
            ),
        )
    identifier_keys = _supplied_option_keys(resource_reference, ("id", "name"))
    if len(identifier_keys) != 1:
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference must include exactly one of id or name",
        )
    return WorkloadParameterValueResourceReference(
        **{
            key: resource_reference[key]
            for key in resource_reference
            if resource_reference[key] is not None
        }
    )


def _build_parameter_value(module, parameter_name, value_definition):
    if not isinstance(value_definition, dict):
        _parameter_fail(module, parameter_name, "value must be a dictionary")
    unknown_keys = set(value_definition) - set(SUPPORTED_PARAMETER_VALUE_TYPES)
    if unknown_keys:
        _parameter_fail(
            module,
            parameter_name,
            "value contains unsupported keys: {0}".format(
                ", ".join(sorted(unknown_keys))
            ),
        )
    supplied_value_types = _supplied_option_keys(
        value_definition, SUPPORTED_PARAMETER_VALUE_TYPES
    )
    if len(supplied_value_types) != 1:
        _parameter_fail(
            module,
            parameter_name,
            "value must include exactly one of {0}".format(
                ", ".join(SUPPORTED_PARAMETER_VALUE_TYPES)
            ),
        )

    value_type = supplied_value_types[0]
    normalized_value = value_definition[value_type]
    if value_type == "string":
        if not isinstance(normalized_value, str):
            _parameter_fail(module, parameter_name, "string value must be a string")
    elif value_type == "integer":
        if isinstance(normalized_value, bool) or not isinstance(normalized_value, int):
            _parameter_fail(module, parameter_name, "integer value must be an integer")
    elif value_type == "boolean":
        if not isinstance(normalized_value, bool):
            _parameter_fail(
                module, parameter_name, "boolean value must be true or false"
            )
    elif value_type == "resource_reference":
        normalized_value = _build_resource_reference(
            module, parameter_name, normalized_value
        )

    return value_type, WorkloadParameterValue(**{value_type: normalized_value})


def _build_workload_parameters(module, preset_config):
    raw_parameters = module.params.get("parameters") or []
    if not raw_parameters:
        return None

    preset_parameters = {}
    for preset_parameter in _coerce_parameter_list(
        getattr(preset_config, "parameters", [])
    ):
        if getattr(preset_parameter, "name", None):
            preset_parameters[preset_parameter.name] = preset_parameter

    normalized_parameters = []
    seen_parameters = set()
    for raw_parameter in raw_parameters:
        if not isinstance(raw_parameter, dict):
            module.fail_json(msg="Each workload parameter must be a dictionary")
        parameter_name = raw_parameter.get("name")
        if not parameter_name:
            module.fail_json(msg="Each workload parameter requires a name")
        if parameter_name in seen_parameters:
            _parameter_fail(module, parameter_name, "parameter names must be unique")
        if parameter_name not in preset_parameters:
            _parameter_fail(
                module,
                parameter_name,
                "parameter is not defined by preset {0}".format(
                    module.params["preset"]
                ),
            )
        if "value" not in raw_parameter:
            _parameter_fail(module, parameter_name, "parameter requires a value")

        value_type, parameter_value = _build_parameter_value(
            module, parameter_name, raw_parameter["value"]
        )
        preset_type = getattr(preset_parameters[parameter_name], "type", None)
        if preset_type and preset_type != value_type:
            _parameter_fail(
                module,
                parameter_name,
                "expected type {0}, got {1}".format(preset_type, value_type),
            )

        normalized_parameters.append(
            WorkloadParameter(name=parameter_name, value=parameter_value)
        )
        seen_parameters.add(parameter_name)
    return normalized_parameters


def _workload_completed(module, workload):
    """True when the array has no operation in flight for this workload.

    Anything unrecognised counts as in-flight, so a status added by a future
    Purity release can never be mistaken for success.
    """
    status = getattr(workload, "status", None)
    if status in TERMINAL_STATUSES:
        return True
    if status not in TRANSIENT_STATUSES:
        module.warn(
            f"Workload {workload.name} reported unrecognised status {status!r}. "
            f"Treating as in progress. This collection may need updating."
        )
    return False


def _workload_facts(module, workload):
    """Build the flat fact dict for a Workload object

    Takes an already-fetched Workload and performs no I/O. Returns an empty dict
    only when there is no workload to describe at all.
    """
    if not workload:
        return {}
    return {
        "name": workload.name,
        "context": workload.context.name,
        "preset": workload.preset.name,
        "status": workload.status,
        "completed": _workload_completed(module, workload),
        "status_details": workload.status_details,
        "destroyed": workload.destroyed,
        "time_remaining": getattr(workload, "time_remaining", None),
        "created": time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.gmtime(workload.created / 1000),
        ),
    }


def _read_workload(module, array, context):
    """Read the workload in the given context, or None if it does not exist"""
    res = array.get_workloads(names=[module.params["name"]], context_names=[context])
    if res.status_code == 404:
        return None
    check_response(res, module, f"Failed to read workload {module.params['name']}")
    return list(res.items)[0]


def _status_detail(workload):
    """Render the array's own diagnostics for a timeout message"""
    if not workload:
        return ""
    return ", ".join(getattr(workload, "status_details", None) or [])


def _wait_for_status(module, array, context, status):
    """Wait until the workload has settled into the given status

    The context is passed in rather than read from module.params, so that a
    recommendation-resolved placement stays fixed for the life of the poll.
    """
    return wait_for(
        module,
        probe=lambda: _read_workload(module, array, context),
        is_done=lambda workload: (
            workload is not None
            and _workload_completed(module, workload)
            and workload.status == status
        ),
        timeout=module.params["wait_timeout"],
        description=f"workload {module.params['name']} to become {status}",
        detail=_status_detail,
    )


def _wait_for_absent(module, array, context):
    """Wait until the workload has been fully eradicated

    Done here is the absence of a status rather than a value of one, so this is
    the one path that cannot use _workload_completed().
    """
    return wait_for(
        module,
        probe=lambda: _read_workload(module, array, context),
        is_done=lambda workload: workload is None,
        timeout=module.params["wait_timeout"],
        description=f"workload {module.params['name']} to be eradicated",
        detail=_status_detail,
    )


def _wait_for_volumes(module, array, context, volume_names):
    """Wait until new volumes exist and the workload has settled back to ready

    Volumes carry no lifecycle status of their own, so the volume half of this
    can only test existence, and the POST that created them has already
    returned. The workload half is what covers the configuration the preset
    derives from those volumes.
    """

    def probe():
        res = array.get_volumes(names=volume_names, context_names=[context])
        # A name that does not resolve yet is an error rather than an empty
        # result, and here means "not created yet" rather than a real failure
        found = (
            {volume.name for volume in list(res.items)}
            if res.status_code == 200
            else set()
        )
        return {"workload": _read_workload(module, array, context), "volumes": found}

    def is_done(state):
        workload = state["workload"]
        return (
            not set(volume_names) - state["volumes"]
            and workload is not None
            and _workload_completed(module, workload)
            and workload.status == "ready"
        )

    state = wait_for(
        module,
        probe=probe,
        is_done=is_done,
        timeout=module.params["wait_timeout"],
        description=(
            f"volumes added to workload {module.params['name']} to become ready"
        ),
        detail=lambda state: _status_detail(state["workload"]),
    )
    return state["workload"] if state else None


def _create_volume(module, array):
    """Create an actual volume in a workload

    Returns the array-generated volume name, so that a later wait can target
    exactly the volumes this task created.
    """
    res = array.post_volumes(
        volume=VolumePost(
            workload=WorkloadConfigurationReference(
                name=module.params["name"],
                configuration=module.params["volume_configuration"],
            ),
        ),
        context_names=[module.params["context"]],
    )
    check_response(res, module, "Workload volume creation failed")
    return list(res.items)[0].name


def _disconnect_volumes(module, array):
    """Disconnect host from volumes in the workload"""
    volumes = list(
        array.get_volumes(
            filter="workload.name='{0}'".format(module.params["name"]),
            context_names=[module.params["context"]],
        ).items
    )
    volNames = [vol.name for vol in volumes]

    res = array.delete_connections(
        host_names=[module.params["host"]],
        context_names=[module.params["context"]],
        volume_names=volNames,
    )
    check_response(res, module, "Failed to disconnect volumes from host")


def _connect_volumes(module, array):
    """Connect host to volumes in the workload"""
    volumes = list(
        array.get_volumes(
            filter="workload.name='{0}'".format(module.params["name"]),
            context_names=[module.params["context"]],
        ).items
    )
    volNames = [vol.name for vol in volumes]

    res = array.post_connections(
        host_names=[module.params["host"]],
        context_names=[module.params["context"]],
        volume_names=volNames,
        connection=ConnectionPost(),
    )
    check_response(res, module, "Failed to connect volumes to host")


def create_workload(module, array, fleet, preset_config):
    """Create fleet workload using existing preset"""
    changed = True
    workload_parameters = _build_workload_parameters(module, preset_config)
    if module.params["recommendation"]:
        # Start the workload calculation for the preset being used
        res = array.post_workloads_placement_recommendations(
            inputs=WorkloadPlacementRecommendation(parameters=workload_parameters),
            preset_names=[module.params["preset"]],
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Recommendation calculation failure")
        workload_calc = list(res.items)[0].name
        # Wait for the workload calculation to complete
        result = list(
            array.get_workloads_placement_recommendations(
                names=[workload_calc], context_names=[module.params["context"]]
            ).items
        )[0]
        while result.status != "completed":
            time.sleep(1)
            result = list(
                array.get_workloads_placement_recommendations(
                    names=[workload_calc], context_names=[module.params["context"]]
                ).items
            )[0]
        # Replace any defined placement with the result from the recommendation
        module.params["placement"] = result.results[0].placements[0].targets[0].name
        module.params["context"] = module.params["placement"]
    workload_facts = {}
    if not module.check_mode:
        res = array.post_workloads(
            names=[module.params["name"]],
            preset_names=[module.params["preset"]],
            workload=WorkloadPost(parameters=workload_parameters),
            context_names=[module.params["context"]],
        )
        check_response(
            res, module, f"Failed to create workload {module.params['name']}"
        )
        workload = list(res.items)[0]
        if module.params["wait"]:
            workload = _wait_for_status(
                module, array, module.params["context"], "ready"
            )
        workload_facts = _workload_facts(module, workload)
        if module.params["host"] != "":
            _connect_volumes(module, array)

    module.exit_json(changed=changed, workload=workload_facts)


def expand_workload(module, array, fleet, volume_configs, workload):
    """Add new volumes to workload"""
    changed = False
    volume_names = []
    for vol_config in volume_configs:
        if vol_config.name == module.params["volume_configuration"]:
            for x in range(module.params["volume_count"]):
                changed = True
                volume_names.append(_create_volume(module, array))
    if not changed:
        module.fail_json(
            msg="Volume Configuration {0} does not exist for preset {1}.".format(
                module.params["volume_configuration"], module.params["preset"]
            )
        )
    if module.params["wait"] and not module.check_mode:
        # Re-read rather than reuse main()'s workload, which predates the volumes
        workload = _wait_for_volumes(
            module, array, module.params["context"], volume_names
        )
    if module.params["host"] != "":
        _connect_volumes(module, array)

    # Without a wait this is still main()'s pre-expand read, which is accurate
    # because only the workload's volumes changed here
    module.exit_json(changed=changed, workload=_workload_facts(module, workload))


def delete_workload(module, array, workload=None):
    """Delete the workload"""
    changed = True
    # In check mode nothing is sent, so the pre-delete state is the last known
    workload_facts = _workload_facts(module, workload)
    if not module.check_mode:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(destroyed=True),
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Workload deletion failed")
        # The PATCH response reports destroyed=True and the time_remaining
        # countdown until eradication, so use it rather than the pre-delete read
        deleted = list(res.items)[0]
        if module.params["wait"]:
            deleted = _wait_for_status(
                module, array, module.params["context"], "destroyed"
            )
        workload_facts = _workload_facts(module, deleted)
        if module.params["eradicate"]:
            eradicate_workload(module, array)
    module.exit_json(changed=changed, workload=workload_facts)


def eradicate_workload(module, array):
    """Eradicate the workload"""
    changed = True
    if not module.check_mode:
        res = array.delete_workloads(
            names=[module.params["name"]],
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Workload eradication failed")
        if module.params["wait"]:
            _wait_for_absent(module, array, module.params["context"])
    # The workload no longer exists, so there is nothing to describe
    module.exit_json(changed=changed, workload={})


def recover_workload(module, array, workload=None):
    """Recover the workload and optionally reconnect to host"""
    changed = True
    # In check mode nothing is sent, so the destroyed state is the last known
    workload_facts = _workload_facts(module, workload)
    if not module.check_mode:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(destroyed=False),
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Workload recovery failed")
        recovered = list(res.items)[0]
        if module.params["wait"]:
            recovered = _wait_for_status(
                module, array, module.params["context"], "ready"
            )
        workload_facts = _workload_facts(module, recovered)
        if module.params["host"] != "":
            _connect_volumes(module, array)

    module.exit_json(changed=changed, workload=workload_facts)


def rename_workload(module, array, workload=None):
    """Rename the workload

    Nothing about a rename is asynchronous, so wait does not apply.
    """
    changed = True
    # In check mode nothing is sent, so the workload still has its old name
    workload_facts = _workload_facts(module, workload)
    if not module.check_mode:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(name=module.params["rename"]),
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Workload rename failed")
        # Reports the new name, as returned by the PATCH response
        workload_facts = _workload_facts(module, list(res.items)[0])
    module.exit_json(changed=changed, workload=workload_facts)


def connect_or_disconnect_volumes(module, array, mode, workload):
    """Connect or disconnect volumes in the workload to a host"""
    changed = False

    res = array.get_connections(
        host_names=[module.params["host"]],
        context_names=[module.params["context"]],
    )
    check_response(
        res, module, f"Failed to get volume connection for host {module.params['host']}"
    )
    volume_connections = [conn.volume.name for conn in list(res.items)]

    res = array.get_volumes(
        filter="workload.name='{0}'".format(module.params["name"]),
        context_names=[module.params["context"]],
    )
    check_response(
        res, module, f"Failed to get volumes for workload {module.params['name']}"
    )
    volumes = list(res.items)

    if mode == "connect":
        for volume in volumes:
            if volume.name not in volume_connections:
                changed = True
    elif mode == "disconnect":
        for volume in volumes:
            if volume.name in volume_connections:
                changed = True

    if not module.check_mode and changed:
        if mode == "connect":
            _connect_volumes(module, array)
        elif mode == "disconnect":
            _disconnect_volumes(module, array)

    # Only host connections change here, not the workload itself
    module.exit_json(changed=changed, workload=_workload_facts(module, workload))


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            name=dict(type="str", required=True),
            state=dict(
                type="str",
                default="present",
                choices=["absent", "present", "expand"],
            ),
            preset=dict(type="str"),
            rename=dict(type="str"),
            eradicate=dict(type="bool", default=False),
            placement=dict(type="str"),
            parameters=dict(
                type="list",
                elements="dict",
                options=dict(
                    name=dict(type="str", required=True),
                    value=dict(
                        type="dict",
                        required=True,
                        options=dict(
                            string=dict(type="str"),
                            integer=dict(type="int"),
                            boolean=dict(type="bool"),
                            resource_reference=dict(
                                type="dict",
                                options=dict(
                                    id=dict(type="str"),
                                    name=dict(type="str"),
                                    resource_type=dict(type="str"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            volume_count=dict(type="int"),
            volume_configuration=dict(type="str"),
            recommendation=dict(type="bool", default=False),
            context=dict(type="str", default=""),
            host=dict(type="str", default=""),
            # Deliberately not in purefa_argument_spec(), which would land these
            # on every module in the collection
            wait=dict(type="bool", default=False),
            wait_timeout=dict(type="int", default=300),
        )
    )

    required_if = [["state", "expand", ["volume_count", "volume_configuration"]]]

    module = AnsibleModule(
        argument_spec, supports_check_mode=True, required_if=required_if
    )

    if not HAS_PURESTORAGE:
        module.fail_json(msg="py-pure-client sdk is required for this module")

    array = get_array(module)
    api_version = array.get_rest_version()
    if LooseVersion(MIN_REQUIRED_API_VERSION) > LooseVersion(api_version):
        module.fail_json(
            msg="FlashArray REST version not supported. "
            "Minimum version required: {0}".format(MIN_REQUIRED_API_VERSION)
        )
    state = module.params["state"]
    if module.params["volume_count"] and module.params["volume_count"] <= 0:
        module.fail_json(msg="volume_count must be a positive integer.")
    fleet_res = array.get_fleets()
    fleet_items = list(fleet_res.items) if fleet_res.status_code == 200 else []
    if not fleet_items:
        module.fail_json(
            msg="purefa_workload requires a Fusion fleet environment, but this "
            "array is not a member of a fleet."
        )
    fleet = fleet_items[0].name
    if not module.params["context"]:
        # No context given: route the request via the placement target if one was
        # named, otherwise via the local array. This module already requires a
        # fleet, so the local array is always a valid fleet context. An empty
        # context is rejected by the array with an internal error.
        module.params["context"] = (
            module.params["placement"] or list(array.get_arrays().items)[0].name
        )

    workload_destroyed = False
    workload_exists = False
    workload = None
    preset_config = {}
    # Update preset name with fleet prefix
    module.params["preset"] = fleet + ":" + module.params["preset"]
    res = array.get_workloads(
        names=[module.params["name"]], context_names=[module.params["context"]]
    )
    if res.status_code == 200:
        workload_exists = True
        workload = list(res.items)[0]
        workload_destroyed = workload.destroyed

    if (state == "present" and not workload_destroyed and not workload_exists) or (
        state == "expand" and not workload_destroyed
    ):
        res = array.get_presets_workload(
            names=[module.params["preset"]],
        )
        check_response(
            res,
            module,
            f"Preset {module.params['preset']} does not exist in fleet {fleet}",
        )
        preset_config = list(res.items)[0]
    if (
        state == "present"
        and workload_exists
        and module.params["rename"]
        and not workload_destroyed
    ):
        rename_workload(module, array, workload)
    elif state == "present" and not workload_exists:
        create_workload(module, array, fleet, preset_config)
    elif state == "expand" and workload_exists and not workload_destroyed:
        expand_workload(
            module, array, fleet, preset_config.volume_configurations, workload
        )
    elif state == "present" and workload_exists and workload_destroyed:
        recover_workload(module, array, workload)
    elif (
        state == "present"
        and workload_exists
        and not workload_destroyed
        and module.params["host"] != ""
    ):
        connect_or_disconnect_volumes(module, array, "connect", workload)
    elif (
        state == "absent"
        and workload_exists
        and not workload_destroyed
        and module.params["host"] != ""
    ):
        connect_or_disconnect_volumes(module, array, "disconnect", workload)
    elif state == "absent" and workload_exists and not workload_destroyed:
        delete_workload(module, array, workload)
    elif state == "absent" and workload_destroyed and module.params["eradicate"]:
        eradicate_workload(module, array)
    else:
        module.exit_json(changed=False, workload=_workload_facts(module, workload))


if __name__ == "__main__":
    main()
