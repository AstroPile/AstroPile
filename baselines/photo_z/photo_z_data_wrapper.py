import sys
sys.path.append('../')  # TODO
import torch
from datasets.arrow_dataset import Dataset as HF_Dataset  # for typing etc
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader
from dataset_utils import compute_dataset_statistics, normalize_sample, get_nested


class DatasetWrapper(LightningDataModule):
    def __init__(self, 
                 train_dataset: HF_Dataset, 
                 test_dataset: HF_Dataset,
                 feature_flag: str = 'images_by_batch.array',
                 label_flag: str = 'label',
                 feature_dynamic_range: bool = True,
                 feature_z_score: bool = True,
                 batch_size: int = 128, 
                 num_workers: int = 8, 
                 val_size: float = 0.2, 
                 loading: str = 'iterated', 
                 ):
        super().__init__()
        """
        Initializes the data module with a dataset that is already loaded, setting up parameters
        for data processing and batch loading.

        Parameters:
<<<<<<<< HEAD:baselines/galaxy10_decals/dataset_wrapper.py
        - train_dataset (Dataset): The pre-loaded dataset, expected to be a torch.utils.data.Dataset with images in size B x C x H x W.
        - test_dataset (Dataset): The pre-loaded dataset, expected to be a torch.utils.data.Dataset with images in size B x C x H x W.
========
        - dataset (Dataset): The pre-loaded dataset, expected to be a torch.utils.data.Dataset with images in size B x C x H x W.
        - batch_size (int): The size of each data batch for loading.
        - num_workers (int): Number of subprocesses to use for data loading.
        - val_size (float): The proportion of the dataset to reserve for validation.
        - split_method (str): Strategy for splitting the dataset ('naive' implemented).
        - loading (str): Approach for loading the dataset ('full' or 'iterated').
>>>>>>>> b0e569a0c2daac7ac865c24cea2a95c018ce0e75:baselines/photo_z/photo_z_data_wrapper.py
        - feature_flag (str): The key in the dataset corresponding to the image data.
        - label_flag (str): The key in the dataset corresponding to the redshift data.
        - feature_dynamic_range (bool): Flag indicating whether dynamic range compression should be applied.
        - batch_size (int): The size of each data batch for loading.
        - num_workers (int): Number of subprocesses to use for data loading.
        - loading (str): Approach for loading the dataset ('full' or 'iterated').

        """

        self._train_dataset = train_dataset
        self.test_dataset = test_dataset

        self.feature_flag = feature_flag
        self.feature_dynamic_range = feature_dynamic_range
        self.feature_z_score = feature_z_score

        self.label_flag = label_flag

        self.batch_size = batch_size
        self.num_workers = num_workers
        self.prepare_data_per_node = False
        self.loading = loading

        self.val_size = 0.2

    def prepare_data(self):
        # Compute the dataset statistics
        if self.feature_z_score:
            self.feature_mean, self.feature_std = compute_dataset_statistics(self._train_dataset, flag=self.feature_flag, loading=self.loading)
        if self.label_z_score:
            self.label_mean, self.label_std = compute_dataset_statistics(self._train_dataset, flag=self.label_flag, loading=self.loading)

        # Split the dataset
        train_test_split = self._train_dataset.train_test_split(test_size=self.val_size)
        self.train_dataset = train_test_split['train']
        self.val_dataset = train_test_split['test']

    def setup(self, stage=None):
        pass

    def collate_fn(self, batch):
        batch = torch.utils.data.default_collate(batch)
        x = normalize_sample(get_nested(batch, self.feature_flag), self.feature_mean, self.feature_std, dynamic_range=self.feature_dynamic_range, z_score=self.feature_z_score) # dynamic range compression and z-score normalization
        y = normalize_sample(get_nested(batch, self.label_flag), self.label_mean, self.label_std, dynamic_range=self.label_dynamic_range, z_score=self.label_z_score)
        return x, y

    def train_dataloader(self):
        return DataLoader(self.train_dataset, batch_size=self.batch_size, num_workers=self.num_workers, collate_fn=self.collate_fn)
    
    def val_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.batch_size, num_workers=self.num_workers, collate_fn=self.collate_fn)
    
    def test_dataloader(self):
        return DataLoader(self.test_dataset, batch_size=self.batch_size, num_workers=self.num_workers, collate_fn=self.collate_fn)
    
    
