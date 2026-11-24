#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_dir"

godot_version=godot@4.7.2-stable
project_dir="$repo_dir/godot4"
cache_dir="$project_dir/.godot"
sky_import="$project_dir/assets/linear_track_sky.jpg.import"

sky_cache_ready() {
    [ -f "$sky_import" ] || return 1
    for format in s3tc etc2; do
        cache_path=$(sed -n "s|^path\\.$format=\"res://\\(.*\\)\"$|\\1|p" "$sky_import")
        if [ -z "$cache_path" ] || [ ! -s "$project_dir/$cache_path" ]; then
            return 1
        fi
    done
}

prepare_imports() (
    flock 9
    if ! sky_cache_ready; then
        # Godot regenerates missing files but can skip empty ones.
        for cache_path in "$cache_dir"/imported/linear_track_sky.jpg-*.ctex; do
            if [ -f "$cache_path" ] && [ ! -s "$cache_path" ]; then
                rm -f -- "$cache_path"
            fi
        done
        mise exec "$godot_version" -- godot --headless --path "$project_dir" --import
        if ! sky_cache_ready; then
            printf '%s\n' 'Godot failed to import both sky texture formats.' >&2
            exit 1
        fi
    fi
)

mkdir -p "$cache_dir"
prepare_imports 9>>"$cache_dir/gnoom-import.lock"

exec mise exec "$godot_version" -- godot --path "$project_dir" "$@"
