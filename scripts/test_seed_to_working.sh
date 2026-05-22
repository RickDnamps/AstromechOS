#!/bin/bash
# Test: seed_to_working copies NEW files only, never overwrites working.
# This validates the copy-new-only semantics the seed/working model relies on.
set -e
seed_to_working() {  # $1=seed dir, $2=working dir
    [ -d "$1" ] || return 0
    mkdir -p "$2"
    rsync -a --ignore-existing "$1/" "$2/"
}
TMP=$(mktemp -d)
mkdir -p "$TMP/seed" "$TMP/work"
echo "shipped-v1" > "$TMP/seed/a.txt"
echo "shipped-v1" > "$TMP/seed/b.txt"
echo "operator-edit" > "$TMP/work/a.txt"   # operator already changed a.txt
seed_to_working "$TMP/seed" "$TMP/work"
# a.txt must keep the operator's content (not overwritten)
[ "$(cat "$TMP/work/a.txt")" = "operator-edit" ] || { echo "FAIL: a.txt overwritten"; exit 1; }
# b.txt is new -> must be copied
[ "$(cat "$TMP/work/b.txt")" = "shipped-v1" ] || { echo "FAIL: b.txt not copied"; exit 1; }
# operator-only file in work must survive
echo "operator-custom" > "$TMP/work/c.txt"
seed_to_working "$TMP/seed" "$TMP/work"
[ "$(cat "$TMP/work/c.txt")" = "operator-custom" ] || { echo "FAIL: c.txt lost"; exit 1; }
echo "PASS"
rm -rf "$TMP"
