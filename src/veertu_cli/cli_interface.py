import os
from copy import copy
from time import sleep
from typing import Any, Dict, List, Optional, Union

import click
from .formatter import CliFormatter, JsonFormatter, ListDictStrAny, DictStrAny
from .utils import name_from_file_path
from .veertu_manager import (
    VeertuManager,
    get_veertu_manager,
    VeertuManagerException,
    VeertuAppNotFoundException,
    VMNotFoundException,
    ImportExportFailedException
)
import tarfile
import plistlib

# Global instances, type hinted
veertu_mngr: VeertuManager = get_veertu_manager() # Renamed for clarity
cli_fmt: Union[CliFormatter, JsonFormatter] = CliFormatter()


class CliContext(object):
    def __init__(self) -> None:
        self.machine_readable: bool = False
        self.vm_id: Optional[str] = None


@click.group()
@click.option('--machine-readable', is_flag=True, default=False)
@click.pass_context
def main(ctx: click.Context, machine_readable: bool) -> None:
    global cli_fmt # Ensure we're re-assigning the global formatter
    try:
        veertu_mngr.version()
    except VeertuAppNotFoundException:
        # Handle early if app is not found, before CliContext is even fully used by commands
        # cli_fmt might still be the default CliFormatter here.
        cli_fmt.echo_status_failure(message='Veertu app not found. Please ensure Veertu Desktop is installed and configured.')
        ctx.exit(1) # Exit early
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=f"Veertu manager error on init: {str(e)}")
        ctx.exit(1)


    ctx.obj = CliContext()
    if machine_readable:
        if isinstance(ctx.obj, CliContext): # Type guard for mypy
            ctx.obj.machine_readable = True
        cli_fmt = JsonFormatter()


@click.command(name="list", help='Shows a list of VMs, ids and names') # Explicit command name
def list_vms() -> None: # Renamed to avoid conflict with built-in list
    try:
        vms_list: ListDictStrAny = veertu_mngr.list()
        cli_fmt.format_list_output(vms_list)
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(help='Show runtime VM state and properties. VM can be name or id.')
@click.argument('vm_id', type=str)
@click.option('--state', 'show_state', default=False, is_flag=True, help='Show state of vm') # Renamed for clarity
@click.option('--ip-address', 'show_ip_address', default=False, is_flag=True, help='Show ip address of vm') # Renamed
@click.option('--port-forwarding', 'show_port_forwarding', default=False, is_flag=True, help='show port forwarding info of vm') # Renamed
@click.pass_context
def show(ctx: click.Context, vm_id: str, show_state: bool, show_ip_address: bool, show_port_forwarding: bool) -> None:
    try:
        vm_info: DictStrAny = veertu_mngr.show(vm_id)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
        return
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))
        return

    if show_state:
        click.echo(str(vm_info.get('status', 'N/A')))
    if show_ip_address:
        click.echo(str(vm_info.get('ip', 'N/A')))
    if show_port_forwarding:
        pf_info: ListDictStrAny = vm_info.get('port_forwarding', [])
        cli_fmt.format_port_forwarding_info(pf_info)

    if any([show_state, show_ip_address, show_port_forwarding]):
        return

    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj:
        cli_fmt.echo_status_failure(message="CLI context not properly initialized.")
        return

    if vm_info.get('status', False) != 'running' and not current_ctx_obj.machine_readable:
        keep_keys = ['id', 'name', 'status']
        # Create a new dict for the filtered info
        filtered_vm_info: DictStrAny = {
            k: v for k, v in vm_info.items() if k in keep_keys
        }
        cli_fmt.format_show_output(filtered_vm_info)
    else:
        cli_fmt.format_show_output(vm_info)


@click.command(help='Starts or resumes paused VM')
@click.argument('vm_id', type=str)
@click.option('--restart', is_flag=True, default=False)
def start(vm_id: str, restart: bool) -> None:
    try:
        success: bool = veertu_mngr.start(vm_id, restart=restart)
        cli_fmt.format_start_output(success, restart=restart, vm_id=vm_id)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(help='Pauses a VM')
@click.argument('vm_id', type=str)
def pause(vm_id: str) -> None:
    try:
        success: bool = veertu_mngr.pause(vm_id)
        cli_fmt.format_pause_output(success, vm_id=vm_id)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(help='Shuts down a vm')
@click.argument('vm_id', type=str)
@click.option('--force', is_flag=True, default=False)
def shutdown(vm_id: str, force: bool) -> None:
    try:
        success: bool = veertu_mngr.shutdown(vm_id, force=force)
        cli_fmt.format_shutdown_output(success, vm_id=vm_id)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(help='Restarts a VM')
@click.argument('vm_id', type=str)
@click.option('--force', is_flag=True, default=False)
def reboot(vm_id: str, force: bool) -> None:
    try:
        success: bool = veertu_mngr.reboot(vm_id, force=force)
        cli_fmt.format_reboot_output(success, vm_id=vm_id)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(name='delete', help="Deletes a VM") # Explicit command name
@click.argument('vm_id', type=str)
@click.option('--yes', is_flag=True, default=False, help="Confirm deletion without prompting.")
@click.pass_context
def delete_vm(ctx: click.Context, vm_id: str, yes: bool) -> None:
    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj:
        cli_fmt.echo_status_failure(message="CLI context not properly initialized.")
        return
    try:
        # show() can raise VMNotFoundException, which is caught below.
        vm_details_for_confirm: DictStrAny = veertu_mngr.show(vm_id)
        if not yes and not current_ctx_obj.machine_readable:
            click.confirm(
                f"Are you sure you want to delete vm {vm_details_for_confirm.get('id', vm_id)} {vm_details_for_confirm.get('name', '')}?",
                abort=True
            )

        success: bool = veertu_mngr.delete(vm_id) # This can also raise VMNotFoundException
        cli_fmt.format_delete_output(success, vm_id=vm_id)
    except VMNotFoundException: # Catches from either show() or delete()
        cli_fmt.format_vm_not_exist()
    except click.exceptions.Abort:
        click.echo("Deletion aborted by user.")
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.command(help='Exports a vm to a file')
@click.argument('vm_id', type=str)
@click.argument('output_file', type=click.Path(exists=False, dir_okay=False, writable=True))
@click.option('--fmt', 'export_format', default='vmz', type=click.Choice(['vmz', 'box']), required=False, show_default=True) # Renamed
@click.option('--silent', is_flag=True, default=False)
@click.pass_context
def export(ctx: click.Context, vm_id: str, output_file: str, export_format: str, silent: bool) -> None:
    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj:
        cli_fmt.echo_status_failure(message="CLI context not properly initialized.")
        return
    try:
        # If machine_readable, manager handles progress loop silently.
        # Otherwise, this CLI part handles progress bar display if not silent.
        actual_silent_for_manager = current_ctx_obj.machine_readable or silent
        do_cli_progress_loop = not actual_silent_for_manager

        if not silent and os.path.isfile(output_file): # Check for overwrite only if CLI is interactive
            click.confirm('File exists, do you want to overwrite?', default=False, abort=True)

        export_result: Union[str, bool] = veertu_mngr.export_vm(
            vm_id, output_file, fmt=export_format,
            silent=actual_silent_for_manager, # Manager is silent if machine_readable or explicit --silent
            do_progress_loop=actual_silent_for_manager # Manager loops if it's silent (machine_readable or --silent)
        )

        if do_cli_progress_loop: # Interactive CLI, needs to show progress bar
            if isinstance(export_result, str): # This is the handle
                length = 100 if export_format == 'vmz' else 200
                _do_import_export_progress_bar(export_result, length)
                cli_fmt.echo_status_ok(message="Export completed.") # Success message after loop
            elif not export_result : # Explicit False from manager, means it couldn't even start
                cli_fmt.echo_status_failure(message='Could not export vm. Export process did not start.')
        # If actual_silent_for_manager was true, manager handled the loop.
        # We assume success if no exception, or rely on manager's output if it's machine_readable.
        # If machine_readable and export_result was False, it indicates an issue.
        elif current_ctx_obj.machine_readable and isinstance(export_result, bool) and not export_result:
            cli_fmt.echo_status_failure(message="Export failed (machine-readable mode).")


    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except ImportExportFailedException as e:
        cli_fmt.echo_status_failure(message=f"Export failed: {str(e)}")
    except click.exceptions.Abort:
        click.echo("Export aborted by user.")
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))
    except Exception as e:
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred during export: {str(e)}")


def _do_import_export_progress_bar(handle: str, length: int) -> None:
    """Helper to display a progress bar for import/export operations."""
    try:
        # Label added for clarity
        with click.progressbar(length=length, show_eta=False, label=f"Processing task {handle[:8]}...") as bar:
            progress: int = 0
            previous_progress: int = 0
            while progress < length:
                current_progress_val: int = veertu_mngr.progress(handle) # progress() should return int or raise
                progress = current_progress_val

                step: int = progress - previous_progress

                if step == 0 and progress < length:
                    sleep(1) # Avoid busy-waiting if no progress and not done

                update_val = max(0, step)
                if bar.pos + update_val > bar.length: # Prevent overshooting
                    update_val = bar.length - bar.pos

                bar.update(update_val)
                previous_progress = progress

                if progress >= length: # Ensure loop terminates
                    break
    except ImportExportFailedException as e: # Handled by manager.progress
        # Print above the (now broken) progress bar.
        click.echo(f"\nError during progress update: {str(e)}", err=True)
        # Let the caller handle the failure state
    except VeertuManagerException as e:
        click.echo(f"\nManager error during progress update: {str(e)}", err=True)
    # Let other unexpected exceptions propagate to the main CLI handler.


@click.command(name='import', help='Import a vm into Veertu') # Explicit command name
@click.argument('input_file', type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('--os-family', default=None, type=str)
@click.option('--os-type', default=None, type=str)
@click.option('--name', default=None, type=str)
@click.option('--fmt', 'import_format', default=None, type=str) # Renamed
@click.option('-n', '--get-name-suggestion', is_flag=True, default=False, help="Suggest a name for the VM based on the file.")
@click.pass_context
def import_vm(
    ctx: click.Context,
    input_file: str,
    os_family: Optional[str],
    os_type: Optional[str],
    name: Optional[str],
    import_format: Optional[str],
    get_name_suggestion: bool
) -> None:
    if get_name_suggestion:
        suggested_name = _try_guess_name(input_file)
        click.echo(f'Suggested VM name: "{suggested_name}"')
        return

    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj:
        cli_fmt.echo_status_failure(message="CLI context not properly initialized.")
        return

    try:
        actual_silent_for_manager = current_ctx_obj.machine_readable
        do_cli_progress_loop = not actual_silent_for_manager

        import_result: Union[str, bool] = veertu_mngr.import_vm(
            input_file, name, os_family, os_type, import_format,
            silent=actual_silent_for_manager,
            do_progress_loop=actual_silent_for_manager
        )

        if do_cli_progress_loop:
            if isinstance(import_result, str):
                _do_import_export_progress_bar(import_result, 100)
                cli_fmt.echo_status_ok(message="Import process completed.")
            elif not import_result:
                cli_fmt.echo_status_failure(message='Could not import VM. Import process did not start.')
        elif actual_silent_for_manager: # Machine readable or silent
            if isinstance(import_result, bool) and not import_result:
                 cli_fmt.echo_status_failure(message="Import process reported failure.")
            else: # Assume success (True or handle string)
                 cli_fmt.echo_status_ok()

    except ImportExportFailedException as e:
        cli_fmt.echo_status_failure(
            message=f"Veertu failed to import {input_file}. Error: {str(e)}"
        )
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))
    except Exception as e:
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred during import: {str(e)}")


def _try_guess_name(file_path: str) -> str:
    """Tries to guess a VM name from a .box file's metadata or the filename."""
    try:
        # Try reading as a tar.gz file (common for .box)
        with tarfile.open(file_path, 'r:gz') as tf:
            d: DictStrAny = {}
            plist_content_bytes: Optional[bytes] = None
            # Efficiently find and extract settings.plist if it exists
            try:
                member = tf.getmember('settings.plist') # Check if member exists
                extracted_file = tf.extractfile(member)
                if extracted_file:
                    plist_content_bytes = extracted_file.read()
                    extracted_file.close()
            except KeyError: # settings.plist not found in tar
                pass

            if plist_content_bytes:
                try:
                    d = plistlib.loads(plist_content_bytes)
                except plistlib.InvalidFileException: # Handle malformed plist
                    pass # Fall through to filename guess

            # Try to get 'name' or 'display_name' from plist data
            suggested_name_any: Any = d.get('name', d.get('display_name', None))
            if suggested_name_any is not None:
                return str(suggested_name_any) # Ensure it's a string
            # If not in plist, or plist failed, fall back to filename
            return name_from_file_path(file_path)
    except tarfile.ReadError: # Not a valid tar.gz file
        return name_from_file_path(file_path)
    except Exception: # Catch other potential errors (e.g., file IO)
        return name_from_file_path(file_path) # Fallback


@click.command(name='create') # Explicit command name
@click.argument('input_file', type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('--os-family', default=None, type=str)
@click.option('--os-type', default=None, type=str)
@click.option('--name', default=None, type=str)
@click.pass_context
def create_vm(
    ctx: click.Context,
    input_file: str,
    os_family: Optional[str],
    os_type: Optional[str],
    name: Optional[str]
) -> None:
    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj:
        cli_fmt.echo_status_failure(message="CLI context not properly initialized.")
        return

    try:
        new_uuid: Optional[str] = veertu_mngr.create_vm(input_file, name, os_family, os_type)
        cli_fmt.format_create(new_uuid)
        if new_uuid and not current_ctx_obj.machine_readable:
            if click.confirm('Would you like to start the new vm?', default=False):
                veertu_mngr.start(new_uuid)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist() # Should not happen for create, but start can raise it
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))
    except click.exceptions.Abort: # User chose not to start the VM
        click.echo("VM start aborted by user.")
    except Exception as e:
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred during VM creation: {str(e)}")


@click.command(help='Show all data for a VM')
@click.argument('vm_id', type=str)
def describe(vm_id: str) -> None:
    try:
        vm_dict: DictStrAny = veertu_mngr.describe(vm_id)
        cli_fmt.format_describe(vm_dict)
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@click.group(help='Modifys a VM settings')
@click.argument('vm_id', type=str)
@click.pass_context
def modify(ctx: click.Context, vm_id: str) -> None:
    # Ensure CliContext exists on ctx.obj
    if not isinstance(ctx.obj, CliContext):
        ctx.obj = CliContext() # Initialize if not present (e.g. modify called directly)

    # Store vm_id in context
    ctx.obj.vm_id = vm_id

    # Verify vm exists before proceeding to subcommands to provide early feedback
    try:
        veertu_mngr.show(vm_id) # A light check, show() itself handles VMNotFound
    except VMNotFoundException:
        cli_fmt.format_vm_not_exist()
        ctx.exit(1) # Prevent subcommands from running if VM doesn't exist
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=f"Error verifying VM {vm_id}: {str(e)}")
        ctx.exit(1)


@modify.command(name="set", help="Set various properties of a VM.")
@click.pass_context
@click.option('--headless', type=click.Choice(['0', '1']), default=None, required=False)
@click.option('--name', 'new_name', default=None, type=str, help="Set new name for the VM")
@click.option('--cpu', default=None, type=str, help="Set number of cpu cores")
@click.option('--ram', default=None, type=str, help="Set memory - e.g., 2048MB or 2GB")
# Options below are defined but not implemented in the original logic, so commented out from params
# @click.option('--read-only', type=click.Choice(['0', '1']), default=None)
# @click.option('--hdpi', type=click.Choice(['0', '1']), default=None)
# @click.option('--copy-paste', type=click.Choice(['0', '1']), default=None)
# @click.option('--file-sharing', type=click.Choice(['0', '1']), default=None)
@click.option('--network-card-idx', default=None, type=str, help="Index of the network card to modify.")
@click.option('--network-type', default=None, type=click.Choice(['shared', 'host', 'disconnected']))
def set_options(
    ctx: click.Context,
    headless: Optional[str],
    new_name: Optional[str],
    cpu: Optional[str],
    ram: Optional[str],
    # read_only: Optional[str],
    # hdpi: Optional[str],
    # copy_paste: Optional[str],
    # file_sharing: Optional[str],
    network_card_idx: Optional[str],
    network_type: Optional[str]
) -> None:
    current_ctx_obj: Optional[CliContext] = ctx.obj if isinstance(ctx.obj, CliContext) else None
    if not current_ctx_obj or current_ctx_obj.vm_id is None: # vm_id should be set by 'modify' group
        cli_fmt.echo_status_failure(message="VM ID not found in context. This is an internal error.")
        return

    vm_id: str = current_ctx_obj.vm_id
    good_ones: DictStrAny = {}
    bad_ones: DictStrAny = {}

    any_option_provided = any(opt is not None for opt in [headless, new_name, cpu, ram, network_card_idx, network_type])
    if not any_option_provided:
        click.echo("No options provided to set. Use --help for available options.", err=True)
        return

    try:
        if headless is not None:
            _add_to_dict(veertu_mngr.set_headless(vm_id, headless), 'headless', headless, good_ones, bad_ones)
        if new_name is not None:
            _add_to_dict(veertu_mngr.rename(vm_id, new_name), 'name', new_name, good_ones, bad_ones)
        if cpu is not None:
            _add_to_dict(veertu_mngr.set_cpu(vm_id, cpu), 'cpu', cpu, good_ones, bad_ones)
        if ram is not None:
            _add_to_dict(veertu_mngr.set_ram(vm_id, ram), 'ram', ram, good_ones, bad_ones)

        if network_card_idx is not None and network_type is not None:
            _add_to_dict(veertu_mngr.set_network_type(vm_id, network_card_idx, network_type),
                         f'network type for card {network_card_idx}', network_type, good_ones, bad_ones)
        elif network_card_idx is not None or network_type is not None:
             _add_to_dict(False, 'network modification', 'Both --network-card-idx and --network-type are required together.', good_ones, bad_ones)

        cli_fmt.format_properties_changed(good_ones, bad_ones)

    except VMNotFoundException: # Should be caught by modify group, but as safeguard
        cli_fmt.format_vm_not_exist()
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))
    except Exception as e: # Catch-all for unexpected issues
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred while setting options: {str(e)}")


def _add_to_dict(success: bool, key: str, value: Any, good_ones: DictStrAny, bad_ones: DictStrAny) -> None:
    """Helper to populate dictionaries based on operation success."""
    if success:
        good_ones[key] = value
    else:
        bad_ones[key] = value


@modify.group(help="Add components to a VM.")
@click.pass_context
def add(ctx: click.Context) -> None:
    # This group function ensures that vm_id is available in ctx.obj
    # The 'modify' group should have already set it and verified VM existence.
    if not isinstance(ctx.obj, CliContext) or ctx.obj.vm_id is None:
        cli_fmt.echo_status_failure(message="VM ID not found in context for 'add' commands. This indicates an internal setup error.")
        ctx.exit(1)


@add.command(name='port-forwarding', help="Add a port forwarding rule.")
@click.pass_context
@click.argument('rule_name', type=str)
@click.option('--host-ip', default="0.0.0.0", type=str, show_default=True, help="Host IP to listen on.")
@click.option('--host-port', required=True, type=int, help="Host port to listen on.")
@click.option('--guest-ip', default=None, type=str, help="Guest IP to forward to. Defaults to guest's primary IP if supported by manager.")
@click.option('--guest-port', required=True, type=int, help="Guest port to forward to.")
@click.option('--protocol', default='tcp', type=click.Choice(['tcp', 'udp']), show_default=True)
def add_port_forwarding_rule(
    ctx: click.Context,
    rule_name: str,
    host_ip: str,
    host_port: int,
    guest_ip: Optional[str],
    guest_port: int,
    protocol: str
) -> None:
    # vm_id is asserted to be non-None by the 'add' group context check
    vm_id: str = ctx.obj.vm_id # type: ignore

    try:
        # Manager expects strings for ports based on original implementation; adapt if manager API changes
        success: bool = veertu_mngr.add_port_forwarding(
            vm_id, rule_name, host_ip, str(host_port), guest_ip, str(guest_port), protocol=protocol
        )
        cli_fmt.format_added_port_forwarding_rule(success)
    except VeertuManagerException as e: # Catches VMNotFound if manager raises it
        cli_fmt.echo_status_failure(message=str(e))
    except Exception as e: # Other unexpected errors
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred: {str(e)}")


@add.command(name="network-card", help="Add a network card.")
@click.pass_context
@click.option('--type', 'nic_type', type=click.Choice(['shared', 'host', 'disconnected']), default='shared', show_default=True)
@click.option('--model', type=click.Choice(['e1000', 'rtl8139']), default='e1000', show_default=True)
def add_network_card_to_vm(ctx: click.Context, nic_type: str, model: str) -> None:
    vm_id: str = ctx.obj.vm_id # type: ignore

    try:
        success: bool = veertu_mngr.add_network_card(vm_id, nic_type, model)
        cli_fmt.format_add_network_card(success)
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@modify.group(name="delete", help="Delete components or configuration from a VM.")
@click.pass_context
def delete_modify_items(ctx: click.Context) -> None:
    if not isinstance(ctx.obj, CliContext) or ctx.obj.vm_id is None:
        cli_fmt.echo_status_failure(message="VM ID not found in context for 'delete' commands. Internal error.")
        ctx.exit(1)


@delete_modify_items.command('port-forwarding', help="Delete a port forwarding rule by name.")
@click.pass_context
@click.argument('rule_name', type=str)
def delete_port_forwarding_rule(ctx: click.Context, rule_name: str) -> None:
    vm_id: str = ctx.obj.vm_id # type: ignore

    try:
        success: bool = veertu_mngr.remove_port_forwarding(vm_id, rule_name)
        cli_fmt.format_deleted_port_forwarding_rule(success)
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))


@delete_modify_items.command('network-card', help="Delete a network card by its index.")
@click.pass_context
@click.argument('card_index', type=str) # Manager might expect string index
def delete_network_card_from_vm(ctx: click.Context, card_index: str) -> None:
    vm_id: str = ctx.obj.vm_id # type: ignore
    try:
        success: bool = veertu_mngr.delete_network_card(vm_id, card_index)
        cli_fmt.format_delete_network_card(success)
    except VeertuManagerException as e:
        cli_fmt.echo_status_failure(message=str(e))

# Add commands to main group
main.add_command(list_vms)
main.add_command(show)
main.add_command(start)
main.add_command(pause)
main.add_command(shutdown)
main.add_command(reboot)
main.add_command(delete_vm)
main.add_command(export)
main.add_command(import_vm)
main.add_command(describe)
main.add_command(modify)
main.add_command(create_vm)

def cli_entry_point() -> None:
    """Main entry point for the Veertu CLI."""
    global cli_fmt # Access global cli_fmt for exception handling
    try:
        # standalone_mode=False is good for testing, ensures Click doesn't call sys.exit()
        main(standalone_mode=False)
    except VeertuAppNotFoundException as e:
        # Use the current cli_fmt, which might be JsonFormatter if --machine-readable was used
        error_msg = str(e) if str(e) else 'Veertu app not found. Please check configuration.'
        cli_fmt.echo_status_failure(message=error_msg)
        # Consider sys.exit(app_not_found_exit_code) here if not using standalone_mode=False
    except VeertuManagerException as e: # For other known manager issues
        cli_fmt.echo_status_failure(message=str(e))
    except click.exceptions.Abort: # User aborted a click.confirm()
        # For Abort, it's common to output a specific message or just exit quietly
        cli_fmt.echo_status_failure(message="Operation aborted by user.")
    except Exception as e: # Catch-all for any other unexpected errors
        # Provide a generic error message but include specifics for debugging
        cli_fmt.echo_status_failure(message=f"An unexpected error occurred: {type(e).__name__} - {str(e)}")


if __name__ == '__main__':
    cli_entry_point()
