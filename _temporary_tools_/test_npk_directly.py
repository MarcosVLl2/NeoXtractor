#!/usr/bin/env python3
"""Simple script to test NPK extraction directly."""

# TODO: script should be removed once NPK module is migrated.

from concurrent.futures import ThreadPoolExecutor
import time
import asyncio
import os
import sys
import traceback

import _use_application_modules # pylint: disable=unused-import

# Import the NPK module
from core.npk import NPKFile

async def main():
    """Main function to test NPK file extraction."""
    # Path to the NPK file
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_npk_file>")
        return 1

    npk_path = os.path.expanduser(sys.argv[1])

    if not os.path.exists(npk_path):
        print(f"Error: File does not exist: {npk_path}")
        return 1

    print(f"Opening NPK file: {npk_path}")

    try:
        # Create output directory
        output_dir = os.path.expanduser("./npk_test_output")
        os.makedirs(output_dir, exist_ok=True)

        # Open NPK file
        npk = NPKFile(npk_path)
        print("File opened successfully")
        print(f"File count: {npk.file_count}")

        with ThreadPoolExecutor() as executor:
            print(f"Extracting files to {output_dir}")

            start_time = time.time()
            extracted = []
            extract_list = []
            for i in range(npk.file_count):
                try:
                    def save_to_file(index):
                        entry = npk.read_entry(index)
                        out_file = os.path.join(output_dir, entry.filename)

                        print(f"Extracting file {index}: {len(entry.data)} bytes, extension: {entry.extension}")
                        entry.save_to_file(out_file)
                        extracted.append(out_file)
                        print(f"Saved to: {out_file}")

                    extract_list.append(executor.submit(save_to_file, i))
                except Exception as e:
                    print(f"Error extracting file {i}: {e}")
                    traceback.print_exc()

            for extract in extract_list:
                extract.result()

            end_time = time.time()
            mt_total_time = end_time - start_time

            print(f"Extracted {len(extracted)} files")
            print(f"Extraction completed in {mt_total_time:.2f} seconds")

        npk = NPKFile(npk_path)

        print(f"Extracting files to {output_dir}")

        start_time = time.time()
        extracted = []
        extract_list = []
        for i in range(npk.file_count):
            try:
                entry = npk.read_entry(i)
                out_file = os.path.join(output_dir, entry.filename)

                print(f"Extracting file {i}: {len(entry.data)} bytes, extension: {entry.extension}")
                entry.save_to_file(out_file)
                extracted.append(out_file)
                print(f"Saved to: {out_file}")
            except Exception as e:
                print(f"Error extracting file {i}: {e}")
                traceback.print_exc()

        end_time = time.time()
        total_time = end_time - start_time

        print(f"Extracted {len(extracted)} files")
        print(f"Extraction completed in {total_time:.2f} seconds")

        print(f"Multi-thread extraction time: {mt_total_time:.2f} seconds")
        print(f"Single-thread extraction time: {total_time:.2f} seconds")

        return 0
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
