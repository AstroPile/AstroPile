from typing import Tuple
import urllib.request
import argparse
import os
from tqdm.contrib.concurrent import process_map

DATA_DIR = os.path.abspath(os.path.dirname(__file__))


def _download_file(file_args: Tuple[str, str]):
    output_dir, f = file_args
    f = f.strip()
    savename = f"{output_dir}/{f.split('/')[-1]}"
    if not os.path.exists(savename):
        urllib.request.urlretrieve(f, savename)


def main(args):
    if not args.aria2:
        with open(f"{DATA_DIR}/source_file_list.txt") as f:
            source_files = f.readlines()

        with open(f"{DATA_DIR}/coeff_file_list.txt") as f:
            coeff_files = f.readlines()

        if args.tiny:
            source_files = source_files[:1]
            coeff_files = coeff_files[:1]

        files_flat = [*source_files, *coeff_files]
        files_flat = [(args.output_dir, file) for file in files_flat]

        process_map(_download_file, files_flat, max_workers=16, chunksize=1)

    else:
        if args.tiny:
            with open(f"{DATA_DIR}/source_file_list.txt") as f:
                source_files = f.readline().strip()
            with open(f"{DATA_DIR}/coeff_file_list.txt") as f:
                coeff_files = f.readline().strip()

            os.system(
                f'aria2c -j2 -x2 -s2 -c -d {args.output_dir} -Z "{source_files}" "{coeff_files}"'
            )

        else:
            os.system(
                f"aria2c -j16 -x16 -s16 -c -i source_file_list.txt -d {args.output_dir}"
            )
            os.system(
                f"aria2c -j16 -x16 -s16 -c -i coeff_file_list.txt -d {args.output_dir}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aria2", help="use aria2c for downloading", action="store_true"
    )
    parser.add_argument(
        "--tiny",
        help="download a single source and coeff file only",
        action="store_true",
    )
    parser.add_argument(
        "--output_dir",
        help="output directory",
        default=".",
    )
    args = parser.parse_args()
    main(args)
