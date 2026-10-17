#!/usr/bin/env bash

_setup_was_sourced=0
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  _setup_was_sourced=1
fi

setup_atlas_environment() {
  local project_dir
  project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || return 1

  if ! command -v python3 >/dev/null 2>&1; then
    printf 'Error: python3 is required but was not found in PATH.\n' >&2
    return 1
  fi

  if [[ ! -f "$project_dir/requirements.txt" ]]; then
    printf 'Error: requirements.txt not found in %s.\n' "$project_dir" >&2
    return 1
  fi

  printf 'Creating virtual environment in %s/.venv ...\n' "$project_dir"
  python3 -m venv "$project_dir/.venv" || return 1

  printf 'Installing project requirements ...\n'
  "$project_dir/.venv/bin/python" -m pip install -r "$project_dir/requirements.txt" || return 1

  # Sourcing this script keeps the activated environment in the caller's shell.
  source "$project_dir/.venv/bin/activate" || return 1
  printf 'Virtual environment activated: %s\n' "$VIRTUAL_ENV"
}

setup_atlas_environment
_setup_status=$?
unset -f setup_atlas_environment
if [[ "$_setup_status" -ne 0 ]]; then
  if [[ "$_setup_was_sourced" -eq 1 ]]; then
    return "$_setup_status"
  fi
  exit "$_setup_status"
fi
unset _setup_status _setup_was_sourced
