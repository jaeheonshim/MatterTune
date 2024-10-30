from __future__ import annotations

from pathlib import Path
from typing import final

import ase
from fairchem.core.datasets import AseDBDataset
from pydantic import BaseModel
from torch.utils.data import Dataset
from typing_extensions import override

from .base import DatasetProtocol


class OMAT24DatasetConfig(BaseModel):
    src: Path
    """The path to the OMAT24 dataset."""


@final
class OMAT24Dataset(DatasetProtocol, Dataset[ase.Atoms]):
    def __init__(self, config: OMAT24DatasetConfig):
        super().__init__()

        self.config = config
        self.dataset = AseDBDataset(
            config={"src": config.src},
        )

    @override
    def __getitem__(self, idx: int) -> ase.Atoms:
        atoms = self.dataset.get_atoms(idx)
        return atoms

    @override
    def __len__(self) -> int:
        return len(self.dataset)
