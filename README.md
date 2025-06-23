# Veertu Desktop Hosted Hypervisor & CLI

## Overview

Veertu Desktop Hosted Hypervisor (VDHH) is the core hypervisor platform for the Veertu Desktop product, a native Type 2 virtualization solution for macOS that runs Linux and Windows VMs. It leverages Apple's Hypervisor.Framework and QEMU's device emulation codebase, providing a lightweight, responsive, and resource-efficient virtualization experience without requiring kernel extensions (KEXTs).

This project also includes `veertu-cli`, a Python-based command-line interface for managing Veertu VMs. The CLI interacts with the Veertu Desktop application to provide scripting and automation capabilities.

Veertu Desktop supports Vagrant, features an API for custom automation, and offers shared folders and Copy/Paste for Windows VMs. Advanced features like Level 2 Bridged networking and USB Passthrough are implemented via privileged helpers.

This README provides information on both the core VDHH and the Python CLI.

## Download & Installation

To Install Veertu Desktop on Mac, please visit [veertu.com](https://veertu.com) and follow updates on twitter @veertu_labs.

## Community
Join our Slack community to discuss and give feedback
https://slack.veertu.com/

## Building (Core Hypervisor)

The core VDHH components are primarily C and Objective-C and are managed via Xcode.
To build VDHH with corresponding dependencies, use `vmx.xcworkspace` from the project root:

```
xcodebuild -workspace vmx.xcworkspace -scheme vmx
```

## Environment (Core Hypervisor)

VDHH can be launched as a standalone application from the command line:

```
vmx -vm <path_to_vm_folder>
```

but to achieve full set of features, it have to be launched by Veertu Desktop
app. Veertu Desktop configures environment of vmx process and contains number of
helper tools, used by vdhh. To start custom version of vdhh the `vdlaunch` tool
(shipped with Veertu Desktop) could be used

```
vdlaunch [-vmx <path_to_custom_vdhh/Contents/MacOS/vmx>] [-vm vm_name_or_path]
```

If __-vmx__ argument is omitted, default (being shipped with Veertu Desktop)
hypervisor will be used to run VM.

## Python CLI (`veertu-cli`)

This section focuses on the Python-based command-line interface.

### Python CLI Installation

The `veertu-cli` is packaged using Hatch and can be installed from the source or a built wheel.

1.  **Prerequisites:**
    *   Python 3.8+
    *   `pip` and `uv` (recommended for virtual environments)

2.  **Install from source (for development):**
    It's recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (example using venv)
    python3 -m venv .venv
    source .venv/bin/activate

    # Install using pip with the editable flag
    pip install -e .
    ```
    This will install the CLI in editable mode, meaning changes to the source code in `src/veertu_cli` will be immediately reflected. Dependencies like `click` and `tabulate` will also be installed.

    Alternatively, using Hatch for environment management:
    ```bash
    hatch env create
    # To run commands within the Hatch-managed environment:
    # hatch run default:veertu-cli --help
    ```

3.  **Install from a built wheel (for distribution):**
    If you have a `.whl` file (e.g., from the `dist/` directory after building):
    ```bash
    pip install veertu_vmm-<version>-py3-none-any.whl
    ```

### Python CLI Usage

Once installed, the CLI can be invoked as `veertu-cli`.

**Basic Commands:**

*   **List VMs:**
    ```bash
    veertu-cli list
    ```

*   **Show VM details:**
    ```bash
    veertu-cli show <vm_id_or_name>
    ```
    Example: `veertu-cli show my-linux-vm`

*   **Start a VM:**
    ```bash
    veertu-cli start <vm_id_or_name>
    ```

*   **Shutdown a VM:**
    ```bash
    veertu-cli shutdown <vm_id_or_name>
    ```
    Add `--force` to force shutdown.

*   **Get help:**
    ```bash
    veertu-cli --help
    veertu-cli <command> --help
    ```

For more commands and options, use the `--help` flag. The CLI supports machine-readable output via the `--machine-readable` global option, which will format output as JSON.

## Packaging the Python CLI

The Python CLI (`veertu-cli`) can be packaged into a source distribution (sdist) and a wheel using [Hatch](https://hatch.pypa.io/).

1.  **Ensure Hatch is installed:**
    ```bash
    pip install hatch uv
    ```
    (uv is recommended for faster environment management with Hatch).

2.  **Build the packages:**
    From the root of the repository, run:
    ```bash
    hatch run default:build
    ```
    This command (defined in `pyproject.toml`) will clean any previous builds and create new `sdist` and `wheel` files in the `dist/` directory.

## Publishing the Python CLI (to PyPI or a private index)

Publishing requires [Twine](https://twine.readthedocs.io/).

1.  **Ensure Twine is installed** (if not already in your Hatch environment or globally):
    ```bash
    pip install twine
    ```

2.  **Build the packages** (if not already done):
    ```bash
    hatch run default:build
    ```

3.  **Upload to PyPI:**
    The `pyproject.toml` includes a convenience script:
    ```bash
    hatch run default:publish
    ```
    This will use Twine to upload the packages in the `dist/` directory. You will be prompted for your PyPI username and password (or an API token).

    Alternatively, to upload manually or to a test PyPI instance:
    ```bash
    # For TestPyPI
    twine upload --repository testpypi dist/*
    # For main PyPI
    twine upload dist/*
    ```

    To upload to a private repository, configure Twine accordingly (e.g., via `~/.pypirc` or environment variables) and use:
    ```bash
    twine upload --repository YOUR_PRIVATE_REPO_NAME dist/*
    ```

## Contributing

Contributions to both the core hypervisor and the Python CLI are welcome. Please follow these guidelines.

### Codebase Structure

*   **Core Hypervisor (C/Objective-C):**
    *   The majority of the virtualization logic, device emulation (based on QEMU), and Hypervisor.Framework interactions reside in directories like `audio/`, `block/`, `devices/`, `hw/`, `slirp/`, `vmm/`, etc.
    *   macOS specific UI and application logic can be found in `window/`, `vmmanager/`, and related Objective-C files.
    *   Builds are managed via Xcode (`vmx.xcworkspace`).
*   **Python CLI (`veertu-cli`):**
    *   Located in `src/veertu_cli/`.
    *   `cli_interface.py`: Defines the Click-based command structure and user interactions.
    *   `veertu_manager.py`: Contains the `VeertuManager` class responsible for interfacing with the Veertu Desktop application via AppleScript (`osascript`). This is the bridge between the Python CLI and the core hypervisor functionalities.
    *   `formatter.py`: Handles output formatting (tabular for humans, JSON for machine-readable).
    *   `utils.py`: Utility functions.
    *   Packaging and dependency management are handled by `pyproject.toml` using Hatch.

### Development Environment (Python CLI)

1.  **Clone the repository.**
2.  **Set up a Python virtual environment** (e.g., using `venv` or `virtualenv`) with Python 3.8+.
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  **Install Hatch and uv:**
    ```bash
    pip install hatch uv
    ```
4.  **Create the Hatch development environment:**
    This will install the project in editable mode and all development dependencies.
    ```bash
    hatch env create
    ```
5.  **Activate pre-commit hooks** (recommended):
    ```bash
    pip install pre-commit # If not already installed
    pre-commit install
    ```

### Running Checks (Python CLI)

Use Hatch to run quality assurance checks from the root of the repository:

*   **Linting and Formatting (Ruff):**
    ```bash
    hatch run default:lint  # Check formatting and lint issues
    hatch run default:format # Apply formatting and auto-fixes
    ```
    The pre-commit hooks will also run these automatically.

*   **Type Checking (MyPy):**
    ```bash
    hatch run default:typecheck
    ```
    The pre-commit hook for mypy will also perform these checks.

*   **Tests (Pytest):**
    ```bash
    hatch run default:test
    ```
    This will run tests located in the `tests/` directory. Please add tests for new functionality or bug fixes.

### Commit Messages

Please follow conventional commit message guidelines for clarity (e.g., a short subject line, followed by a more detailed body if necessary). While not strictly enforced by tooling yet, good commit messages are appreciated.

## License

VDHH is licensed under the terms of [GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html).
