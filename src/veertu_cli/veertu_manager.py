import os
try:
    import ConfigParser # Python 2
except ImportError:
    import configparser as ConfigParser # Python 3
import subprocess
# import uuid # uuid is imported but not used
from collections import OrderedDict
import tarfile
import time
# import shutil # shutil is imported but not used
import plistlib
from typing import (
    Any, Dict, List, Optional, Union, Sequence, Tuple, TypeVar, Callable, Type
)

# For older Python versions (pre-3.8), use typing_extensions for Literal if needed for stricter choices.
# from typing_extensions import Literal

# Define common type aliases for clarity
DictStrAny = Dict[str, Any]
ListDictStrAny = List[Dict[str, Any]]
ProjectionType = OrderedDict[str, bool] # Projection is an OrderedDict mapping key (str) to a boolean (include in result)

# Type variable for VeertuManager methods that can return different types based on kwargs
_T = TypeVar('_T')
_VT_co = TypeVar('_VT_co', covariant=True, bound='VeertuManager') # For get_veertu_manager


class VeertuManagerException(Exception):
    """Base exception for VeertuManager errors."""
    pass


class VMNotFoundException(VeertuManagerException):
    """Raised when a VM cannot be found."""
    pass


class NoOutputFileSpecified(VeertuManagerException):
    """Raised when an output file is required but not specified."""
    pass


class InternalAppError(VeertuManagerException):
    """Raised for internal errors, often when parsing application output fails."""
    pass


class ImportExportFailedException(VeertuManagerException):
    """Raised when an import or export operation fails."""
    pass


class WrongProjectionException(VeertuManagerException):
    """Raised when projection arguments are inconsistent with AppleScript output."""
    pass


class VeertuAppNotFoundException(VeertuManagerException):
    """Raised when the Veertu application itself cannot be found or is not responsive."""
    pass


class VeertuManager(object):
    """
    Manages interactions with the Veertu Desktop application via AppleScript (osascript).
    """
    def __init__(self) -> None:
        self.app: str = "Veertu"
        parser: ConfigParser.SafeConfigParser = ConfigParser.SafeConfigParser()
        cfg_file: str = os.path.expanduser('~/.veertu_config')

        app_name_to_use: str = self.app # Start with default

        if os.path.exists(cfg_file):
            try:
                parser.read(cfg_file)
                if parser.has_option('DEFAULT', 'APP_PATH'):
                    config_app_path: Optional[str] = parser.get('DEFAULT', 'APP_PATH')
                    if config_app_path:
                        app_name_to_use = config_app_path
                        if not self._verify_app_name(app_name_to_use):
                            app_name_to_use = self._find_working_app_name_from_options(
                                ['Veertu', 'Veertu 2016 Business', 'Veertu Desktop'],
                                config_app_path
                            )
                    else:
                        app_name_to_use = self._find_working_app_name_from_options(
                            ['Veertu', 'Veertu 2016 Business', 'Veertu Desktop'], self.app
                        )
                else:
                    app_name_to_use = self._find_working_app_name_from_options(
                        ['Veertu', 'Veertu 2016 Business', 'Veertu Desktop'], self.app
                    )
            except ConfigParser.Error:
                app_name_to_use = self._find_working_app_name_from_options(
                    ['Veertu', 'Veertu 2016 Business', 'Veertu Desktop'], self.app
                )
        else:
            app_name_to_use = self._find_working_app_name_from_options(
                ['Veertu', 'Veertu 2016 Business', 'Veertu Desktop'], self.app
            )

        self.app = app_name_to_use

    def _verify_app_name(self, app_name: str) -> bool:
        """Tests if an app name is responsive by calling 'version'."""
        original_app = self.app
        self.app = app_name
        try:
            self.version()
            self.app = original_app
            return True
        except VeertuAppNotFoundException:
            self.app = original_app
            return False
        except VeertuManagerException: # Other errors during version() call
            self.app = original_app # Restore app name
            # This implies app was found but 'version' command failed.
            # Treat as 'verified' for purposes of _find_working_app_name_from_options,
            # as the app itself is present. Actual command failures will be caught later.
            return True


    def _find_working_app_name_from_options(self, options: List[str], fallback_app_name: str) -> str:
        """
        Iterates through app names in `options`, returns the first one that works.
        If none work, returns `fallback_app_name` (after trying to verify it too).
        """
        for app_option in options:
            if self._verify_app_name(app_option):
                return app_option

        # If no option worked, check if the fallback_app_name itself works
        if self._verify_app_name(fallback_app_name):
            return fallback_app_name

        # If absolutely nothing works, return the fallback_app_name.
        # The first actual command will then likely raise VeertuAppNotFoundException.
        return fallback_app_name


    def _call_veertu_app(
        self,
        command: str,
        *args: Any,
        projection: Optional[ProjectionType] = None,
        return_as_dict: bool = False,
        return_list_of_dicts: bool = False,
        scalar: bool = False,
        number: bool = False,
        return_formatted: bool = True,
        format_args: bool = True
    ) -> Any:
        if kwargs.get('format', True):
            command = command.format(*args)

        # Ensure self.app is correctly substituted if it contains spaces
        osa_command = ['osascript', '-e', 'tell application "{}" to {}'.format(self.app.replace('"', '\\"'), command)]

        try:
            osscript_output_bytes = subprocess.check_output(osa_command, stderr=subprocess.PIPE)
            osscript_output = osscript_output_bytes.decode('utf-8').strip() # Decode from bytes
        except subprocess.CalledProcessError as e:
            # Capture stderr for better error reporting
            error_message = e.stderr.decode('utf-8').strip() if e.stderr else str(e)
            # It's possible the app isn't found or another osascript error occurred
            if "Application can't be found" in error_message or "Application not running" in error_message :
                 raise VeertuAppNotFoundException('Application "{}" not found or not running. OSA Error: {}'.format(self.app, error_message))
            raise VeertuManagerException('OSA Script execution failed for app "{}": {}. Command: {}'.format(self.app, error_message, command))


        if kwargs.get('return_as_dict', kwargs.get('return_list_of_dicts', False)):
            projection = kwargs.get('projection', OrderedDict()) # Ensure projection is ordered
            return_list_of_dicts = kwargs.get('return_list_of_dicts', False)
            list_output = self._split_and_strip(osscript_output)
            projection_length = len(projection)
            if projection_length == 0: # Avoid division by zero if projection is empty
                 if not list_output or (len(list_output) == 1 and not list_output[0]): # Empty or [""]
                     return [] if return_list_of_dicts else OrderedDict()
                 raise WrongProjectionException('Projection is empty but received output.')

            list_output_length = len(list_output)

            # Handle cases where output is empty or just [""]
            if list_output_length == 1 and not list_output[0]:
                list_output_length = 0
                list_output = []

            if list_output_length % projection_length != 0:
                raise WrongProjectionException('Wrong parameters passed to projection. Output length {} not divisible by projection length {}. Output: {}'.format(list_output_length, projection_length, list_output))

            objects_returned = list_output_length // projection_length if projection_length > 0 else 0

            if objects_returned == 0: # No objects to return
                return [] if return_list_of_dicts else OrderedDict()

            if objects_returned == 1 and not return_list_of_dicts:
                return self._turn_into_dict(list_output, projection)

            output_lists = [OrderedDict() for _ in range(objects_returned)] # Use _ for unused loop var

            # Ensure projection items are iterated in order for Python < 3.7 where dicts are not ordered by default
            # This is important because we pop from list_output
            current_output_idx = 0
            for _ in range(objects_returned):
                for key, is_return in projection.items():
                    item = list_output[current_output_idx]
                    current_output_idx += 1
                    if is_return: # Check if this key should be included in the result
                        output_lists[_][key] = item # Use the loop variable _ for the current dict
            return output_lists

        osscript_output = osscript_output.strip()
        if kwargs.get('scalar', False):
            if self._is_int_parsed(osscript_output):
                return bool(int(osscript_output))
            if osscript_output.lower() == 'true':
                return True
            if osscript_output.lower() == 'false': # Handle 'false' string
                return False
            return False # Default for scalar if not recognized

        if kwargs.get('number', False):
            try:
                return int(osscript_output)
            except ValueError:
                raise InternalAppError('There was an internal error, your process might have succeeded. please check. Expected number, got: {}'.format(osscript_output))

        if kwargs.get('return_formatted', True): # This means _split_and_strip by default
             return self._split_and_strip(osscript_output)

        return osscript_output # Return raw string if not formatted

    def _is_int_parsed(self, num_str): # Renamed num to num_str
        try:
            int(num_str)
            return True
        except ValueError:
            return False

    def _turn_into_dict(self, list_output, projection):
        output_dict = OrderedDict()
        # Ensure projection items are iterated in order
        list_output_idx = 0
        for key, is_return in projection.items():
            if list_output_idx < len(list_output):
                item = list_output[list_output_idx]
                list_output_idx += 1
                if is_return:
                    output_dict[key] = item
            else: # Not enough items in list_output for projection
                if is_return: # If we expected this key, mark as missing or handle error
                    output_dict[key] = None # Or raise error
        return output_dict


    def _call_veertu_with_name_fallback(self, command, *args, **kwargs):
        id_value = kwargs.pop('id_value', args[0] if args else None)
        if id_value is None:
            raise VeertuManagerException("No vm_id or id_value provided for fallback.")

        # Ensure all args are strings for command.format()
        str_args = [str(arg) for arg in args]
        command_formatted = command.format(*str_args)

        try:
            return self._call_veertu_app(command_formatted, format=False, **kwargs)
        except subprocess.CalledProcessError as e: # This exception is now handled inside _call_veertu_app
            # This block might be redundant if _call_veertu_app raises VeertuAppNotFoundException
            # or VeertuManagerException for osascript errors.
            # If it's specifically for VMNotFound, then it needs to be more specific.
            # For now, let's assume VMNotFoundException might still be the goal here.
            pass # Fall through to name lookup
        except VMNotFoundException: # Explicitly catch if _call_veertu_app determined it's VMNotFound
            pass # Fall through to name lookup
        except VeertuAppNotFoundException: # If app itself is not found, re-raise
            raise

        # Fallback logic
        try:
            vms_list = self.list()
            for vm in vms_list:
                name = vm.get('name')
                if name == str(id_value): # Compare with string version of id_value
                    vm_id_found = vm.get('id')
                    # Replace only the first occurrence of id_value, assuming it's the VM identifier part
                    new_command_formatted = command_formatted.replace(str(id_value), vm_id_found, 1)
                    return self._call_veertu_app(new_command_formatted, format=False, **kwargs)
        except VeertuManagerException as e_fallback: # Catch errors during fallback list() or subsequent call
            raise VMNotFoundException("VM {} not found by ID, and fallback by name also failed: {}".format(id_value, e_fallback))

        raise VMNotFoundException("VM {} was not found by ID or name.".format(id_value))


    def list(self):
        projection_args = OrderedDict([('id', True), ('name', True)])
        return self._call_veertu_app('{{id, name}} of every vm', return_list_of_dicts=True, projection=projection_args)

    def show(self, vm_id, state=True, ip_address=True, port_forwarding=True):
        projection_args = OrderedDict([('id', True), ('name', True), ('status', state), ('ip', ip_address)])
        command = 'get {{id, name, status, ip}} of vm id "{}"'
        vm_info = self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, return_as_dict=True,
                                                       projection=projection_args)
        if port_forwarding and vm_info.get('id'): # Ensure vm_info is not empty and has id
            vm_info['port_forwarding'] = self.get_port_forwarding(vm_info.get('id'))
        return vm_info

    def get_port_forwarding(self, vm_id, protocol=True, description=True, host_ip=True,
                            host_port=True, guest_ip=True, guest_port=True):
        projection_args = OrderedDict([('name', True), ('protocol', protocol),
                                       ('host_ip', host_ip), ('host_port', host_port),
                                       ('guest_ip', guest_ip), ('guest_port', guest_port)])
        command = '{{name, protocol, host ip, host port, guest ip, guest port}}' \
                  ' of port forwarding of advanced settings of vm id "{}"'
        # Use try-except for cases where 'port forwarding' might not exist or be empty
        try:
            port_forwarding_info = self._call_veertu_app(command, vm_id, return_as_dict=False, # Expecting list of dicts
                                                         projection=projection_args, return_list_of_dicts=True)
        except WrongProjectionException as e: # If output is empty leading to this
             if "Output length 0" in str(e) or "Output length 1 not divisible" in str(e): # Check if it's due to empty list
                return [] # No port forwarding rules
             raise e


        # Filter out empty rules more robustly
        # An empty rule might be represented as a dict where all values are empty strings or placeholders like '-'
        # self._split_and_strip now replaces 'missing value' with '-'
        valid_rules = []
        for rule in port_forwarding_info:
            # A rule is considered non-empty if at least one of its values is not '-' and not empty
            if any(val and val != '-' for val in rule.values()):
                valid_rules.append(rule)
        port_forwarding_info = valid_rules

        if description:
            for port_forwarding_dict in port_forwarding_info:
                rule_description = self.get_port_forwarding_description(vm_id, port_forwarding_dict.get('name', ''))
                port_forwarding_dict['description'] = rule_description
        return port_forwarding_info

    def get_port_forwarding_description(self, vm_id, rule_name):
        command = 'virtualbox description of port forwarding "{}" of advanced settings of vm id "{}"'
        # This might return "missing value" which becomes "-"
        desc = self._call_veertu_app(command, rule_name, vm_id, return_formatted=False)
        return desc if desc != '-' else ""


    def start(self, vm_id, restart=False):
        if restart:
            return self.reboot(vm_id)
        command = 'start of vm id "{}"'
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def pause(self, vm_id):
        command = 'suspend of vm id "{}"'
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def shutdown(self, vm_id, force=False):
        if force:
            command = 'force shutdown of vm id "{}"'
        else:
            command = 'shutdown of vm id "{}"'
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def reboot(self, vm_id, force=False):
        if force:
            # Ensure shutdown completes before starting. This might need a loop or check.
            # For simplicity, just calling them sequentially.
            self.shutdown(vm_id, force=True)
            # Add a small delay to allow shutdown to process if needed
            # time.sleep(1) # Consider if this is necessary
            return self.start(vm_id)
        command = 'restart of vm id "{}"' # Original had 'restart   of ...'
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def delete(self, vm_id):
        command = 'delete vm id "{}"'
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def export_vm(self, vm_id, output_file, fmt='box', silent=False, do_progress_loop=True):
        if not output_file:
            raise NoOutputFileSpecified('no output file specified')
        d, f = os.path.split(output_file)
        if '.' not in f: # Ensure filename has an extension
            f += "." + fmt
        # Ensure directory exists
        if d:
            os.makedirs(d, exist_ok=True)
        output_file = os.path.join(d, f)


        command = 'export vm id "{}" to POSIX file "{}" format "{}"'
        handle = self._call_veertu_with_name_fallback(command, vm_id, output_file, fmt, id_value=vm_id,
                                                      return_formatted=False)
        if not handle or handle == "0" or handle == "-": # Check for invalid handle
            return False
        if do_progress_loop:
            self.progress_loop(handle, silent=silent)
            return True
        return handle

    def create_vm(self, file_path, name, os_family, os_type):
        command = 'create vm POSIX file "{}" with name "{}" os "{}" os family "{}"'
        if not name:
            d, f = os.path.split(file_path)
            name = f
            if '.' in name:
                name = name.split('.').pop(0)

        # Make sure all args to format are strings
        args_for_command = [str(file_path), str(name), str(os_type), str(os_family)]
        # Use _call_veertu_app directly if no name fallback is needed for create
        # Assuming create always needs explicit parameters and doesn't use a vm_id for fallback
        result_list = self._call_veertu_app(command, *args_for_command, return_formatted=True) # Expects list
        result = result_list[0] if result_list else None

        if result == 'false' or result is None or result == '-':
            return None
        return result


    def import_vm(self, file_path, name, os_family, os_type, fmt, silent=False, do_progress_loop=True):
        command_parts = ['import vm POSIX file "{}" with name "{}"']
        if not name:
            d, f = os.path.split(file_path)
            name = f
            if '.' in name:
                name = name.split('.').pop(0)
        args = [str(file_path), str(name)]

        if os_type:
            command_parts.append('os "{}"')
            args.append(str(os_type))
        if os_family:
            command_parts.append('os family "{}"')
            args.append(str(os_family))
        # fmt seems unused in the original command string construction, but was a param
        # If fmt is important, it needs to be added to command_parts and args

        final_command = " ".join(command_parts)
        handle = self._call_veertu_app(final_command, *args, return_formatted=False)

        if not handle or handle == "0" or handle == "-": # Check for invalid handle
             raise ImportExportFailedException("Failed to get a valid handle for import operation.")

        if do_progress_loop:
            self.progress_loop(handle, silent=silent)
            return True
        return handle

    def progress_loop(self, handle, silent=False):
        # progress value from app is float like "0.00" to "1.00", or "2.00" for error/unknown state
        while True:
            progress_str = self._call_veertu_app('get progress of "{}"', handle, return_formatted=False)
            if not progress_str or progress_str == '(null)' or progress_str == "-":
                raise ImportExportFailedException("Process failed to complete or invalid progress handle.")

            try:
                progress_float = float(progress_str)
            except ValueError:
                raise ImportExportFailedException("Invalid progress value received: {}".format(progress_str))

            if not silent:
                # Python 2 print was: print(progress_str)
                # For Python 3, if you want it on the same line, use end='\r'
                print("Progress: {:.0f}%".format(progress_float * 100), end='\r')

            if progress_float >= 1.0: # Completion (1.00 or more)
                break
            if progress_float < 0.0: # Typically error codes like -1.0, or the 2.00 mentioned in original comments
                 raise ImportExportFailedException("Import/Export operation reported an error state: progress {}".format(progress_float))

            time.sleep(1)
        if not silent:
            print() # Newline after loop finishes

    def progress(self, handle):
        progress_string = self._call_veertu_app('get progress of "{}"', handle, return_formatted=False)
        if not progress_string or progress_string == '(null)' or progress_string == "-":
            raise ImportExportFailedException("Process failed to complete or invalid progress handle.")

        try:
            progress_num_float = float(progress_string.strip())
        except ValueError:
            raise ImportExportFailedException("Invalid progress value received: {}".format(progress_string))

        if progress_num_float < 0: # Error
            raise ImportExportFailedException("Operation reported error state: progress {}".format(progress_num_float))

        progress_num = int(progress_num_float * 100)
        # Original code returned 1 if progress_num was 0. This might be to avoid 0 in progress bars.
        # Keeping it for now, but evaluate if it's truly necessary.
        return progress_num if progress_num != 0 else 1


    def describe(self, vm_id, advanced_settings=True, general_settings=True, hardware=True):
        # Basic VM info
        keys = ['id', 'name', 'status', 'ip', 'version'] # 'version' was in original keys, assuming it's vm config version or similar
        vm_info = self._get_section(vm_id, keys) # No specific section for these top-level items

        if not vm_info.get('id'): # If basic info failed or vm_id is invalid
            raise VMNotFoundException(f"Could not retrieve basic info for VM ID: {vm_id}")

        if advanced_settings:
            vm_info['advanced_settings'] = self.get_advanced_settings(vm_info.get('id'))
        if general_settings:
            vm_info['general_settings'] = self.get_general_settings(vm_info.get('id'))
        if hardware:
            vm_info['hardware'] = self.get_hardware(vm_info.get('id'))
        return vm_info

    def _get_section(self, vm_id, keys, section=None): # section can be str or list/tuple
        projection_args = OrderedDict([(k, True) for k in keys])
        section_string_parts = []
        if section:
            # basestring is not in Python 3, use isinstance(section, str)
            if isinstance(section, str):
                section_string_parts.append("of " + section)
            elif isinstance(section, (list, tuple)):
                section_string_parts.extend(["of " + s for s in section])

        # Construct the command: 'get {key1, key2} of section1 of section2 of vm id "..."'
        # The order of "of section" parts matters and should be from most specific to least, or as AppleScript expects.
        # Original was ` ' '.join(["of " + exp for exp in section]) ` which implies sections are nested in order.
        # Example: `get {file sharing} of guest tools of advanced settings of vm id "..."`
        command_core = 'get {{' + ', '.join(keys) + '}} '
        command = command_core + ' '.join(section_string_parts) + (' of vm id "{}"' if vm_id else "")

        # If vm_id is part of the command (usually is), use fallback mechanism
        if vm_id:
            return self._call_veertu_with_name_fallback(command.strip(), vm_id, id_value=vm_id,
                                                        return_as_dict=True, projection=projection_args)
        else: # Should not happen if vm_id is always expected for _get_section
             raise VeertuManagerException("_get_section called without vm_id when it's required by the command structure")


    def get_advanced_settings(self, vm_id):
        # Corrected section path: 'advanced settings' is the direct section for these keys.
        adv_keys = ['snapshot', 'headless', 'hdpi', 'remap cmd']
        advanced_settings = self._get_section(vm_id, adv_keys, 'advanced settings')

        advanced_settings['port_forwarding'] = self.get_port_forwarding(vm_id, protocol=True, description=True,
                                                                        host_ip=True, host_port=True, guest_ip=True,
                                                                        guest_port=True)
        guest_tools = self.get_guest_tools(vm_id) # guest_tools is a sub-section of advanced_settings
        advanced_settings.update(guest_tools) # Merge guest tools info
        return advanced_settings

    def get_guest_tools(self, vm_id):
        keys = ['file sharing', 'copy paste', 'shared folder']
        # Section path: 'guest tools' is part of 'advanced settings'
        return self._get_section(vm_id, keys, ['guest tools', 'advanced settings'])

    def get_hardware(self, vm_id):
        keys = ['chipset', 'ram', 'acpi', 'hpet', 'hyperv', 'vga'] # Basic hardware props
        hardware_info = self._get_section(vm_id, keys, 'hardware')

        # Sub-sections of hardware
        # Ensure these calls handle potential empty results gracefully (e.g., return [] or {} )
        try: hardware_info['harddisks'] = self.get_harddisks(vm_id)
        except WrongProjectionException: hardware_info['harddisks'] = []

        try: hardware_info['audio'] = self.get_audio(vm_id)
        except WrongProjectionException: hardware_info['audio'] = [] # Or {} if it's a single item

        try: hardware_info['cd_roms'] = self.get_cd_rom(vm_id) # 'cd roms' in original, snake_case for consistency
        except WrongProjectionException: hardware_info['cd_roms'] = []

        try: hardware_info['disk_controllers'] = self.get_disk_controller(vm_id)
        except WrongProjectionException: hardware_info['disk_controllers'] = []

        try: hardware_info['network_cards'] = self.get_network_cards(vm_id)
        except WrongProjectionException: hardware_info['network_cards'] = []

        return hardware_info

    def get_harddisks(self, vm_id): # Plural, returns list of dicts
        keys = ['drive index', 'boot', 'controller', 'bus', 'file', 'size']
        return self._get_section(vm_id, keys, ['harddisks', 'hardware']) # Plural form in AppleScript? Check this. Assuming 'harddisk' for items of 'harddisks'

    def get_audio(self, vm_id): # Potentially list if multiple audio devices supported
        keys = ['audio index', 'type']
        return self._get_section(vm_id, keys, ['audio', 'hardware'])

    def get_cd_rom(self, vm_id): # Potentially list
        keys = ['cd index', 'cd controller', 'cd file', 'cd bus', 'cd type', 'media in']
        return self._get_section(vm_id, keys, ['cd rom', 'hardware']) # Singular 'cd rom' for items of 'cd roms'

    def get_disk_controller(self, vm_id): # Potentially list
        keys = ['controller index', 'controller type', 'controller model', 'controller mode']
        return self._get_section(vm_id, keys, ['disk controller', 'hardware'])

    def get_network_cards(self, vm_id): # Potentially list
        keys = ['card index', 'connection', 'pci bus', 'mac address', 'card model', 'card family']
        return self._get_section(vm_id, keys, ['network card', 'hardware'])


    def get_general_settings(self, vm_id):
        keys = ['os', 'os family', 'boot device']
        # No _call_veertu_app directly, use _get_section for consistency and fallback
        return self._get_section(vm_id, keys, 'general settings')


    def set_headless(self, vm_id, value):
        # Value is '0' or '1' from click.Choice. Convert to boolean for AppleScript.
        bool_value = True if str(value) == '1' else False
        # AppleScript expects 'true' or 'false' literals
        as_value = 'true' if bool_value else 'false'
        command = 'set headless of advanced settings of vm id "{}" to {}' # Corrected path
        # Using format with *args, ensure vm_id is first, then as_value.
        return self._call_veertu_with_name_fallback(command, vm_id, as_value, id_value=vm_id, scalar=True)


    def unset_headless(self, vm_id): # This seems redundant if set_headless(vm_id, '0') works
        command = 'set headless of advanced settings of vm id "{}" to false' # Corrected path
        return self._call_veertu_with_name_fallback(command, vm_id, id_value=vm_id, scalar=True)

    def add_port_forwarding(self, vm_id, name, host_ip, host_port, guest_ip, guest_port, protocol='tcp'):
        # Ensure all params are properly quoted or formatted if they contain spaces or special chars.
        # AppleScript command for adding port forwarding might be different.
        # Original command: 'listen on "{}" {} port {} forward to vm id "{}" port {} with name "{}"'
        # This looks like a custom syntax not standard AppleScript for object properties.
        # Assuming it's a custom command handler in the Veertu app.
        # Need to ensure all args are strings.
        args = [
            str(host_ip if host_ip is not None else "127.0.0.1"), # Default host_ip
            str(protocol).lower(),
            str(host_port),
            str(vm_id),
            str(guest_port),
            str(name)
        ]
        command = 'listen on "{}" {} port {} forward to vm id "{}" port {} with name "{}"'
        return self._call_veertu_with_name_fallback(command, *args, id_value=vm_id, number=True)


    def remove_port_forwarding(self, vm_id, rule_name):
        command = 'remove port forwarding "{}" from vm id "{}"' # Path might need 'of advanced settings'
        return self._call_veertu_with_name_fallback(command, rule_name, vm_id, id_value=vm_id, number=True)

    def rename(self, vm_id, new_name):
        command = 'rename vm id "{}" to name "{}"' # This might be `set name of vm id "{}" to "{}"`
        # return_formatted=False returns raw string. If it's a success/fail message, it's fine.
        # If it's expected to be a boolean or specific status, adjust parsing.
        # For now, assume raw string output is OK.
        return self._call_veertu_with_name_fallback(command, vm_id, new_name, id_value=vm_id, return_formatted=False)


    def set_cpu(self, vm_id, cpu_count):
        # Assuming 'cpu count' is a property of 'hardware' or 'cpu settings'
        return self.set_property(vm_id, 'cpu count', cpu_count, section=['hardware']) # Example section

    def set_ram(self, vm_id, ram):
        # RAM is often a direct property or within hardware. Ram value might need units like "MB" or "GB" if not just int.
        # The original command was `'"%s"' % ram` which suggests ram is a string.
        return self.set_property(vm_id, 'ram', str(ram), section=['hardware'], string_type=True) # string_type=True if value needs quotes

    def set_network_type(self, vm_id, card_index, net_type): # Renamed 'type' to 'net_type'
        # Command: 'set network card connection type of vm id "{}" with index {} to "{}"'
        # This seems like a custom command rather than direct property set.
        # Or it could be: `set connection of network card index {} of hardware of vm id "{}" to "{}"`
        # For now, stick to the provided custom command structure.
        command = 'set network card connection type of vm id "{}" with index {} to "{}"'
        args_for_cmd = [str(vm_id), str(card_index), str(net_type)]
        return self._call_veertu_with_name_fallback(command, *args_for_cmd, id_value=vm_id, scalar=True)


    def add_network_card(self, vm_id, connection_type, model):
        command = 'add network card vm id "{}" connection type "{}" model "{}"'
        args_for_cmd = [str(vm_id), str(connection_type), str(model)]
        return self._call_veertu_with_name_fallback(command, *args_for_cmd, id_value=vm_id, scalar=True)


    def delete_network_card(self, vm_id, card_index):
        command = 'remove network card vm id "{}" index {}'
        args_for_cmd = [str(vm_id), str(card_index)]
        return self._call_veertu_with_name_fallback(command, *args_for_cmd, id_value=vm_id, scalar=True)


    def set_property(self, vm_id, property_name, value, section=None, string_type=False, **kwargs):
        # section should be a list of path elements, e.g., ['guest tools', 'advanced settings']
        # property_name is the final property in that path.

        section_path_str = ""
        if section:
            if isinstance(section, str): # Single section string
                section_path_str = "of {} ".format(section)
            elif isinstance(section, list): # List of section path elements
                section_path_str = " ".join(["of {}".format(s) for s in reversed(section)]) + " " # Reversed for AppleScript path

        # Value formatting: if string_type, enclose in quotes. Numbers/booleans usually don't need quotes.
        # AppleScript booleans are 'true'/'false' literals.
        if isinstance(value, bool):
            value_str = 'true' if value else 'false'
        elif string_type and isinstance(value, str):
            value_str = '"{}"'.format(value.replace('"', '\\"')) # Escape quotes in string value
        else:
            value_str = str(value)

        command = 'set {} {}of vm id "{}" to {}'.format(property_name, section_path_str, vm_id, value_str)

        oargs = {'scalar': True} # Default expectation for set operations
        oargs.update(kwargs)
        return self._call_veertu_with_name_fallback(command, vm_id, value_str, # vm_id, value_str are for fallback if prop name is part of id_value
                                                    id_value=vm_id, **oargs)


    def get_property(self, vm_id, property_name, section): # section is string or list
        # This is largely what _get_section does. Consider refactoring to use _get_section.
        # For now, implement as per original structure.
        section_path_str = ""
        if isinstance(section, str):
            section_path_str = "of {}".format(section)
        elif isinstance(section, list): # Assumes list is ordered correctly for AppleScript path
            section_path_str = " ".join(["of {}".format(s) for s in section])

        command = 'get {} {} of vm id "{}"'.format(property_name, section_path_str, vm_id)
        return self._call_veertu_app(command, vm_id, return_formatted=False) # Raw string output


    def version(self):
        command = 'version' # This is 'version of application "Veertu"'
        try:
            # _call_veertu_app will handle subprocess.CalledProcessError and raise VeertuAppNotFoundException if app not found
            response_list = self._call_veertu_app(command, return_formatted=True) # Expect list from _split_and_strip
            if response_list and response_list[0]: # Check if list is not empty and first item is not empty string
                return True # Successfully got a version string (content of string not checked here)
        except VeertuAppNotFoundException: # Catch specific exception from _call_veertu_app
            raise # Re-raise it as it's the expected behavior for this method
        except VeertuManagerException as e: # Catch other manager exceptions (e.g. OSA script failed for other reasons)
             # This indicates app was found but 'version' command failed.
             # Depending on desired behavior, either raise e or treat as version check failure (return False)
             # Original code implies any failure other than CalledProcessError (now VeertuAppNotFoundException) means False.
             # However, if 'version' command itself is malformed or app is in bad state, it should be an error.
             # For now, let's stick to raising if it's not specifically "app not found".
             raise VeertuManagerException("Failed to get version, app communication error: {}".format(e))

        return False # Should only be reached if response_list was empty or contained empty string


    @classmethod
    def _split_and_strip(cls, str_list_input): # Renamed str_list to str_list_input
        if not isinstance(str_list_input, str): # Ensure input is a string
            return [] # Or handle error appropriately
        # AppleScript lists are comma-separated. 'missing value' is a common placeholder.
        items = [item.strip().replace('missing value', '-') for item in str_list_input.split(',')]
        # If the only item is an empty string as a result of splitting an empty string, return empty list
        if len(items) == 1 and items[0] == '':
            return []
        return items


class VeertuManagerException(Exception):
    pass


class VMNotFoundException(VeertuManagerException):
    pass


class NoOutputFileSpecified(VeertuManagerException):
    pass


class InternalAppError(VeertuManagerException): # Typically when parsing app output fails
    pass


class ImportExportFailedException(VeertuManagerException):
    pass

class WrongProjectionException(VeertuManagerException): # Changed from Exception to VeertuManagerException
    pass

class VeertuAppNotFoundException(VeertuManagerException): # For when the Veertu.app itself isn't found/responsive
   pass


class VeertuManager120(VeertuManager): # Example for version specific manager
    pass


def get_veertu_manager(version='1.2.0'): # Version param not currently used to select class
    # Basic factory, could be extended if more manager versions are needed.
    return VeertuManager120()
