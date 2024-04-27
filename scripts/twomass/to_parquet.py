import argparse
from functools import partial
import glob

import healpy as hp
import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
from tqdm.contrib.concurrent import process_map

from twomass import _mapping


def ang2pix(nside, ra, dec):
    return hp.ang2pix(nside, ra, dec, lonlat=True, nest=True)


def read_table(filename, args):
    table = pcsv.read_csv(
        filename,
        read_options=pcsv.ReadOptions(
            use_threads=True, column_names=list(_mapping.keys())
        ),
        parse_options=pcsv.ParseOptions(delimiter="|"),
        convert_options=pcsv.ConvertOptions(column_types=_mapping, null_values=["\\N"]),
    )
    healpix = ang2pix(args.nside, table["ra"], table["decl"])
    table = table.append_column("healpix", [healpix])
    return table


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--nside", type=int, default=16)
    parser.add_argument("--output_dir", type=str, required=True)
    args = parser.parse_args()

    filenames = glob.glob(f"{args.data_dir}/**/psc*")

    results = process_map(partial(read_table, args=args), filenames)
    table = pa.concat_tables(results)  # , promote_options="permissive")
    pq.write_to_dataset(table, args.output_dir, partition_cols=["healpix"])
