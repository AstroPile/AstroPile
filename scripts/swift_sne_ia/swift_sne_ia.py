# Copyright 2020 The HuggingFace Datasets Authors and the current dataset script contributor.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datasets
from datasets import Features, Value, Sequence
from datasets.data_files import DataFilesPatternsDict
import itertools
import h5py
import numpy as np
import os


# Find for instance the citation on arxiv or on the dataset repo/website
_CITATION = """
@ARTICLE{2014Ap&SS.354...89B,
       author = {{Brown}, Peter J. and {Breeveld}, Alice A. and {Holland}, Stephen and {Kuin}, Paul and {Pritchard}, Tyler},
        title = "{SOUSA: the Swift Optical/Ultraviolet Supernova Archive}",
      journal = {\apss},
     keywords = {Supernovae, Ultraviolet, Astrophysics - High Energy Astrophysical Phenomena, Astrophysics - Cosmology and Nongalactic Astrophysics},
         year = 2014,
        month = nov,
       volume = {354},
       number = {1},
        pages = {89-96},
          doi = {10.1007/s10509-014-2059-8},
archivePrefix = {arXiv},
       eprint = {1407.3808},
 primaryClass = {astro-ph.HE},
       adsurl = {https://ui.adsabs.harvard.edu/abs/2014Ap&SS.354...89B},
      adsnote = {Provided by the SAO/NASA Astrophysics Data System}
}
"""

# You can copy an official description
_DESCRIPTION = """
Time-series dataset from Swift SNe Ia.

Data Citations:

Brown et al. (2014)
"""

_HOMEPAGE = "https://pbrown801.github.io/SOUSA"


_LICENSE = "GNU LESSER GENERAL PUBLIC LICENSE"

_VERSION = "0.0.1"

_STR_FEATURES = [
    "object_id",
    "obj_type"
]

_FLOAT_FEATURES = [
    "ra", 
    "dec", 
    "redshift",
    "host_log_mass"
]


class SwiftSNIa(datasets.GeneratorBasedBuilder):
    """"""

    VERSION = _VERSION

    BUILDER_CONFIGS = [
        datasets.BuilderConfig(
            name="swift_sne_ia",
            version=VERSION,
            data_files=DataFilesPatternsDict.from_patterns({"train": ["./healpix=*/*.hdf5"]}), # This seems fairly inflexible. Probably a massive failure point.
            description="Light curves from Swift SNe Ia",
        ),
    ]

    DEFAULT_CONFIG_NAME = "swift_sne_ia"

    @classmethod
    def _info(self):
        """Defines the features available in this dataset."""
        # Starting with all features common to light curve datasets
        features = {
            'lightcurve': Sequence(feature={
                'band': Value('string'),
                'flux': Value('float32'),
                'flux_err': Value('float32'),
                'time': Value('float32'),
            }),
        }


        # Adding all values from the catalog
        for f in _FLOAT_FEATURES:
            features[f] = Value("float32")
        for f in _STR_FEATURES:
            features[f] = Value("string")

        return datasets.DatasetInfo(
            # This is the description that will appear on the datasets page.
            description=_DESCRIPTION,
            # This defines the different columns of the dataset and their types
            features=Features(features),
            # Homepage of the dataset for documentation
            homepage=_HOMEPAGE,
            # License for the dataset if available
            license=_LICENSE,
            # Citation for the dataset
            citation=_CITATION,
        )

    def _split_generators(self, dl_manager):
        """We handle string, list and dicts in datafiles"""
        if not self.config.data_files:
            raise ValueError(
                f"At least one data file must be specified, but got data_files={self.config.data_files}"
            )
        splits = []
        for split_name, files in self.config.data_files.items():
            if isinstance(files, str):
                files = [files]
            splits.append(
                datasets.SplitGenerator(name=split_name, gen_kwargs={"files": files})
            )
        return splits

    def _generate_examples(self, files, object_ids=None):
        """Yields examples as (key, example) tuples."""
        if object_ids is not None:
            files = [f for f in files if os.path.split(f)[-1][:-5] in object_ids]
            # Filter files by object_id
        for file in files:
            with h5py.File(file, "r") as data:
                # Parse data
                idxs = np.arange(0, data["flux"].shape[0])
                band_idxs = idxs.repeat(data["flux"].shape[-1]).reshape(
                    len(data["bands"][()].decode('utf-8').split(",")), -1
                )
                bands = data["bands"][()].decode('utf-8').split(",")
                example = {
                    "lightcurve": {
                        "band": np.asarray([bands[band_number] for band_number in band_idxs.flatten().astype("int32")]).astype("str"),
                        "time": np.asarray(data["time"]).flatten().astype("float32"),
                        "flux": np.asarray(data["flux"]).flatten().astype("float32"),
                        "flux_err": np.asarray(data["flux_err"]).flatten().astype("float32"),
                    }
                }
                    
                # Add remaining features
                for f in _FLOAT_FEATURES:
                    example[f] = np.asarray(data[f]).astype("float32")
                for f in _STR_FEATURES:
                    example[f] = data[f][()].decode('utf-8')

                yield str(data["object_id"][()]), example