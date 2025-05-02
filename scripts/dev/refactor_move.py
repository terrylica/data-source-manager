#!/usr/bin/env python3
"""
Move files with git mv, refactor imports with Rope, and verify with Ruff.

This script helps move Python files while automatically handling import refactoring
and verifying the changes don't introduce import-related errors.
"""

import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import git  # Use GitPython instead of subprocess
import typer
from rich.console import Console
from rich.prompt import Confirm
from rope.base.libutils import path_to_resource
from rope.base.project import Project
from rope.refactor.move import MoveModule

from utils.logger_setup import logger

logger.setLevel("DEBUG")

console = Console()

# Define the specific Ruff import-related codes to check
RUFF_IMPORT_CHECKS = [
    "F821",  # Undefined name
    "F822",  # Undefined name '...' in __all__
    "F823",  # Local variable '...' referenced before assignment
    "F401",  # F401: 'module.name' imported but unused
    "F402",  # F402: Module 'module' imported more than once
    "F403",  # F403: 'from module import *' used; unable to detect undefined names
    "F632",  # F632: Use of `in <constant>` where <constant> is a list or tuple. Use a set instead.
    "F841",  # F841: Local variable '...' is assigned to but never used
    "I001",  # Unsorted imports
    "ARG",  # Unused arguments
    "B006",  # Mutable argument default
    "B008",  # Function call in default argument
    "PLC0415",  # Import outside top level
]

# Configure typer app with explicit help options to ensure -h works
app = typer.Typer(
    help="Move files with git, refactor imports, and verify with Ruff",
    context_settings={"help_option_names": ["--help", "-h"]},
)

# Define all commands using the decorator approach
moves_argument = typer.Argument(
    ...,
    help="Pairs of source and destination paths in format 'source.py:destination.py'. Source must exist.",
)
project_option = typer.Option(
    ".", "--project", "-p", help="Root of your Python project"
)
dry_run_option = typer.Option(
    False, "--dry-run", "-d", help="Show what would happen without making changes"
)
verbose_option = typer.Option(
    0,
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity: -v for INFO, -vv for DEBUG",
)
log_file_option = typer.Option(
    None,
    "--log-file",
    "-l",
    help="Custom log file name (default: refactor_YYYYMMDD_HHMMSS.log)",
)


@contextmanager
def rope_project(project_path: Path):
    """Context manager for Rope projects to ensure proper cleanup."""
    project = Project(str(project_path))
    try:
        yield project
    finally:
        project.close()


def git_mv(old_path: Path, new_path: Path, dry_run: bool = False) -> bool:
    """Move a file using git mv."""
    # Check if source file exists
    if not old_path.exists():
        logger.error(f"Source file does not exist: {old_path}")
        return False

    if dry_run:
        logger.info(f"[DRY-RUN] git mv {old_path} {new_path}")
        return True

    try:
        # Use GitPython to move the file
        repo = git.Repo(search_parent_directories=True)
        repo.git.mv(str(old_path), str(new_path))
        logger.info(f"Moved {old_path} -> {new_path}")
        return True
    except git.GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        return False


def run_command(cmd: List[str], dry_run: bool = False) -> subprocess.CompletedProcess:
    """Run a command with proper error handling and dry-run support."""
    command_str = " ".join(cmd)
    logger.debug(f"Run command: {command_str}")

    if dry_run:
        logger.info(f"[DRY-RUN] Would run: {command_str}")
        # Return a dummy CompletedProcess for dry-run
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command_str}")
        logger.error(f"Return code: {e.returncode}")
        if e.stdout:
            logger.debug(f"Command stdout: {e.stdout}")
        if e.stderr:
            logger.debug(f"Command stderr: {e.stderr}")
        raise


def run_ruff(project_path: Path, dry_run: bool = False) -> bool:
    """Run Ruff to check for import-related issues."""
    if dry_run:
        logger.info(
            f"[DRY-RUN] Ruff would run: ruff check {project_path} --select {','.join(RUFF_IMPORT_CHECKS)}"
        )
        return True

    logger.info("Running Ruff sanity check...")
    try:
        cmd = [
            "ruff",
            "check",
            str(project_path),
            "--select",
            ",".join(RUFF_IMPORT_CHECKS),
        ]
        result = run_command(cmd, dry_run)

        # If stdout contains "All checks passed!" or is empty, it's a success
        if not result.stdout or "All checks passed!" in result.stdout:
            logger.info("Ruff found no import-related issues.")
            return True

        # Otherwise, there are actual issues
        logger.warning(f"Ruff detected issues:\n{result.stdout}")
        return False
    except Exception as e:
        logger.error(f"Ruff check failed: {e}")
        return False


def fix_ruff_issues(project_path: Path, dry_run: bool = False) -> bool:
    """Fix import-related issues using Ruff's auto-fix capability."""
    if dry_run:
        logger.info(
            f"[DRY-RUN] Ruff would fix: ruff check {project_path} --select {','.join(RUFF_IMPORT_CHECKS)} --fix"
        )
        return True

    logger.info("Applying Ruff fixes to import-related issues...")
    try:
        cmd = [
            "ruff",
            "check",
            str(project_path),
            "--select",
            ",".join(RUFF_IMPORT_CHECKS),
            "--fix",
        ]
        result = run_command(cmd, dry_run)

        if "error:" in result.stderr.lower():
            logger.error(f"Ruff fix encountered errors:\n{result.stderr}")
            return False

        fixed_count = result.stdout.count("fixed")
        if fixed_count > 0:
            logger.info(f"Ruff automatically fixed {fixed_count} import-related issues")
        else:
            logger.info("No import-related issues required fixing by Ruff")

        return True
    except Exception as e:
        logger.error(f"Ruff fix failed: {e}")
        return False


def run_ruff_pre_check(project_path: Path, dry_run: bool = False) -> bool:
    """Run Ruff to check for import-related issues before we start moving files."""
    if dry_run:
        logger.info(
            f"[DRY-RUN] Ruff would run pre-check: ruff check {project_path} --select {','.join(RUFF_IMPORT_CHECKS)}"
        )
        return True

    logger.info("Running Ruff pre-check for existing import issues...")
    try:
        cmd = [
            "ruff",
            "check",
            str(project_path),
            "--select",
            ",".join(RUFF_IMPORT_CHECKS),
        ]
        result = run_command(cmd, dry_run)

        # If stdout contains "All checks passed!" or is empty, it's a success
        if not result.stdout or "All checks passed!" in result.stdout:
            logger.info("Ruff pre-check passed: no pre-existing import issues found.")
            return True

        # Otherwise, there are actual issues
        logger.warning(f"Ruff detected pre-existing issues:\n{result.stdout}")
        logger.warning(
            "These issues exist before refactoring. They may not be caused by the move operation."
        )
        # Use rich's Confirm for better UX
        return Confirm.ask("Continue despite pre-existing issues?")
    except Exception as e:
        logger.error(f"Ruff pre-check failed: {e}")
        return False


def update_import_paths(
    project_path: Path, old_path: Path, new_path: Path, dry_run: bool = False
) -> bool:
    """Update import paths across the codebase using Rope."""
    if dry_run:
        logger.info(
            f"[DRY-RUN] Would update import paths from {old_path} to {new_path} using Rope"
        )
        return True

    logger.info(f"Updating import paths from '{old_path}' to '{new_path}' using Rope")

    try:
        # Use context manager for Rope project
        with rope_project(project_path) as project:
            # Create relative paths to the project root
            old_rel_path = str(
                old_path.relative_to(project_path)
                if old_path.is_absolute()
                else old_path
            )
            new_rel_path = str(
                new_path.relative_to(project_path)
                if new_path.is_absolute()
                else new_path
            )

            # Get the resources
            old_resource = path_to_resource(project, old_rel_path)

            # Use MoveModule for Python files
            if old_path.suffix == ".py":
                # Create the destination folder if it doesn't exist
                new_parent = new_path.parent
                new_parent.mkdir(parents=True, exist_ok=True)

                # Get the destination folder resource
                dest_folder = str(Path(new_rel_path).parent)
                if not dest_folder:
                    dest_folder = "."

                # Get the new module name
                new_module_name = new_path.stem

                # Perform the move
                mover = MoveModule(project, old_resource)
                changes = mover.get_changes(dest_folder, new_module_name)
                project.do(changes)

                logger.info(
                    "Rope successfully updated import references across the codebase"
                )
                return True
            else:
                logger.info(
                    f"Skipping Rope import refactoring for non-Python file: {old_path}"
                )
                return True

    except Exception as e:
        logger.error(f"Error updating import paths with Rope: {e}")
        return False


@app.command()
def move(
    moves: List[str] = moves_argument,
    project: str = project_option,
    dry_run: bool = dry_run_option,
    verbose: int = verbose_option,
    log_file: Optional[str] = log_file_option,
    skip_validation: bool = typer.Option(
        False, "--skip-validation", "-s", help="Skip file existence validation"
    ),
    skip_pre_check: bool = typer.Option(
        False,
        "--skip-pre-check",
        "-S",
        help="Skip Ruff pre-check for existing import issues",
    ),
    auto_fix_imports: bool = typer.Option(
        False,
        "--auto-fix",
        "-a",
        help="Auto-fix import issues with Ruff after refactoring",
    ),
):
    """
    Move files with git mv, refactor imports via Rope, and verify with Ruff.

    This command handles moving Python files while ensuring imports remain valid.
    It first uses git mv to move the files, then uses Rope to update imports,
    and finally runs Ruff to verify no import errors were introduced.

    Example:
        ./refactor_move.py move "existing_file.py:new_location.py"
    """
    # Set default values within the function body
    if moves is None:
        moves = typer.Argument(
            ...,
            help="Pairs of source and destination paths in format 'source.py:destination.py'. Source must exist.",
        )
    if project is None:
        project = typer.Option(
            ".", "--project", "-p", help="Root of your Python project"
        )
    if dry_run is None:
        dry_run = typer.Option(
            False,
            "--dry-run",
            "-d",
            help="Show what would happen without making changes",
        )
    if verbose is None:
        verbose = typer.Option(
            0,
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity: -v for INFO, -vv for DEBUG",
        )
    if log_file is None:
        log_file = typer.Option(
            None,
            "--log-file",
            "-l",
            help="Custom log file name (default: refactor_YYYYMMDD_HHMMSS.log)",
        )
    if skip_validation is None:
        skip_validation = typer.Option(
            False, "--skip-validation", "-s", help="Skip file existence validation"
        )
    if skip_pre_check is None:
        skip_pre_check = typer.Option(
            False,
            "--skip-pre-check",
            "-S",
            help="Skip Ruff pre-check for existing import issues",
        )
    if auto_fix_imports is None:
        auto_fix_imports = typer.Option(
            False,
            "--auto-fix",
            "-a",
            help="Auto-fix import issues with Ruff after refactoring",
        )

    # Setup log file if not provided
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"refactor_{timestamp}.log"

    # Set the log level
    if verbose >= 2:
        logger.setLevel(20)  # DEBUG in rich logger
    elif verbose == 1:
        logger.setLevel(30)  # INFO in rich logger

    logger.debug(f"Arguments: moves={moves}, project={project}, dry_run={dry_run}")

    # Process each move operation
    success = True
    project_path = Path(project).resolve()

    # Run pre-check if not skipped
    if not skip_pre_check:
        if not run_ruff_pre_check(project_path, dry_run):
            logger.error("Pre-check failed. Exiting.")
            return 1
    else:
        logger.info("Skipping pre-check for existing import issues as requested.")

    # Process all move pairs
    with console.status("[bold green]Processing file moves...") as status:
        for move_pair in moves:
            try:
                old_path, new_path = move_pair.split(":")
                old_path_obj = Path(old_path)
                new_path_obj = Path(new_path)
            except ValueError:
                logger.error(
                    f"Invalid move format '{move_pair}'; use old_path:new_path"
                )
                success = False
                continue

            status.update(f"[bold green]Processing: {old_path} → {new_path}")
            logger.info(f"Processing move: {old_path} -> {new_path}")

            # Check if source exists and destination doesn't already exist
            if not old_path_obj.exists():
                if new_path_obj.exists() and not skip_validation:
                    logger.warning(
                        f"Source file {old_path} does not exist, but destination {new_path} does - assuming already moved"
                    )
                    continue
                elif skip_validation:
                    logger.warning(
                        f"Source file {old_path} does not exist, but proceeding due to --skip-validation"
                    )
                else:
                    logger.error(f"Source file does not exist: {old_path}")
                    success = False
                    continue

            # Move the file with git
            if not git_mv(old_path_obj, new_path_obj, dry_run):
                success = False
                continue

            # Update import paths across the codebase using Rope
            status.update(f"[bold blue]Updating imports: {old_path} → {new_path}")
            if not update_import_paths(
                project_path, old_path_obj, new_path_obj, dry_run
            ):
                logger.warning(
                    f"Failed to update import paths for {old_path} -> {new_path}"
                )
                success = False
                continue

    # Final verification with Ruff
    with console.status("[bold yellow]Verifying imports with Ruff..."):
        if not run_ruff(project_path, dry_run):
            logger.warning("Ruff check found issues after refactoring")

            # Try to auto-fix import issues if enabled
            if auto_fix_imports and not dry_run:
                logger.info("Attempting to auto-fix import issues with Ruff...")
                if fix_ruff_issues(project_path, dry_run):
                    logger.info("Auto-fix applied, running final verification")
                    if run_ruff(project_path, dry_run):
                        logger.info("All issues fixed automatically!")
                    else:
                        logger.error(
                            "Some issues remain after auto-fix. Manual intervention required."
                        )
                        success = False
                else:
                    logger.error("Auto-fix failed. Manual intervention required.")
                    success = False
            else:
                if auto_fix_imports and dry_run:
                    logger.info(
                        "[DRY-RUN] Would attempt to auto-fix import issues with Ruff"
                    )
                else:
                    logger.warning(
                        "Use --auto-fix flag to attempt automatic fix of import issues"
                    )
                success = False

    if success:
        console.print("[bold green]✓ All operations completed successfully.")
        return 0
    else:
        console.print("[bold red]✗ Some operations failed. Check the log for details.")
        return 1


@app.command(name="check")
def check_ruff(
    project: str = project_option,
    dry_run: bool = dry_run_option,
    verbose: int = verbose_option,
    log_file: Optional[str] = log_file_option,
):
    """
    Run Ruff to check for import-related issues on the current codebase state.
    """
    # Setup log file if not provided
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"ruff_check_{timestamp}.log"

    # Set the log level
    if verbose >= 2:
        logger.setLevel(20)  # DEBUG in rich logger
    elif verbose == 1:
        logger.setLevel(30)  # INFO in rich logger

    logger.debug(f"Arguments: project={project}, dry_run={dry_run}")

    project_path = Path(project).resolve()

    with console.status("[bold yellow]Checking code with Ruff..."):
        success = run_ruff(project_path, dry_run)

    if success:
        console.print("[bold green]✓ Ruff check completed successfully.")
        return 0
    else:
        console.print("[bold red]✗ Ruff check failed. Check the log for details.")
        return 1


if __name__ == "__main__":
    sys.exit(app())
