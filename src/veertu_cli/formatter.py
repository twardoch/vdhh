import json
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union, Tuple

import click
from tabulate import tabulate


# Using TypeAlias for complex types if available (Python 3.10+)
# from typing import TypeAlias
# DictStrAny = TypeAlias(Dict[str, Any])
# ListDictStrAny = TypeAlias(List[Dict[str, Any]])

# For older Python versions:
DictStrAny = Dict[str, Any]
ListDictStrAny = List[Dict[str, Any]]


class AbstractFormatter(object):

    def format_list_output(self, vms_list: ListDictStrAny) -> None:
        pass

    def format_show_output(self, vm_info: DictStrAny) -> None:
        pass

    def format_start_output(self, result: bool, restart: bool = False, vm_id: Optional[str] = None) -> None:
        pass

    def format_pause_output(self, result: bool, vm_id: Optional[str]) -> None:
        pass

    def format_shutdown_output(self, result: bool, vm_id: Optional[str]) -> None:
        pass

    def format_reboot_output(self, result: bool, vm_id: Optional[str]) -> None:
        pass

    def format_delete_output(self, result: bool, vm_id: Optional[str]) -> None:
        pass

    def format_vm_not_exist(self) -> None:
        pass

    def echo_status_ok(self, message: str = '') -> None:
        pass

    def echo_status_failure(self, message: str = '') -> None:
        pass

    def format_properties_changed(self, succeeded: DictStrAny, failed: DictStrAny) -> None:
        pass

    def format_added_port_forwarding_rule(self, result: bool) -> None:
        pass

    def format_deleted_port_forwarding_rule(self, result: bool) -> None:
        pass

    def format_describe(self, vm_dict: DictStrAny) -> None:
        pass

    def format_create(self, new_uuid: Optional[str]) -> None: # Changed 'success' to 'new_uuid' for clarity
        pass

    def format_add_network_card(self, success: bool) -> None:
        pass

    def format_delete_network_card(self, success: bool) -> None:
        pass


class CliFormatter(AbstractFormatter):

    def format_list_of_dicts(self, list_of_dicts: ListDictStrAny) -> str:
        if isinstance(list_of_dicts, list) and len(list_of_dicts) > 0:
            # Ensure all keys are strings for headers
            headers = {str(k): str(k) for k in list_of_dicts[0].keys()}
            # Ensure all values are suitable for tabulate (mostly strings)
            safe_list_of_dicts = []
            for row_dict in list_of_dicts:
                safe_row = {str(k): str(v) if v is not None else "" for k, v in row_dict.items()}
                safe_list_of_dicts.append(safe_row)
            return tabulate(safe_list_of_dicts, headers=headers, tablefmt='grid')
        return ""

    def format_dict(self, dict_to_output: DictStrAny) -> str:
        output = ''
        data: List[Tuple[str, str]] = [] # Explicitly type 'data'
        additionals: Dict[str, Union[str, DictStrAny, ListDictStrAny]] = {}

        if not isinstance(dict_to_output, dict):
            return ""

        for k, v in dict_to_output.items():
            key_str = str(k) # Ensure key is string
            if isinstance(v, str):
                data.append((key_str, v))
            elif isinstance(v, (dict, OrderedDict)):
                additionals[key_str] = v # Store as is, will be formatted recursively or by format_list_of_dicts
            elif isinstance(v, list):
                if len(v) > 0 and isinstance(v[0], (dict, OrderedDict)):
                    # This list contains dicts, format it as a table string
                    additionals[key_str] = self.format_list_of_dicts(v)
                else:
                    data.append((key_str, ', '.join(map(str, v))))
            else:
                data.append((key_str, str(v)))

        if data: # Only call tabulate if data is not empty
            output += tabulate(data, tablefmt='grid')
            output += '\n\n'

        for k, v_item in additionals.items():
            output += k + "\n\n"
            if isinstance(v_item, dict): # This should be DictStrAny from earlier check
                output += self.format_dict(v_item)
            elif isinstance(v_item, str): # This means it's already formatted list of dicts
                 output += v_item
            # Note: if v_item is ListDictStrAny, it's an unhandled case here,
            # but format_list_of_dicts should have turned it into a string.
            output += '\n\n'
        return output

    def format_list_output(self, vms_list: ListDictStrAny) -> None:
        click.echo('list of vms:')
        output = self.format_list_of_dicts(vms_list)
        click.echo(output)

    def format_show_output(self, vm_info: DictStrAny) -> None:
        output = self.format_dict(vm_info)
        click.echo(output)

    def format_port_forwarding_info(self, info: ListDictStrAny) -> None:
        click.echo(self.format_list_of_dicts(info))

    def format_start_output(self, result: bool, restart: bool = False, vm_id: Optional[str] = None) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            if restart:
                click.echo(f"VM {vm_id_str} successfully restarted")
            else:
                click.echo(f"VM {vm_id_str} successfully started")
        else:
            if restart:
                click.echo(f"VM {vm_id_str} failed to restart", err=True)
            else:
                click.echo(f"VM {vm_id_str} failed to start", err=True)

    def format_pause_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            click.echo(f"VM {vm_id_str} paused")
        else:
            click.echo(f"VM {vm_id_str} failed to pause", err=True)

    def format_shutdown_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            click.echo(f"VM {vm_id_str} is shutting down")
        else:
            click.echo(f"VM {vm_id_str} was unable to shut down (you can try with --force)", err=True)

    def format_reboot_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            click.echo(f"VM {vm_id_str} is rebooting")
        else:
            click.echo(f"VM {vm_id_str} was unable to reboot (you can try with --force)", err=True)

    def format_delete_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            click.echo(f"VM {vm_id_str} deleted successfully")
        else:
            click.echo(f"Unable to delete VM {vm_id_str} ", err=True)

    def format_vm_not_exist(self) -> None:
        click.echo('vm does not exist')

    def echo_status_ok(self, message: str = '') -> None:
        click.echo('OK')
        if message:
            click.echo(message)

    def echo_status_failure(self, message: str = '') -> None:
        click.echo('Action Failed')
        if message:
            click.echo(message)

    def format_properties_changed(self, succeeded: DictStrAny, failed: DictStrAny) -> None:
        if succeeded:
            click.echo("the following properties were set successfully:")
            for k, v in succeeded.items():
                click.echo(f"{k} set to {str(v)}")
        if failed:
            click.echo('the following properties failed to set:')
            for k, v in failed.items():
                click.echo(f"{k} to {str(v)}")

    def format_added_port_forwarding_rule(self, result: bool) -> None:
        if result:
            click.echo('rule added successfully')
        else:
            click.echo('could not add port forwarding', err=True)

    def format_deleted_port_forwarding_rule(self, result: bool) -> None:
        if result:
            click.echo('rule deleted successfully')
        else:
            click.echo('could not delete port forwarding', err=True)

    def format_describe(self, vm_dict: DictStrAny) -> None:
        click.echo(self.format_dict(vm_dict))

    def format_create(self, new_uuid: Optional[str]) -> None:
        if new_uuid:
            click.echo(f'vm created successfully new uuid: {new_uuid}')
        else:
            click.echo('could not create vm')

    def format_add_network_card(self, success: bool) -> None:
        if success:
            click.echo('successfully added network card')
        else:
            click.echo('could not add network card')

    def format_delete_network_card(self, success: bool) -> None:
        if success:
            click.echo('successfully deleted network card')
        else:
            click.echo('could not delete network card')


class JsonFormatter(AbstractFormatter):

    def _make_response(self, status: str = "OK", body: DictStrAny = {}, message: str = '') -> DictStrAny:
        response: DictStrAny = {
            'status': status,
            'body': body,
            'message': message
        }
        return response

    def _format_to_json(self, response: DictStrAny) -> str:
        return json.dumps(response)

    def echo_response(self, body: DictStrAny = {}, status: str = 'OK', message: str = '', err: bool = False) -> None:
        if err:
            status = "ERROR"
        # Ensure body is a valid dict for _make_response
        current_body = body if isinstance(body, dict) else {}
        response_dict = self._make_response(status=status, body=current_body, message=message)
        click.echo(self._format_to_json(response_dict))

    def format_list_output(self, vms_list: ListDictStrAny) -> None:
        self.echo_response(body={'vms': vms_list}) # Wrap list in a dict for consistent body structure

    def format_show_output(self, vm_info: DictStrAny) -> None:
        self.echo_response(body=vm_info)

    def format_port_forwarding_info(self, info: ListDictStrAny) -> None:
        self.echo_response(body={'port_forwarding_rules': info})

    def format_start_output(self, result: bool, restart: bool = False, vm_id: Optional[str] = None) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            if restart:
                self.echo_response(message=f"VM {vm_id_str} successfully restarted")
            else:
                self.echo_response(message=f"VM {vm_id_str} successfully started")
        else:
            if restart:
                self.echo_response(message=f"VM {vm_id_str} failed to restart", err=True)
            else:
                self.echo_response(message=f"VM {vm_id_str} failed to start", err=True)

    def format_pause_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            self.echo_response(message=f"VM {vm_id_str} paused")
        else:
            self.echo_response(message=f"VM {vm_id_str} failed to pause", err=True)

    def format_shutdown_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            self.echo_response(message=f"VM {vm_id_str} is shutting down")
        else:
            self.echo_response(message=f"VM {vm_id_str} was unable to shut down (you can try with --force)", err=True)

    def format_reboot_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            self.echo_response(message=f"VM {vm_id_str} is rebooting")
        else:
            self.echo_response(message=f"VM {vm_id_str} was unable to reboot (you can try with --force)", err=True)

    def format_delete_output(self, result: bool, vm_id: Optional[str]) -> None:
        vm_id_str = vm_id if vm_id is not None else "Unknown VM"
        if result:
            self.echo_response(message=f"VM {vm_id_str} deleted successfully")
        else:
            self.echo_response(message=f"Unable to delete VM {vm_id_str} ", err=True)

    def format_vm_not_exist(self) -> None:
        self.echo_response(message="vm does not exist", err=True)

    def echo_status_ok(self, message: str = '') -> None:
        self.echo_response(message=message)

    def echo_status_failure(self, message: str = '') -> None:
        self.echo_response(err=True, message=message)

    def format_properties_changed(self, succeeded: DictStrAny, failed: DictStrAny) -> None:
        self.echo_response(body={'succeeded': succeeded, 'failed': failed})

    def format_added_port_forwarding_rule(self, result: bool) -> None:
        if result:
            self.echo_status_ok(message='rule added successfully')
        else:
            self.echo_status_failure(message='could not add port forwarding')

    def format_deleted_port_forwarding_rule(self, result: bool) -> None:
        if result:
            self.echo_status_ok(message='rule deleted successfully')
        else:
            self.echo_status_failure(message='could not delete port forwarding')

    def format_describe(self, vm_dict: DictStrAny) -> None:
        self.echo_response(body=vm_dict)

    def format_create(self, new_uuid: Optional[str]) -> None:
        if new_uuid:
            self.echo_response(body={'uuid': new_uuid}, message="vm created successfully")
        else:
            self.echo_status_failure("could not create vm")

    def format_add_network_card(self, success: bool) -> None:
        if success:
            self.echo_status_ok('successfully added network card')
        else:
            self.echo_status_failure('could not add network card')

    def format_delete_network_card(self, success: bool) -> None:
        if success:
            self.echo_status_ok('successfully deleted network card')
        else:
            self.echo_status_failure('could not delete network card')
