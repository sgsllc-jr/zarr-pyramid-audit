#!/usr/bin/env bash
# env.sh - portable project environment bootstrap for the research toolkit.
#
# Usage:   source ./env.sh
# Safe to source repeatedly. Never exits the calling shell on failure; it
# sets RT_ENV_OK=0 and prints a diagnostic instead, so an interactive shell
# is never killed by sourcing this.
#
# Portability contract:
#   - No WSL assumptions. No /mnt/c. No hard-coded absolute paths.
#   - Detects NVIDIA (CUDA), AMD (ROCm/HIP) or no accelerator, and reports
#     which. Never assumes CUDA: the toolkit is expected to run on ROCm
#     hosts (gfx1151) and on CPU-only cloud workers as well.
#   - Degrades cleanly: absence of an accelerator is a normal outcome,
#     not an error.

# ---- locate project root (works when sourced from anywhere) ----------------
if [ -n "${BASH_SOURCE[0]:-}" ]; then
    _rt_src="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
    _rt_src="${(%):-%x}"
else
    _rt_src="$0"
fi
RT_ROOT="$(cd "$(dirname "$_rt_src")" && pwd)"
export RT_ROOT
export RT_LIB="$RT_ROOT/lib"
export RT_BIN="$RT_ROOT/bin"
export RT_TMP="$RT_ROOT/tmp"
mkdir -p "$RT_TMP"

RT_ENV_OK=1

# ---- python virtualenv -----------------------------------------------------
RT_VENV="$RT_ROOT/.venv"
if [ -x "$RT_VENV/bin/python" ]; then
    # shellcheck disable=SC1091
    . "$RT_VENV/bin/activate"
    RT_PYTHON="$RT_VENV/bin/python"
else
    echo "env.sh: WARNING no venv at $RT_VENV" >&2
    echo "env.sh:   create with: python3 -m venv \"$RT_VENV\"" >&2
    RT_PYTHON="$(command -v python3 || true)"
    RT_ENV_OK=0
fi
export RT_PYTHON

# make lib/ importable without installing a package
case ":${PYTHONPATH:-}:" in
    *":$RT_ROOT:"*) ;;
    *) export PYTHONPATH="$RT_ROOT${PYTHONPATH:+:$PYTHONPATH}" ;;
esac

# ---- CPU topology ----------------------------------------------------------
if command -v nproc >/dev/null 2>&1; then
    RT_CORES="$(nproc)"
elif command -v sysctl >/dev/null 2>&1; then
    RT_CORES="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
else
    RT_CORES=4
fi
export RT_CORES
export RT_WORKERS="${RT_WORKERS:-$RT_CORES}"

# ---- accelerator probe (portable; NVIDIA *or* AMD *or* none) ---------------
# Rationale: nvidia-smi is frequently NOT on PATH even when the driver works
# (notably in WSL, where it lives in /usr/lib/wsl/lib, and that directory is
# only added to PATH for interactive shells). Probe known locations rather
# than trusting PATH, but do not *persist* any of them into the environment
# of scripts -- callers should use RT_SMI, not assume a PATH entry exists.
RT_ACCEL="none"
RT_SMI=""
RT_ACCEL_NAME=""

_rt_try_nvidia() {
    local c
    for c in \
        "$(command -v nvidia-smi 2>/dev/null)" \
        /usr/lib/wsl/lib/nvidia-smi \
        /usr/local/cuda/bin/nvidia-smi \
        /opt/cuda/bin/nvidia-smi \
        /usr/bin/nvidia-smi
    do
        [ -n "$c" ] && [ -x "$c" ] || continue
        if timeout -k 5 25 "$c" --query-gpu=name --format=csv,noheader </dev/null >/dev/null 2>&1; then
            RT_SMI="$c"; RT_ACCEL="cuda"
            RT_ACCEL_NAME="$(timeout -k 5 25 "$c" --query-gpu=name,memory.total --format=csv,noheader </dev/null 2>/dev/null | head -1)"
            return 0
        fi
    done
    return 1
}

_rt_try_amd() {
    local c
    for c in \
        "$(command -v rocm-smi 2>/dev/null)" \
        /opt/rocm/bin/rocm-smi \
        "$(command -v rocminfo 2>/dev/null)" \
        /opt/rocm/bin/rocminfo
    do
        [ -n "$c" ] && [ -x "$c" ] || continue
        if timeout -k 5 25 "$c" </dev/null >/dev/null 2>&1; then
            RT_SMI="$c"; RT_ACCEL="rocm"
            RT_ACCEL_NAME="$(timeout -k 5 25 "$c" </dev/null 2>/dev/null | grep -oE 'gfx[0-9a-f]+' | head -1)"
            [ -z "$RT_ACCEL_NAME" ] && RT_ACCEL_NAME="rocm device"
            return 0
        fi
    done
    return 1
}

if [ "${RT_SKIP_ACCEL_PROBE:-0}" != "1" ]; then
    _rt_try_nvidia || _rt_try_amd || true
fi
export RT_ACCEL RT_SMI RT_ACCEL_NAME
unset -f _rt_try_nvidia _rt_try_amd

# ---- report ----------------------------------------------------------------
rt_env_report() {
    echo "project root : $RT_ROOT"
    echo "python       : $RT_PYTHON"
    if [ -n "$RT_PYTHON" ] && [ -x "$RT_PYTHON" ]; then
        echo "             : $("$RT_PYTHON" -V 2>&1)"
    fi
    echo "venv active  : ${VIRTUAL_ENV:-<none>}"
    echo "cores        : $RT_CORES  (RT_WORKERS=$RT_WORKERS)"
    echo "output dir   : $RT_TMP"
    case "$RT_ACCEL" in
        cuda) echo "accelerator  : NVIDIA/CUDA -- ${RT_ACCEL_NAME}" ;
              echo "             : smi at $RT_SMI" ;;
        rocm) echo "accelerator  : AMD/ROCm -- ${RT_ACCEL_NAME}" ;
              echo "             : smi at $RT_SMI" ;;
        *)    echo "accelerator  : none detected (CPU-only; this is fine)" ;;
    esac
    echo "env ok       : $RT_ENV_OK"
}
export RT_ENV_OK

if [ "${RT_QUIET:-0}" != "1" ]; then
    rt_env_report
fi
