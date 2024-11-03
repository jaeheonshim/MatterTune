from __future__ import annotations

__codegen__ = True

from typing import TYPE_CHECKING

# Config/alias imports

if TYPE_CHECKING:
    from mattertune import MatterTunerConfig as MatterTunerConfig
    from mattertune.backbones import BackboneConfig as BackboneConfig
    from mattertune.backbones import JMPBackboneConfig as JMPBackboneConfig
    from mattertune.backbones.jmp import (
        FinetuneModuleBaseConfig as FinetuneModuleBaseConfig,
    )
    from mattertune.backbones.jmp import GraphComputerConfig as GraphComputerConfig
    from mattertune.backbones.m3gnet import M3GNetBackboneConfig as M3GNetBackboneConfig
    from mattertune.backbones.m3gnet import 
    from mattertune.data import DatasetConfig as DatasetConfig
    from mattertune.data import OMAT24DatasetConfig as OMAT24DatasetConfig
    from mattertune.finetune.base import LRSchedulerConfig as LRSchedulerConfig
    from mattertune.finetune.base import OptimizerConfig as OptimizerConfig
    from mattertune.finetune.base import PropertyConfig as PropertyConfig
    from mattertune.finetune.loss import HuberLossConfig as HuberLossConfig
    from mattertune.finetune.loss import L2MAELossConfig as L2MAELossConfig
    from mattertune.finetune.loss import LossConfig as LossConfig
    from mattertune.finetune.loss import MAELossConfig as MAELossConfig
    from mattertune.finetune.loss import MSELossConfig as MSELossConfig
    from mattertune.finetune.lr_scheduler import (
        CosineAnnealingLRConfig as CosineAnnealingLRConfig,
    )
    from mattertune.finetune.lr_scheduler import ExponentialConfig as ExponentialConfig
    from mattertune.finetune.lr_scheduler import MultiStepLRConfig as MultiStepLRConfig
    from mattertune.finetune.lr_scheduler import (
        ReduceOnPlateauConfig as ReduceOnPlateauConfig,
    )
    from mattertune.finetune.lr_scheduler import StepLRConfig as StepLRConfig
    from mattertune.finetune.main import PerSplitDataConfig as PerSplitDataConfig
    from mattertune.finetune.optimizer import AdamConfig as AdamConfig
    from mattertune.finetune.optimizer import AdamWConfig as AdamWConfig
    from mattertune.finetune.optimizer import SGDConfig as SGDConfig
    from mattertune.finetune.properties import (
        EnergyPropertyConfig as EnergyPropertyConfig,
    )
    from mattertune.finetune.properties import (
        ForcesPropertyConfig as ForcesPropertyConfig,
    )
    from mattertune.finetune.properties import (
        GraphPropertyConfig as GraphPropertyConfig,
    )
    from mattertune.finetune.properties import PropertyConfigBase as PropertyConfigBase
    from mattertune.finetune.properties import (
        StressesPropertyConfig as StressesPropertyConfig,
    )
else:

    def __getattr__(name):
        import importlib

        if name in globals():
            return globals()[name]
        if name == "AdamConfig":
            return importlib.import_module("mattertune.finetune.optimizer").AdamConfig
        if name == "AdamWConfig":
            return importlib.import_module("mattertune.finetune.optimizer").AdamWConfig
        if name == "CosineAnnealingLRConfig":
            return importlib.import_module(
                "mattertune.finetune.lr_scheduler"
            ).CosineAnnealingLRConfig
        if name == "EnergyPropertyConfig":
            return importlib.import_module(
                "mattertune.finetune.properties"
            ).EnergyPropertyConfig
        if name == "ExponentialConfig":
            return importlib.import_module(
                "mattertune.finetune.lr_scheduler"
            ).ExponentialConfig
        if name == "FinetuneModuleBaseConfig":
            return importlib.import_module(
                "mattertune.backbones.jmp"
            ).FinetuneModuleBaseConfig
        if name == "ForcesPropertyConfig":
            return importlib.import_module(
                "mattertune.finetune.properties"
            ).ForcesPropertyConfig
        if name == "GraphComputerConfig":
            return importlib.import_module(
                "mattertune.backbones.jmp"
            ).GraphComputerConfig
        if name == "GraphPropertyConfig":
            return importlib.import_module(
                "mattertune.finetune.properties"
            ).GraphPropertyConfig
        if name == "HuberLossConfig":
            return importlib.import_module("mattertune.finetune.loss").HuberLossConfig
        if name == "JMPBackboneConfig":
            return importlib.import_module("mattertune.backbones").JMPBackboneConfig
        if name == "L2MAELossConfig":
            return importlib.import_module("mattertune.finetune.loss").L2MAELossConfig
        if name == "MAELossConfig":
            return importlib.import_module("mattertune.finetune.loss").MAELossConfig
        if name == "MSELossConfig":
            return importlib.import_module("mattertune.finetune.loss").MSELossConfig
        if name == "MatterTunerConfig":
            return importlib.import_module("mattertune").MatterTunerConfig
        if name == "MultiStepLRConfig":
            return importlib.import_module(
                "mattertune.finetune.lr_scheduler"
            ).MultiStepLRConfig
        if name == "OMAT24DatasetConfig":
            return importlib.import_module("mattertune.data").OMAT24DatasetConfig
        if name == "PerSplitDataConfig":
            return importlib.import_module(
                "mattertune.finetune.main"
            ).PerSplitDataConfig
        if name == "PropertyConfigBase":
            return importlib.import_module(
                "mattertune.finetune.properties"
            ).PropertyConfigBase
        if name == "ReduceOnPlateauConfig":
            return importlib.import_module(
                "mattertune.finetune.lr_scheduler"
            ).ReduceOnPlateauConfig
        if name == "SGDConfig":
            return importlib.import_module("mattertune.finetune.optimizer").SGDConfig
        if name == "StepLRConfig":
            return importlib.import_module(
                "mattertune.finetune.lr_scheduler"
            ).StepLRConfig
        if name == "StressesPropertyConfig":
            return importlib.import_module(
                "mattertune.finetune.properties"
            ).StressesPropertyConfig
        if name == "BackboneConfig":
            return importlib.import_module("mattertune.backbones").BackboneConfig
        if name == "DatasetConfig":
            return importlib.import_module("mattertune.data").DatasetConfig
        if name == "LRSchedulerConfig":
            return importlib.import_module("mattertune.finetune.base").LRSchedulerConfig
        if name == "LossConfig":
            return importlib.import_module("mattertune.finetune.loss").LossConfig
        if name == "OptimizerConfig":
            return importlib.import_module("mattertune.finetune.base").OptimizerConfig
        if name == "PropertyConfig":
            return importlib.import_module("mattertune.finetune.base").PropertyConfig
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Submodule exports
from . import backbones as backbones
from . import data as data
from . import finetune as finetune
from . import wrappers as wrappers
