# Development Scripts README

This directory contains various scripts used for development, testing, and maintenance tasks.

## Scripts

### `clear_cache.py`

**Functionality:**

This Python script is used to clear specified cache and log directories. It supports clearing directories on local and various remote filesystems (like S3, GCS) using `fsspec`. It can recursively delete files and remove empty subdirectories while preserving the base directories. It includes options for specifying directories, filesystem protocol, storage options, running in test mode, skipping confirmation, showing version, and creating directories if missing.

**Critical Review:**

- **Strengths:** Highly flexible due to `fsspec` support; robust with test mode and confirmation; user-friendly CLI via `typer`. Specific handling for `cache_metadata.json` is useful.
- **Weaknesses:** Current implementation of logging does not fully align with the project's `utils.logger_setup` standard and imports the base `logging` module, which violates a project rule. Error handling could be more granular. May be less efficient for extremely large directories.

### `find_all_dead_code.sh`

**Functionality:**

This shell script helps identify potential dead code in the Python codebase. It first looks for "dangling" Python script files that don't seem to be imported or executed elsewhere using `grep`. It then runs the `vulture` static analysis tool to find unused functions, classes, variables, etc., within Python files. It categorizes `vulture` results by confidence level (100% and 90-99%) and provides a summary count.

**Critical Review:**

- **Strengths:** Attacks dead code from two angles; leverages the effective `vulture` tool; provides clear, colored output grouped by confidence; handles exclusions well.
- **Weaknesses:** The `grep`-based logic for finding "dangling scripts" is simplistic and prone to false positives/negatives. The script relies on external tools (`fdfind`, `vulture`) being pre-installed. The shell scripting logic for the dangling check is complex and hard to maintain.

### `install_code2prompt.sh`

**Functionality:**

This shell script automates the installation of the `code2prompt` command-line tool (written in Rust). It checks for and installs Rust/Cargo if needed, then uses `cargo install` to install `code2prompt`. It also creates a small example directory with sample Python files and provides basic usage examples after installation.

**Critical Review:**

- **Strengths:** Fully automates the installation process; checks for existing dependencies; provides clear, colored output and usage examples; includes a helpful example directory.
- **Weaknesses:** Platform-specific (Linux only); PATH management requires user action in new shells (though communicated); error handling could be more detailed; embedding example file content directly within the script makes it less readable.

### `remove_empty_dirs.sh`

**Functionality:**

This shell script finds and removes empty directories recursively from the current location downwards. It uses the `find` command with the `-empty` and `-delete` options. It excludes `.git` and `.venv` directories. The script runs the `find` command multiple times (5 iterations) to handle nested empty directories.

**Critical Review:**

- **Strengths:** Simple and effective for its purpose using standard tools; basic exclusions are helpful.
- **Weaknesses:** The loop of 5 iterations is a heuristic and might not be necessary or sufficient in all cases (a single pass with `-depth` should be enough). Excluded directories are hardcoded.

### `run_tests_parallel.sh`

**Functionality:**

This comprehensive shell script runs `pytest` tests with a focus on parallel execution using `pytest-xdist`. It defaults to 8 parallel workers but supports sequential mode (`-s`). It intelligently handles tests marked `@pytest.mark.serial` by running them separately and sequentially. The script offers interactive test selection (`-i`), passes arbitrary arguments to `pytest`, configures asyncio event loops for stability, provides a detailed error/warning summary (`-e`) with severity scoring, manages log files (including saving a clean version), and supports performance profiling (`-p`, `--profile-svg`). It also checks for and suggests installing necessary dependencies.

**Critical Review:**

- **Strengths:** Highly feature-rich, covering parallel execution, serial test handling, interactive selection, robust error analysis, logging, and profiling. Excellent internal documentation makes it very usable.
- **Weaknesses:** The script is very long and complex, making it potentially difficult to maintain and debug. Implementing complex logic like log parsing in shell script can be brittle. Relies on an external shell script (`enhanced_extract_errors.sh`) and uses `readarray` (bash-specific). Its complexity might warrant a rewrite in Python for better maintainability.
