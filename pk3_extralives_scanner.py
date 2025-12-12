"""
MBII Extra Lives Scanner
Finds all characters across .pk3 files that have more than one life and exports to JSON.
"""

import os
import sys
import json
from typing import List

from pk3_character_reader import read_pk3_characters, export_to_json


def find_pk3_files(root_dir: str) -> List[str]:
    """Recursively find all .pk3 files in a directory tree."""
    pk3_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith('.pk3'):
                pk3_files.append(os.path.join(dirpath, filename))
    return pk3_files


def scan_mbii_for_extralives(mbii_dir: str):
    """Scan all .pk3 files under mbii_dir and return characters with extralives >= 1."""
    results = []
    pk3_files = find_pk3_files(mbii_dir)
    if not pk3_files:
        print(f"No .pk3 files found under: {mbii_dir}")
        return results

    print(f"Found {len(pk3_files)} .pk3 file(s) to scan.")
    for pk3_path in pk3_files:
        print(f"Scanning: {pk3_path}")
        try:
            chars = read_pk3_characters(pk3_path)
        except Exception as e:
            print(f"  - Error reading {pk3_path}: {e}")
            continue

        for char in chars:
            try:
                if char.extralives is not None and int(char.extralives) >= 0:
                    results.append(char)
            except Exception:
                # If extralives is not parseable as int, skip
                continue

    print(f"Matched {len(results)} character(s) with extralives >= 0.")
    return results


def export_extralives_only(characters, output_file):
    """
    Export only extra life data to a JSON file.
    Only includes: filename, name, mb_class, and extralives fields.
    
    Args:
        characters: List of CharacterInfo objects
        output_file: Path to output JSON file
    """
    try:
        # Build a dictionary keyed by character name with minimal data
        characters_by_name = {}
        for idx, char in enumerate(characters, start=1):
            # Prefer the parsed name; fallback to filename or an index-based key
            base_key = (char.name or os.path.basename(char.filename) if char.filename else None) or f"character_{idx}"
            key = base_key
            # Ensure unique keys by appending a numeric suffix when needed
            suffix = 2
            while key in characters_by_name:
                key = f"{base_key} ({suffix})"
                suffix += 1
            
            # Only include extra life related data
            characters_by_name[key] = {
                'filename': char.filename,
                'name': char.name,
                'mb_class': char.mb_class,
                'extralives': char.extralives
            }

        # Convert to JSON structure
        data = {
            'total_characters': len(characters_by_name),
            'characters': characters_by_name
        }

        # Write to JSON file with nice formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n Successfully exported {len(characters_by_name)} characters (extra lives only) to: {output_file}")
        print(f"  File size: {os.path.getsize(output_file):,} bytes")
        return True

    except Exception as e:
        print(f"\n✗ Error exporting to JSON: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("MBII Extra Lives Scanner")
        print("="*80)
        print("\nUsage:")
        print(f"  python {os.path.basename(__file__)} <path_to_MBII_folder> [--json output.json] [--extralivesonly]")
        print("\nOptions:")
        print("  --json <file>       Specify output JSON file (default: extralives.json)")
        print("  --extralivesonly    Only include extra life data in JSON output")
        print("\nExample:")
        print(f"  python {os.path.basename(__file__)} C:/Games/JediAcademy/GameData/MBII --json data/extralives.json --extralivesonly")
        sys.exit(1)

    mbii_dir = os.path.normpath(sys.argv[1])
    json_output = None
    extralives_only = False
    
    # Parse command line arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--json' and i + 1 < len(sys.argv):
            json_output = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--extralivesonly':
            extralives_only = True
            i += 1
        else:
            i += 1
    
    if not json_output:
        json_output = os.path.join(os.getcwd(), 'extralives.json')

    if not os.path.isdir(mbii_dir):
        print(f"Error: Directory not found: {mbii_dir}")
        sys.exit(2)

    print(f"Scanning MBII folder: {mbii_dir}")
    print("-"*80)

    matches = scan_mbii_for_extralives(mbii_dir)

    # Export based on flag
    if extralives_only:
        success = export_extralives_only(matches, json_output)
    else:
        # Export using existing exporter (keys by character name)
        success = export_to_json(matches, json_output)
    
    if not success:
        sys.exit(3)


if __name__ == "__main__":
    main()


