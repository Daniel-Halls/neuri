.PHONY: all install sync bootstrap cli test lint format clean help

all: install

# ------------------------------------------------------------------------------
# Automated Installation Script
# ------------------------------------------------------------------------------
define NEURI_INSTALL_SCRIPT
set -euo pipefail

# ANSI color formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

log_info() {
    printf "$${BLUE}ℹ$${RESET} %b\n" "$$1"
}

log_success() {
    printf "$${GREEN}✓$${RESET} %b\n" "$$1"
}

log_warn() {
    printf "$${YELLOW}⚠$${RESET} %b\n" "$$1"
}

log_error() {
    printf "$${RED}✗$${RESET} %b\n" "$$1" >&2
}

echo -e "$${BOLD}====================================================$${RESET}"
echo -e "$${BOLD}          Neuri Automated Installer                 $${RESET}"
echo -e "$${BOLD}====================================================$${RESET}"

# 1. Resolve repository directory
REPO_DIR="$(CURDIR)"
cd "$${REPO_DIR}"

log_info "Workspace root: $${BOLD}$${REPO_DIR}$${RESET}"

# 2. Verify or locate uv
UV_BIN=""
if command -v uv >/dev/null 2>&1; then
    UV_BIN="$$(command -v uv)"
elif [[ -x "$${HOME}/.local/bin/uv" ]]; then
    UV_BIN="$${HOME}/.local/bin/uv"
elif [[ -x "$${HOME}/.cargo/bin/uv" ]]; then
    UV_BIN="$${HOME}/.cargo/bin/uv"
fi

if [[ -z "$${UV_BIN}" ]]; then
    log_warn "uv package manager not detected. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [[ -x "$${HOME}/.local/bin/uv" ]]; then
        UV_BIN="$${HOME}/.local/bin/uv"
    elif [[ -x "$${HOME}/.cargo/bin/uv" ]]; then
        UV_BIN="$${HOME}/.cargo/bin/uv"
    else
        log_error "Failed to locate uv after install. Please install uv manually: https://docs.astral.sh/uv/"
        exit 1
    fi
fi

UV_VERSION="$$("$${UV_BIN}" --version)"
log_success "Found uv: $${BOLD}$${UV_BIN}$${RESET} ($${UV_VERSION})"

# 3. Synchronize repository virtual environment and dependencies
log_info "Synchronizing dependencies via uv..."
"$${UV_BIN}" sync --all-extras

# 4. Install neuri CLI into ~/.local/bin as editable tool
log_info "Installing 'neuri' CLI tool into ~/.local/bin/..."
"$${UV_BIN}" tool install --editable . --force

# 5. Bootstrap ~/.neuri base directory from ./neuri
log_info "Bootstrapping base assets into $${HOME}/.neuri/..."
if [[ -x "$${HOME}/.local/bin/neuri" ]]; then
    "$${HOME}/.local/bin/neuri" install --force
else
    "$${UV_BIN}" run neuri install --force
fi

# 6. Check and configure PATH if needed
LOCAL_BIN="$${HOME}/.local/bin"
PATH_CONFIGURED=false

if [[ ":$$PATH:" == *":$${LOCAL_BIN}:"* ]]; then
    PATH_CONFIGURED=true
fi

if [[ "$${PATH_CONFIGURED}" == false ]]; then
    log_warn "$${LOCAL_BIN} is not in your current PATH."
    CURRENT_SHELL="$$(basename "$${SHELL:-bash}")"
    RC_FILE=""
    if [[ "$${CURRENT_SHELL}" == "zsh" ]]; then
        RC_FILE="$${HOME}/.zshrc"
    elif [[ "$${CURRENT_SHELL}" == "bash" ]]; then
        RC_FILE="$${HOME}/.bashrc"
    fi

    if [[ -n "$${RC_FILE}" && -f "$${RC_FILE}" ]]; then
        if ! grep -q 'export PATH=.*\.local/bin' "$${RC_FILE}"; then
            echo '' >> "$${RC_FILE}"
            echo '# Added by Neuri installer' >> "$${RC_FILE}"
            echo 'export PATH="$$HOME/.local/bin:$$PATH"' >> "$${RC_FILE}"
            log_success "Added $${LOCAL_BIN} to $${RC_FILE}"
        fi
    else
        log_info "Please ensure $${LOCAL_BIN} is added to your PATH in your shell configuration."
    fi
fi

# 7. Verification check
NEURI_BIN="$${LOCAL_BIN}/neuri"
if [[ -x "$${NEURI_BIN}" ]]; then
    NEURI_VER="$$("$${NEURI_BIN}" --version 2>/dev/null || echo "0.1.0")"
    log_success "Neuri CLI verified: $${BOLD}$${NEURI_VER}$${RESET}"
fi

echo ""
echo -e "$${GREEN}$${BOLD}====================================================$${RESET}"
echo -e "$${GREEN}$${BOLD}       Neuri Successfully Installed!                $${RESET}"
echo -e "$${GREEN}$${BOLD}====================================================$${RESET}"
echo -e "• CLI Executable : $${BOLD}$${LOCAL_BIN}/neuri$${RESET}"
echo -e "• Assets & Config: $${BOLD}$${HOME}/.neuri/$${RESET}"
echo ""
echo -e "To launch the interactive chat interface anywhere, run:"
echo -e "    $${BOLD}neuri$${RESET}"
echo ""
echo -e "To run headless commands or check status:"
echo -e "    $${BOLD}neuri -p \"/skills\"$${RESET}"
echo -e "    $${BOLD}neuri -p \"/status\"$${RESET}"
echo ""
endef
export NEURI_INSTALL_SCRIPT

install:
	@bash -c "$$NEURI_INSTALL_SCRIPT"

sync:
	uv sync --all-extras

cli:
	uv tool install --editable . --force

bootstrap:
	uv run neuri install --force

test:
	uv run pytest -v

lint:
	uv run ruff check
	uv run mypy src

format:
	uv run ruff format
	uv run ruff check --fix

clean:
	-rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info 2>/dev/null || true

help:
	@echo "Neuri Makefile targets:"
	@echo "  make install    - Full automated installation (uv, dependencies, CLI, ~/.neuri, PATH)"
	@echo "  make sync       - Synchronize dependencies with uv"
	@echo "  make cli        - Install neuri executable into ~/.local/bin"
	@echo "  make bootstrap  - Seed ~/.neuri with base templates and assets"
	@echo "  make test       - Run test suite with pytest"
	@echo "  make lint       - Run ruff and mypy linters"
	@echo "  make format     - Auto-format code with ruff"
	@echo "  make clean      - Remove build and test caches"
	@echo "  make help       - Show this help message"
