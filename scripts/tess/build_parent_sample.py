import os
import argparse
import numpy as np
from astropy.io import fits
from astropy.table import Table, join
from multiprocessing import Pool
from tqdm import tqdm
import h5py
import healpy as hp
from astropy.units import cds
from quality import TESSQualityFlags

_healpix_nside = 16

# Breakdown of the different TESS pipelines, each one will be stored as a subdataset
PIPELINES = ['spoc  ']

def processing_fn(args):
    """ Parallel processing function reading all requested light curves from one sector.
    """
    filename, object_id = args

    with fits.open(filename, mode='readonly', memmap=True) as hdu:
        # The header of hdu[0] contains the following information:
        # Page 34, Section 5 - https://archive.stsci.edu/files/live/sites/mast/files/home/missions-and-data/active-missions/tess/_documents/EXP-TESS-ARC-ICD-TM-0014-Rev-F.pdf

        telescope = hdu[0].header.get('TELESCOP')
        if telescope == 'TESS' and hdu[0].header.get('ORIGIN') == 'NASA/Ames':
            targetid = hdu[0].header.get('TICID')
            ra = hdu[0].header.get('RA_OBJ')
            dec = hdu[0].header.get('DEC_OBJ')

            time = hdu['LIGHTCURVE'].data['TIME']
            time_format = 'btjd'
            # Units: BTJD (Barycenter corrected TESS Julian Date; BJD - 2457000, days)

            flux = hdu['LIGHTCURVE'].data['PDCSAP_FLUX']
            flux_err = hdu['LIGHTCURVE'].data['PDCSAP_FLUX_ERR']
            # Units: e-/s (electrons per second) -> can be read from the flux files, see the TESS data products documentation (TUNIT4)

            quality = np.asarray(hdu['LIGHTCURVE'].data['QUALITY'], dtype='int32')
            quality_bitmask = TESSQualityFlags.DEFAULT_BITMASK
        
        # TODO: add support for other pipelines

    # TODO: implement normalization option into relative flux (ppm)?

    exclude_bad_data = True
    if exclude_bad_data:
        indx = TESSQualityFlags.filter(quality, flags=quality_bitmask)
        time, flux, flux_err = time[indx], flux[indx], flux_err[indx]

    # Return the results
    return {'object_id': object_id,
            'time': time, 
            'flux': flux, 
            'flux_err': flux_err
            }


def save_in_standard_format(args):
    """ This function takes care of iterating through the different input files 
    corresponding to this healpix index, and exporting the data in standard format.
    """
    
    catalog, output_filename, tess_data_path, tiny = args

    # Create the output directory if it does not exist
    if not os.path.exists(os.path.dirname(output_filename)):
        os.makedirs(os.path.dirname(output_filename))

    # Rename columns to match the standard format
    catalog['object_id'] = catalog['target_name']

    # Process all files
    results = []
    for args in catalog[['lc_path', 'object_id']]:
        results.append(processing_fn(args))

    
    # Pad all light curves to the same length
    max_length = max([len(d['time']) for d in results])
    for i in range(len(results)):
        results[i]['time'] = np.pad(results[i]['time'], (0,max_length - len(results[i]['time'])), mode='constant')
        results[i]['flux'] = np.pad(results[i]['flux'], (0,max_length - len(results[i]['flux'])), mode='constant')
        results[i]['flux_err'] = np.pad(results[i]['flux_err'], (0,max_length - len(results[i]['flux_err'])), mode='constant')
    
    # Aggregate all light curves into an astropy table
    lightcurves = Table({k: [d[k] for d in results]
                     for k in results[0].keys()})

    # Join on target id with the input catalog
    catalog = join(catalog, lightcurves, keys='object_id', join_type='inner')
    catalog.convert_unicode_to_bytestring()
    
    # Making sure we didn't lose anyone
    assert len(catalog) == len(lightcurves), "There was an error in the join operation, probably some spectra files are missing"

    # Save all columns to disk in HDF5 format
    with h5py.File(output_filename, 'w') as hdf5_file:
        for key in catalog.colnames:
            hdf5_file.create_dataset(key, data=catalog[key])
    return 1

def main(args):
    # Load the catalog file and apply main cuts
    catalog = Table.read(os.path.join(args.tess_data_path, "tess_lc_catalog_sector_64.csv"))
    
    # Add healpix index to the catalog
    catalog['healpix'] = hp.ang2pix(_healpix_nside, catalog['RA'], catalog['DEC'], lonlat=True, nest=True)

    #TODO: add support for multiple pipelines, currently only using SPOC
    for pipeline in PIPELINES:
        print("Processing pipeline:", pipeline)

        cat_pipeline = catalog
        #cat_pipeline = catalog[catalog['PIPELINE'] == pipeline]
        
        cat_pipeline = cat_pipeline.group_by(['healpix'])
    
        map_args = []
        for group in cat_pipeline.groups:
            # Create a filename for the group
            group_filename = os.path.join(args.output_dir, '{}/healpix={}/001-of-001.hdf5'.format(pipeline.strip(), group['healpix'][0]))
            
            map_args.append((group, group_filename, args.tess_data_path, args.tiny))

        # Run the parallel processing
        with Pool(args.num_processes) as pool:
            results = list(tqdm(pool.imap(save_in_standard_format, map_args), total=len(map_args)))

        if sum(results) != len(map_args):
            print("There was an error in the parallel processing, some files may not have been processed correctly")

        print("All done!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extracts light curves from all TESS light curves downloaded from MAST')
    parser.add_argument('tess_data_path', type=str, help='Path to the local copy of the TESS data')
    parser.add_argument('output_dir', type=str, help='Path to the output directory')
    parser.add_argument('-nproc', '--num_processes', type=int, default=10, help='The number of processes to use for parallel processing')
    parser.add_argument('--tiny', action='store_true', help='Use a tiny subset of the data for testing')
    args = parser.parse_args()

    main(args)