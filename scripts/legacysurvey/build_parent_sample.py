from astropy.io import fits
from astropy.table import Table, join, vstack, hstack
from astropy.wcs import WCS
from astropy.nddata import Cutout2D
from multiprocessing import Pool
from filelock import FileLock
import healpy as hp
from tqdm import tqdm
import numpy as np
import h5py
import glob
import os
import argparse
import time 

_pixel_scale = 0.262
_healpix_nside = 16
_cutout_size = 160
_filters = ['DES-G', 'DES-R', 'DES-I', 'DES-Z']

_utf8_filter_type = h5py.string_dtype('utf-8', 5)
_utf8_filter_typeb = h5py.string_dtype('utf-8', 16)

def dr10_south_selection_fn(catalog, zmag_cut=21.):
    """ Selection function applied to the DECaLS DR10 South catalog.    
    """
    # Magnitude cut
    mask_mag = (22.5 - 2.5*np.log10(catalog['FLUX_Z']/catalog['MW_TRANSMISSION_Z'])) < zmag_cut

    # Require observations in all bands
    flux_bands=['G', 'R', 'I', 'Z']
    nobs = np.array([catalog['NOBS_'+fb] for fb in flux_bands]).T
    mask_obs = ~np.any(nobs ==  0, axis=1)

    # Remove point sources
    mask_type = catalog['TYPE'] != 'PSF'

    # Quality cuts
    # See definition of mask bits here:
    # https://www.legacysurvey.org/dr10/bitmasks/
    # This will remove all objects on the borders of images
    # or directly affected by brigh stars or saturating any of the bands
    maskbits = [0, 1, 2, 3, 4, 5, 6, 7, 11, 14, 15]
    mask_clean = np.ones(len(catalog), dtype=bool)
    m = catalog['MASKBITS'] 
    for bit in maskbits:
        mask_clean &= (m & 2**bit)==0

    return mask_mag & mask_clean & mask_obs & mask_type

def _read_catalog(sweep_file):
    catalog = Table.read(sweep_file)
    selected = dr10_south_selection_fn(catalog)
    catalog = catalog[selected]
    catalog['healpix'] = hp.ang2pix(_healpix_nside, catalog['RA'], catalog['DEC'], lonlat=True, nest=True)
    return catalog

def build_catalog_dr10_south(legacysurvey_root_dir, output_dir, num_processes=1, n_output_files=10, proc_id=None):
    """ Process all sweep catalogs and apply selection function to build the parent sample.
    """
    # Get a list of all sweep files in the catalog directory
    sweep_files = glob.glob(os.path.join(legacysurvey_root_dir + '/dr10/south/sweep/10.1/', '*.fits'))
    print('Found {} sweep files'.format(len(sweep_files)))
    print('Number of output files: {}'.format(n_output_files))
    output_files = []
    # Read the files in parallel
    with Pool(num_processes) as pool:
        print('Successfully started pool')
        n_files = len(sweep_files)
        batch_size = n_files//n_output_files
        for i in range(n_output_files):
            if proc_id is not None and i != proc_id:
                continue
            print('processing chunk of files {} out of {}'.format(i, n_output_files))
            file_path = os.path.join(output_dir, 'dr10_south_{}.fits'.format(i))
            if os.path.exists(file_path):
                output_files.append(file_path)
                continue
            results = list(tqdm(pool.imap(_read_catalog, sweep_files[i*batch_size:(i+1)*batch_size]), total=batch_size))
            if i == n_output_files - 1:
                results += list(tqdm(pool.imap(_read_catalog, sweep_files[(i+1)*batch_size:])))
            parent_sample = vstack(results, join_type='exact')
            parent_sample.write(file_path, overwrite=True)
            output_files.append(file_path)
    return output_files

def _processing_fn(args):
    """ Function that processes all the bricks that fall in a given healpix index
    """
    group, legacysurvey_root_dir, group_filename = args

    # Create unique object ids for the group
    group['gid'] = np.arange(len(group))

    # Group the objects by brick
    bricks = group.group_by('BRICKNAME')

    # Loop over the bricks
    for brick in bricks.groups:
        # Create a cutout for each object in the brick
        out_images = []

        brick_name = brick['BRICKNAME'][0]
        brick_group = brick_name[:3]
        # Load all the images for this brick
        images = {}
        brick_path = os.path.join(legacysurvey_root_dir, f'dr10/south/coadd/{brick_group}/{brick_name}')

        # Check if the path to this brick exists, if not, we skip it
        if not os.path.exists(brick_path):
            continue

        for band in ['image-g', 'image-r', 'image-i', 'image-z', 
                     'invvar-g', 'invvar-r', 'invvar-i', 'invvar-z',
                     'maskbits']:
            image_filename = os.path.join(legacysurvey_root_dir, f'dr10/south/coadd/{brick_group}/{brick_name}', 'legacysurvey-{}-{}.fits.fz'.format(brick_name, band))
            with fits.open(image_filename) as hdul:
                images[band] = hdul[1].copy()

        # Post processing the mask to make it binary
        data = images['maskbits'].data 
        maskclean = np.ones_like(data, dtype=bool)
        set_maskbits = [0, 1, 2, 3, 4, 5, 6, 7, 11, 14, 15]         
        for bit in set_maskbits:
            maskclean &= (data & 2**bit)==0
        images['maskbits'].data = maskclean.astype(data.dtype)

        for obj in brick:
            # Create a cutout for each band
            ra, dec = obj['RA'], obj['DEC']
            wcs = WCS(images['image-g'].header)
            x, y = wcs.all_world2pix(ra, dec, 1)
            position = (x, y)
            size = (_cutout_size, _cutout_size)

            # Build image
            image = []
            for band in ['image-g', 'image-r', 'image-i', 'image-z']:
                image.append(Cutout2D(images[band].data, position, size, wcs=wcs).data)
            image = np.stack(image, axis=0)

            # Build inverse variance
            invvar = []
            for band in ['invvar-g', 'invvar-r', 'invvar-i', 'invvar-z']:
                invvar.append(Cutout2D(images[band].data, position, size, wcs=wcs).data)
            invvar = np.stack(invvar, axis=0)

            # Build mask
            mask = Cutout2D(images['maskbits'].data, position, size, wcs=wcs).data

            out_images.append({
                    'object_id': np.array(f'{obj["BRICKNAME"]}-{obj["OBJID"]}', dtype=_utf8_filter_typeb),
                    'gid': obj['gid'],
                    'image_band': np.array([f.lower().encode("utf-8") for f in _filters], dtype=_utf8_filter_type),
                    'image_ivar': invvar,
                    'image_array': image,
                    'image_mask': mask.astype('bool'),
                    'image_psf_fwhm': np.array([obj[f'PSFSIZE_{b}'] for b in ['G', 'R', 'I', 'Z']]),
                    'image_scale': np.array([_pixel_scale for f in _filters]).astype(np.float32),
            })

        # If we didn't find any images, we return 0
        if len(out_images) == 0:
            continue

        # Aggregate all images into an astropy table
        images = Table({k: [d[k] for d in out_images] for k in out_images[0].keys()})

        # Join on object_id with the input catalog
        catalog = join(group, images, 'gid', join_type='inner')
            
        # Create the output directory if it does not exist
        out_path = os.path.dirname(group_filename)
        if not os.path.exists(out_path):
            os.makedirs(out_path)

        with FileLock(group_filename + ".lock"):
            if os.path.exists(group_filename):
                # Load the existing file and concatenate the data with current data
                with h5py.File(group_filename, 'a') as hdf5_file:
                    for key in catalog.colnames:
                        shape = catalog[key].shape
                        hdf5_file[key].resize(hdf5_file[key].shape[0] + shape[0], axis=0)
                        hdf5_file[key][-shape[0]:] = catalog[key]
            else:           
                # This is the first time we write the file, so we define the datasets
                with h5py.File(group_filename, 'w') as hdf5_file:
                    for key in catalog.colnames:
                        shape = catalog[key].shape
                        if len(shape) == 1:
                            hdf5_file.create_dataset(key, data=catalog[key], compression="gzip", chunks=True, maxshape=(None,))
                        else:
                            hdf5_file.create_dataset(key, data=catalog[key], compression="gzip", chunks=True, maxshape=(None, *shape[1:]))

        del catalog, images, out_images

    return 1

def extract_cutouts(parent_sample, legacysurvey_root_dir,  output_dir, num_processes=1, proc_id=None):
    """ Extract cutouts for all detections in the parent sample   
    """
    # Load catalog
    parent_sample = Table.read(parent_sample)

    # Group objects by healpix index
    groups = parent_sample.group_by('healpix')

    # Create output directory if it does not exist
    out_path = os.path.join(output_dir, 'dr10_south_21')
    
    # Loop over the groups
    map_args = []
    for group in groups.groups:
        group_filename = os.path.join(out_path, 'healpix={}/001-of-001.hdf5'.format(group['healpix'][0]))
        map_args.append((group, legacysurvey_root_dir, group_filename))

    # Run the parallel processing
    with Pool(num_processes) as pool:
        results = pool.map(_processing_fn, map_args)                       

    if np.sum(results) == len(groups.groups):
        print('Done!')
    else:
        print("Warning, unexpected number of results, some files may not have been exported as expected")

def main(args):
    # Create the output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # Check if ran as part of a slurm job, if so, only the procid will be processed
    slurm_procid = int(os.getenv('SLURM_PROCID')) if 'SLURM_PROCID' in os.environ else None

    # Build the catalogs
    catalog_files = build_catalog_dr10_south(args.data_dir, args.output_dir, 
                                             num_processes=args.num_processes,
                                             n_output_files=args.nsplits,
                                             proc_id=slurm_procid)
    if args.catalog_only:
        return

    # Extract the cutouts
    for sample in catalog_files:
        print("Processing file", sample)
        extract_cutouts(sample, args.data_dir, args.output_dir, 
                        num_processes=args.num_processes, proc_id=slurm_procid)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Builds a catalog for the Legacy Survey images from DR10.')
    parser.add_argument('data_dir', type=str, help='Path to the local copy of the data')
    parser.add_argument('output_dir', type=str, help='Path to the output directory')
    parser.add_argument('--num_processes', type=int, default=20, help='Number of parallel processes to use')
    parser.add_argument('--catalog_only', action='store_true', help='Only compile the catalog, do not extract cutouts')
    parser.add_argument('--nsplits', type=int, default=10, help='Number of splits for the catalog')
    args = parser.parse_args()
    main(args)
