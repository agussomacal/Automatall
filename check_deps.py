#!/usr/bin/env python3
"""
Central Dependency Checker - Managed by main.py

Checks and installs dependencies for any app using their dependencies.yaml files.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

class DependencyChecker:
    """Centralized dependency management for all apps"""

    def __init__(self, apps_dir: str):
        self.apps_dir = Path(apps_dir)
        self.detected_manager = None
        self.cache: Dict[str, bool] = {}

    def detect_package_manager(self) -> Optional[str]:
        """Detect available package manager."""
        if self.detected_manager:
            return self.detected_manager

        managers = ['apt', 'dnf', 'pacman', 'brew']

        for manager in managers:
            try:
                subprocess.run(
                    [manager, '--version'],
                    capture_output=True,
                    timeout=5
                )
                self.detected_manager = manager
                return manager
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        return None

    def load_app_dependencies(self, app_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load dependencies.yaml for a specific app.

        Args:
            app_name: Name of the app folder

        Returns:
            List of dependency configs or None if not found
        """
        deps_file = self.apps_dir / app_name / "dependencies.yaml"

        if not deps_file.exists():
            return []

        try:
            with open(deps_file, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('dependencies', [])
        except Exception as e:
            print(f"Error loading dependencies.yaml: {e}")
            return []

    def check_binary_exists(self, binary: str) -> bool:
        """Check if a binary is available in PATH."""
        if binary in self.cache:
            return self.cache[binary]

        try:
            result = subprocess.run(
                ['which', binary],
                capture_output=True,
                timeout=5
            )
            exists = result.returncode == 0
            self.cache[binary] = exists
            return exists
        except Exception:
            self.cache[binary] = False
            return False

    def get_binary_version(self, binary: str, version_flag: str) -> str:
        """Get version string for a binary."""
        try:
            result = subprocess.run(
                [binary, version_flag],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.decode('utf-8', errors='ignore').strip().split('\n')[0]
            return "unknown"
        except Exception:
            return "unknown"

    def check_dependency(self, dep: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if a single dependency is satisfied.

        Args:
            dep: Dependency config dict

        Returns:
            Tuple of (is_satisfied, status_message)
        """
        binary = dep.get('binary')
        description = dep.get('description', binary)
        optional = dep.get('optional', False)

        if not self.check_binary_exists(binary):
            if optional:
                return (True, f"⊘ {description} ({binary} - optional)")
            else:
                return (False, f"✗ {description} ({binary} not found)")

        version = self.get_binary_version(binary, dep.get('version_flag', '--version'))
        return (True, f"✓ {description} v{version}")

    def check_app(self, app_name: str) -> Tuple[bool, List[str], List[Dict]]:
        """
        Check all dependencies for an app.

        Args:
            app_name: Name of the app

        Returns:
            Tuple of (all_ok, missing_list, full_status_list)
        """
        deps = self.load_app_dependencies(app_name)

        if not deps:
            return (True, [], [])

        missing = []
        status = []

        for dep in deps:
            satisfied, msg = self.check_dependency(dep)
            status.append({'dep': dep, 'message': msg, 'satisfied': satisfied})

            if not satisfied:
                missing.append(dep)

        return (len(missing) == 0, missing, status)

    def get_install_command(self, dep: Dict[str, Any]) -> Optional[str]:
        """Get install command for a dependency based on detected package manager."""
        pm = self.detect_package_manager()

        if not pm:
            return None

        commands = dep.get('install_commands', {})
        return commands.get(pm)

    def install_missing(self, missing: List[Dict[str, Any]], sudo: bool = True) -> Tuple[bool, str]:
        """
        Install missing dependencies.

        Args:
            missing: List of missing dependency configs
            sudo: Whether to use sudo

        Returns:
            Tuple of (all_success, message)
        """
        if not missing:
            return (True, "No missing dependencies")

        success_count = 0
        fail_count = 0
        messages = []

        for dep in missing:
            cmd = self.get_install_command(dep)

            if not cmd:
                messages.append(f"✗ {dep['name']}: No install command for system")
                fail_count += 1
                continue

            # Prefix with sudo if needed
            pm = self.detect_package_manager()
            if sudo and pm and pm != 'brew':
                if not cmd.startswith('sudo'):
                    cmd = f"sudo {cmd}"

            print(f"Installing: {dep['name']}...")
            print(f"Command: {cmd}")

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0:
                    success_count += 1
                    messages.append(f"✓ {dep['name']}: Installed")
                else:
                    fail_count += 1
                    err = result.stderr[:200]
                    messages.append(f"✗ {dep['name']}: {err}")

            except subprocess.TimeoutExpired:
                fail_count += 1
                messages.append(f"✗ {dep['name']}: Timeout")
            except Exception as e:
                fail_count += 1
                messages.append(f"✗ {dep['name']}: {str(e)}")

        if fail_count == 0:
            return (True, f"All {success_count} dependencies installed")
        else:
            return (False, f"Installed {success_count}/{success_count + fail_count}.\n\n" + "\n".join(messages))

    def print_status(self, app_name: str):
        """Print human-readable status for an app."""
        all_ok, missing, status = self.check_app(app_name)

        print("=" * 60)
        print(f"Dependency Status: {app_name}")
        print("=" * 60)

        for item in status:
            print(item['message'])

        print("-" * 60)

        if all_ok:
            print("✓ All dependencies satisfied")
        else:
            pm = self.detect_package_manager()
            print(f"✗ Missing: {len(missing)} package(s)")
            print(f"Package manager: {pm or 'None detected'}")
            print("\nInstall command:")
            for dep in missing:
                cmd = self.get_install_command(dep)
                if cmd:
                    print(f"  {cmd}")

        print("=" * 60)


def check_app_dependencies(app_name: str, apps_dir: str) -> Tuple[bool, List[str]]:
    """
    Convenience function to check dependencies for an app.

    Args:
        app_name: App to check
        apps_dir: Path to apps directory

    Returns:
        Tuple of (all_ok, missing_names)
    """
    checker = DependencyChecker(apps_dir)
    all_ok, missing, _ = checker.check_app(app_name)
    missing_names = [dep['name'] for dep in missing]
    return (all_ok, missing_names)


def install_app_dependencies(app_name: str, apps_dir: str, sudo: bool = True) -> Tuple[bool, str]:
    """
    Convenience function to install dependencies for an app.

    Args:
        app_name: App to fix
        apps_dir: Path to apps directory
        sudo: Whether to use sudo

    Returns:
        Tuple of (all_success, message)
    """
    checker = DependencyChecker(apps_dir)
    _, missing, _ = checker.check_app(app_name)
    return checker.install_missing(missing, sudo)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Central dependency checker')
    parser.add_argument('app', nargs='?', default=None, help='App name to check')
    parser.add_argument('--apps-dir', default='./apps', help='Path to apps directory')
    parser.add_argument('--install', '-i', action='store_true', help='Auto-install missing')
    parser.add_argument('--list-all', '-l', action='store_true', help='Check all apps')

    args = parser.parse_args()

    checker = DependencyChecker(args.apps_dir)

    if args.list_all:
        print("Checking all apps...")
        for app_dir in sorted(Path(args.apps_dir).iterdir()):
            if app_dir.is_dir() and not app_dir.name.startswith('_'):
                checker.print_status(app_dir.name)
                print()
    elif args.app:
        if args.install:
            success, msg = install_app_dependencies(args.app, args.apps_dir, sudo=True)
            print(f"\n{msg}")
        else:
            checker.print_status(args.app)
    else:
        print("Usage: check_deps.py <app_name> [--install]")
        print("       check_deps.py --list-all")
        print("       check_deps.py --help")