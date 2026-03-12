#!/usr/bin/env bash
set -euo pipefail

# Bootstraps Python installation if needed, then runs the E-CLI Python installer.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INSTALLER_PATH="${REPO_ROOT}/scripts/install_ecli.py"

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_python_linux() {
  echo "Python not found. Attempting Linux package manager install..."

  if have_cmd apt-get; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip
    return 0
  fi
  if have_cmd dnf; then
    sudo dnf install -y python3 python3-pip
    return 0
  fi
  if have_cmd yum; then
    sudo yum install -y python3 python3-pip
    return 0
  fi
  if have_cmd pacman; then
    sudo pacman -Sy --noconfirm python python-pip
    return 0
  fi
  if have_cmd zypper; then
    sudo zypper --non-interactive install python311 python311-pip || sudo zypper --non-interactive install python3 python3-pip
    return 0
  fi
  if have_cmd apk; then
    sudo apk add --no-cache python3 py3-pip
    return 0
  fi

  echo "Could not detect a supported package manager to install Python automatically." >&2
  return 1
}

install_python_macos() {
  echo "Python not found. Attempting macOS install via Homebrew..."
  if ! have_cmd brew; then
    echo "Homebrew not found. Install Homebrew first: https://brew.sh" >&2
    return 1
  fi
  brew install python
}

resolve_python() {
  if have_cmd python3; then
    echo "python3"
    return 0
  fi
  if have_cmd python; then
    echo "python"
    return 0
  fi
  return 1
}

main() {
  if [[ ! -f "${INSTALLER_PATH}" ]]; then
    echo "Installer not found: ${INSTALLER_PATH}" >&2
    exit 1
  fi

  PYTHON_BIN=""
  if ! PYTHON_BIN="$(resolve_python)"; then
    case "$(uname -s)" in
      Linux)
        install_python_linux || exit 1
        ;;
      Darwin)
        install_python_macos || exit 1
        ;;
      *)
        echo "Unsupported Unix platform for automatic Python install: $(uname -s)" >&2
        exit 1
        ;;
    esac

    PYTHON_BIN="$(resolve_python)" || {
      echo "Python installation attempt completed, but Python is still unavailable." >&2
      exit 1
    }
  fi

  echo "Using Python runtime: ${PYTHON_BIN}"
  if [[ "${1:-}" == "--dev" ]]; then
    "${PYTHON_BIN}" "${INSTALLER_PATH}" --dev
  else
    "${PYTHON_BIN}" "${INSTALLER_PATH}"
  fi
}

main "$@"
