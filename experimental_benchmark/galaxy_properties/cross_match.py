import os
import argparse
import datasets
from astropile.utils import cross_match_datasets


def cross_match(
    left: str, 
    right: str, 
    local_astropile_root: str,
    cache_dir: str, 
    matching_radius: float = 1.0, # in arcseconds
    num_proc: int = 0,
):
    # Get paths
    left_path = os.path.join(local_astropile_root, left)
    right_path = os.path.join(local_astropile_root, right)

    # Load datasets
    left = datasets.load_dataset_builder(left_path, trust_remote_code=True)
    right = datasets.load_dataset_builder(right_path, trust_remote_code=True)

    # Cross-match datasets
    dset = cross_match_datasets(
        left,
        right,
        matching_radius=matching_radius,
        cache_dir=cache_dir, # automatically saved to cache_dir
        num_proc=num_proc,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cross-match two datasets')
    parser.add_argument('left', type=str, help='Path to the left dataset')
    parser.add_argument('right', type=str, help='Path to the right dataset')
    parser.add_argument('local_astropile_root', type=str, help='Path to the local astropile root')
    parser.add_argument('cache_dir', type=str, help='Path to the cache directory')
    parser.add_argument('--matching_radius', type=float, default=1.0, help='Matching radius in arcseconds')
    parser.add_argument('--num_proc', type=int, default=0, help='Number of processes to use')

    args = parser.parse_args()

    cross_match(args.left, args.right, args.local_astropile_root, args.cache_dir, args.matching_radius, args.num_proc)
    