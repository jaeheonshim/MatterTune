from __future__ import annotations

import logging
import os
from pathlib import Path

import nshconfig_extra as CE
import nshutils as nu
import pytorch_lightning as pl
import rich
import wandb

import mattertune
import mattertune.backbones
import mattertune.configs as MC
from mattertune import MatterTuner
from mattertune.configs import WandbLoggerConfig

logging.basicConfig(level=logging.WARNING)
nu.pretty()


def main(args_dict: dict):
    def hparams():
        hparams = MC.MatterTunerConfig.draft()

        ## Model Hyperparameters
        hparams.model = MC.EqV2BackboneConfig.draft()
        hparams.model.checkpoint_path = CE.CachedPath(
            uri="hf://fairchem/OMAT24/eqV2_31M_mp.pt"
        )
        hparams.model.atoms_to_graph = MC.FAIRChemAtomsToGraphSystemConfig.draft()
        hparams.model.atoms_to_graph.radius = 8.0
        hparams.model.atoms_to_graph.max_num_neighbors = 20
        hparams.model.ignore_gpu_batch_transform_error = True
        hparams.model.optimizer = MC.AdamWConfig(lr=args_dict["lr"])
        hparams.model.properties = []
        property = MC.GraphPropertyConfig(
            loss=MC.MAELossConfig(),
            loss_coefficient=1.0,
            reduction="mean",
            name=args_dict["property"],
            dtype="float",
        )
        hparams.model.properties.append(property)

        ## Data Hyperparameters
        hparams.data = MC.AutoSplitDataModuleConfig.draft()
        hparams.data.dataset = MC.XYZDatasetConfig.draft()
        hparams.data.dataset.src = Path(args_dict["xyz_path"])
        hparams.data.train_split = args_dict["train_split"]
        hparams.data.batch_size = args_dict["batch_size"]

        ## Trainer Hyperparameters
        hparams.trainer = MC.TrainerConfig.draft()
        hparams.trainer.max_epochs = args_dict["max_epochs"]
        hparams.trainer.accelerator = "gpu"
        hparams.trainer.devices = args_dict["devices"]
        hparams.trainer.strategy = "ddp"
        hparams.trainer.gradient_clip_algorithm = "value"
        hparams.trainer.gradient_clip_val = 1.0
        hparams.trainer.precision = "bf16"

        # Configure Early Stopping
        hparams.trainer.early_stopping = MC.EarlyStoppingConfig(
            monitor="val/forces_mae", patience=200, mode="min"
        )

        # Configure Model Checkpoint
        hparams.trainer.checkpoint = MC.ModelCheckpointConfig(
            monitor="val/forces_mae",
            dirpath="./checkpoints",
            filename="jmp-best",
            save_top_k=1,
            mode="min",
        )

        # Configure Logger
        hparams.trainer.loggers = [
            WandbLoggerConfig(
                project="MatterTune-Examples", name="JMP-Water", offline=False
            )
        ]

        # Additional trainer settings
        hparams.lightning_trainer_kwargs = {
            "inference_mode": False,
        }

        hparams = hparams.finalize(strict=False)
        return hparams

    mt_config = hparams()
    model, trainer = MatterTuner(mt_config).tune()
    trainer.save_checkpoint("finetuned.ckpt")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="orb-v2")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=8.0e-5)
    parser.add_argument("--max_epochs", type=int, default=2000)
    parser.add_argument("--devices", type=int, nargs="+", default=[0, 1, 2, 3])
    args = parser.parse_args()
    args_dict = vars(args)
    main(args_dict)
