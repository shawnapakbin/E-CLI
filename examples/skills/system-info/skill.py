"""System information skill implementation."""

from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class SystemInfoSkill(BaseSkill):
    """System information and monitoring utilities."""

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return SkillMetadata(
            name="system-info",
            version="1.0.0",
            description="System information and monitoring utilities",
            author="E-CLI Team",
            category="system",
            tags=["system", "monitoring", "diagnostics", "info"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        info_type = kwargs.get("info_type")

        if not info_type:
            return False, "info_type parameter is required"

        valid_types = ["os", "cpu", "memory", "disk", "network", "processes", "uptime"]
        if info_type not in valid_types:
            return False, f"Invalid info_type: {info_type}. Must be one of: {', '.join(valid_types)}"

        return True, ""

    def _get_os_info(self) -> str:
        """Get operating system information."""
        info_parts = [
            f"System: {platform.system()}",
            f"Release: {platform.release()}",
            f"Version: {platform.version()}",
            f"Machine: {platform.machine()}",
            f"Processor: {platform.processor()}",
            f"Python: {sys.version.split()[0]}",
        ]
        return "\n".join(info_parts)

    def _get_cpu_info(self) -> str:
        """Get CPU information."""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["lscpu"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout if result.returncode == 0 else "CPU info not available"
            elif platform.system() == "Darwin":  # macOS
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return f"CPU: {result.stdout.strip()}"
            else:
                return f"CPU: {platform.processor()}"
        except Exception as e:
            return f"Error getting CPU info: {e}"

    def _get_memory_info(self) -> str:
        """Get memory information."""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["free", "-h"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout
            elif platform.system() == "Darwin":
                result = subprocess.run(
                    ["vm_stat"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout
            else:
                return "Memory info not available on this platform"
        except Exception as e:
            return f"Error getting memory info: {e}"

    def _get_disk_info(self) -> str:
        """Get disk information."""
        try:
            if platform.system() in ["Linux", "Darwin"]:
                result = subprocess.run(
                    ["df", "-h"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout
            else:
                return "Disk info not available on this platform"
        except Exception as e:
            return f"Error getting disk info: {e}"

    def _get_network_info(self) -> str:
        """Get network information."""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["ip", "addr", "show"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout
            elif platform.system() == "Darwin":
                result = subprocess.run(
                    ["ifconfig"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.stdout
            else:
                return "Network info not available on this platform"
        except Exception as e:
            return f"Error getting network info: {e}"

    def _get_processes_info(self) -> str:
        """Get process information."""
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Return first 20 lines
            lines = result.stdout.split("\n")[:20]
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting process info: {e}"

    def _get_uptime_info(self) -> str:
        """Get system uptime."""
        try:
            result = subprocess.run(
                ["uptime"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error getting uptime: {e}"

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute system info operation."""
        info_type = kwargs["info_type"]

        try:
            if info_type == "os":
                output = self._get_os_info()
            elif info_type == "cpu":
                output = self._get_cpu_info()
            elif info_type == "memory":
                output = self._get_memory_info()
            elif info_type == "disk":
                output = self._get_disk_info()
            elif info_type == "network":
                output = self._get_network_info()
            elif info_type == "processes":
                output = self._get_processes_info()
            elif info_type == "uptime":
                output = self._get_uptime_info()
            else:
                return SkillResult(
                    ok=False,
                    output="",
                    error=f"Unknown info_type: {info_type}",
                )

            return SkillResult(
                ok=True,
                output=output,
                metadata={"info_type": info_type, "system": platform.system()},
            )

        except Exception as e:
            return SkillResult(
                ok=False,
                output="",
                error=f"System info operation failed: {e}",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["os", "cpu", "memory", "disk", "network", "processes", "uptime"],
                    "description": "Type of system information to retrieve",
                },
            },
            "required": ["info_type"],
        }


# Export the skill instance
skill = SystemInfoSkill()
