"""Property-based tests for probe_concurrency_limit in hardware.py."""

from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from e_cli.sub_agent.hardware import probe_concurrency_limit


class TestProbeConcurrencyLimitProperties:
    """Property-based tests for probe_concurrency_limit."""

    @given(cpu=st.integers(0, 64), ram=st.integers(0, 256))
    def test_hardware_limit_formula_correctness(self, cpu: int, ram: int) -> None:
        """Property 1: Concurrency limit formula correctness.

        Validates: Requirements 1.2
        """
        mock_vm = MagicMock()
        mock_vm.available = ram * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=cpu or None),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit()

        effective_cpu = cpu or 1
        expected = max(1, min(effective_cpu // 2, ram // 2))
        assert result == expected

    @given(n=st.integers(1, 10000))
    def test_env_override_cap_enforcement(self, n: int) -> None:
        """Property 2: Environment variable cap enforcement.

        Validates: Requirements 1.6, 10.6
        """
        mock_vm = MagicMock()
        mock_vm.available = 16 * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=8),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit(env_override=n)

        assert result == min(n, 16)


class TestProbeConcurrencyLimitUnit:
    """Unit tests for probe_concurrency_limit edge cases."""

    def test_psutil_import_error_falls_back_to_1(self) -> None:
        """When psutil is unavailable, concurrency_limit falls back to 1."""
        import sys
        import builtins

        real_import = builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("psutil not available")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_mock_import):
            # Re-import the module to trigger the ImportError path
            import importlib
            import e_cli.sub_agent.hardware as hw_mod
            # Patch at the module level instead
            with patch.object(hw_mod, "probe_concurrency_limit", wraps=hw_mod.probe_concurrency_limit):
                pass

        # Test the ImportError branch directly by patching psutil in the module
        with patch.dict("sys.modules", {"psutil": None}):
            result = probe_concurrency_limit()
        assert result == 1

    def test_config_override_used_when_positive(self) -> None:
        """config_override > 0 is used when no env_override is set."""
        mock_vm = MagicMock()
        mock_vm.available = 16 * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=8),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit(config_override=3)

        assert result == 3

    def test_config_override_zero_uses_hardware(self) -> None:
        """config_override=0 (default) falls through to hardware-derived limit."""
        mock_vm = MagicMock()
        mock_vm.available = 8 * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=8),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit(config_override=0)

        # cpu//2=4, ram//2=4 → min(4,4)=4
        assert result == 4

    def test_env_override_takes_priority_over_config(self) -> None:
        """env_override takes priority over config_override."""
        mock_vm = MagicMock()
        mock_vm.available = 16 * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=8),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit(env_override=5, config_override=3)

        assert result == 5

    def test_env_override_zero_not_used(self) -> None:
        """env_override=0 is treated as not set; falls through to hardware."""
        mock_vm = MagicMock()
        mock_vm.available = 8 * (1024**3)

        with (
            patch("psutil.cpu_count", return_value=8),
            patch("psutil.virtual_memory", return_value=mock_vm),
        ):
            result = probe_concurrency_limit(env_override=0)

        assert result == 4
