#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_dir"

godot_version=godot@4.7.2-stable
project_dir="$repo_dir/godot4"

if [ ! -d "$project_dir/.godot/imported" ]; then
    mise exec "$godot_version" -- godot --headless --path "$project_dir" --import
fi

exec mise exec "$godot_version" -- godot --path "$project_dir" "$@"
