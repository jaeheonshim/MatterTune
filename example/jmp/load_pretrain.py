from collections.abc import Callable
from pathlib import Path
from typing import Literal
import os
import nshtrainer as nt
import nshutils as nu
from jmppeft.configs.finetune.jmp_l import jmp_l_ft_config_
from jmppeft.configs.finetune.jmp_s import jmp_s_ft_config_
from jmppeft.modules import loss
from jmppeft.tasks.config import AdamWConfig
from jmppeft.tasks.finetune import base, output_head
from jmppeft.datasets.mptrj_hf import MPTrjDatasetFromXYZConfig
from jmppeft.datasets import mptrj_hf
from jmppeft.tasks.finetune import matbench_discovery as M
from jmppeft.utils.param_specific_util import (
    make_parameter_specific_optimizer_config,
    parameter_specific_optimizer_config,
)


def load_pretrain(model_type: str, ckpt_path: str):
    ## BackBone Model Config
    def jmp_(config: base.FinetuneConfigBase):
        if model_type == "jmp_l":
            path = Path(ckpt_path)
            jmp_l_ft_config_(config)
            config.ckpt_load.checkpoint = base.PretrainedCheckpointConfig(
                path=path, ema=True
            )
            config.meta["jmp_kind"] = "l"
        elif model_type == "jmp_s":
            path = Path(ckpt_path)
            jmp_s_ft_config_(config)
            config.ckpt_load.checkpoint = base.PretrainedCheckpointConfig(
                path=path, ema=True
            )
            config.meta["jmp_kind"] = "s"
        else:
            raise ValueError("Invalid Model Name, Please choose between jmp_l and jmp_s")
    
    ## Predict Forces Directly
    def direct_(config: base.FinetuneConfigBase):
        config.backbone.regress_forces = True
        config.backbone.direct_forces = True
        config.backbone.regress_energy = True
    
    ## Predict Forces with Gradient Method
    def grad_(config: base.FinetuneConfigBase):
        config.backbone.regress_forces = True
        config.backbone.direct_forces = True
        config.backbone.regress_energy = True

        config.trainer.inference_mode = False
        
    ## Data Config
    def data_config_(
        config: M.MatbenchDiscoveryConfig,
        *,
        batch_size: int,
        reference: mptrj_hf.ReferenceConfig | None,
    ):
        config.batch_size = batch_size
        config.name_parts.append(f"bsz{batch_size}")

        def dataset_fn(split: Literal["train", "val", "test"]):
            dataset_config = MPTrjDatasetFromXYZConfig(
                file_path="/nethome/lkong88/workspace/jmp-peft/checkpoints/MgSi-mptrj.xyz",
                split=split,
                split_ratio=[0.8, 0.1, 0.1],
            )
            if reference:
                dataset_config.references["y"] = reference
            return dataset_config

        config.train_dataset = dataset_fn("train")
        config.val_dataset = dataset_fn("val")
        config.test_dataset = dataset_fn("test")

        # Set data config
        config.num_workers = 7

        # Balanced batch sampler
        config.use_balanced_batch_sampler = True
        config.trainer.use_distributed_sampler = False
    
    ## Output Head Config
    def output_heads_config_direct_(
        config: M.MatbenchDiscoveryConfig,
        *,
        mace_energy_loss: bool,
        mace_force_loss: bool,
        energy_coefficient: float,
        force_coefficient: float,
        stress_coefficient: float,
    ):
        energy_loss = loss.HuberLossConfig(delta=0.01)
        if mace_energy_loss:
            energy_loss = loss.MACEHuberEnergyLossConfig(delta=0.01)
            config.tags.append("maceenergy")

        force_loss = loss.HuberLossConfig(delta=0.01)
        if mace_force_loss:
            force_loss = loss.MACEHuberLossConfig(delta=0.01)
            config.tags.append("maceforce")

        # Energy head
        config.graph_targets.append(
            output_head.AllegroScalarTargetConfig(
                name="y",
                loss_coefficient=energy_coefficient,
                loss=energy_loss,
                reduction="sum",
                max_atomic_number=config.backbone.num_elements,
                edge_level_energies=True,
            )
        )
        # Stress head
        config.graph_targets.append(
            output_head.DirectStressTargetConfig(
                name="stress",
                loss_coefficient=stress_coefficient,
                loss=loss.HuberLossConfig(
                    y_mult_coeff=1602.1766208,  # eV/A^3 to kbar
                    delta=0.01,
                ),
                reduction="mean",
            )
        )
        # Force head
        config.node_targets.append(
            output_head.NodeVectorTargetConfig(
                name="force",
                loss_coefficient=force_coefficient,
                loss=force_loss,
                reduction="sum",
            )
        )

        config.tags.append(f"ec{energy_coefficient}")
        config.tags.append(f"fc{force_coefficient}")
        config.tags.append(f"sc{stress_coefficient}")
    
    def output_heads_config_grad_(
        config: M.MatbenchDiscoveryConfig,
        *,
        relaxed_energy: bool,
        mace_energy_loss: bool,
        mace_force_loss: bool,
        energy_coefficient: float,
        force_coefficient: float,
        stress_coefficient: float,
    ):
        energy_loss = loss.HuberLossConfig(delta=0.01)
        if mace_energy_loss:
            energy_loss = loss.MACEHuberEnergyLossConfig(delta=0.01)
            config.name_parts.append("maceenergy")

        force_loss = loss.HuberLossConfig(delta=0.01)
        if mace_force_loss:
            force_loss = loss.MACEHuberLossConfig(delta=0.01)
            config.name_parts.append("maceforce")

        # Energy head
        config.graph_targets.append(
            output_head.ReferencedScalarTargetConfig(
                name="y",
                loss_coefficient=energy_coefficient,
                loss=energy_loss.model_copy(),
                reduction="sum",
                max_atomic_number=config.backbone.num_elements,
                initialization=output_head.ZerosReferenceInitializationConfig(),
            )
        )
        # Force head
        config.node_targets.append(
            output_head.GradientForcesTargetConfig(
                name="force",
                energy_name="y",
                loss_coefficient=force_coefficient,
                loss=force_loss,
                reduction="sum",
            )
        )

        config.name_parts.append(f"ec{energy_coefficient}")
        config.name_parts.append(f"fc{force_coefficient}")
        config.name_parts.append(f"sc{stress_coefficient}")
        return config
    
    ## Optimizer Config
    def optimization_config_(
        config: M.MatbenchDiscoveryConfig,
        *,
        lr: float,
        wd: float,
    ):
        config.optimizer = AdamWConfig(
            lr=lr,
            amsgrad=False,
            betas=(0.9, 0.95),
            weight_decay=wd,
        )
        config.lr_scheduler = base.WarmupCosRLPConfig(
            warmup_epochs=1,
            warmup_start_lr_factor=1.0e-1,
            should_restart=False,
            max_epochs=128,
            min_lr_factor=0.5,
            rlp=base.RLPConfig(patience=5, factor=0.8),
        )
        config.trainer.optimizer.gradient_clipping = nt.model.GradientClippingConfig(
            value=2.0,
            algorithm="value",
        )

        config.name_parts.append(f"lr{lr}")
        config.name_parts.append(f"wd{wd}")

    ## Freeze the backbone
    def parameter_specific_optimizers_(config: base.FinetuneConfigBase):
        if config.parameter_specific_optimizers is None:
            config.parameter_specific_optimizers = []

        match config.meta["jmp_kind"]:
            case "l":
                config.parameter_specific_optimizers.extend(
                    make_parameter_specific_optimizer_config(
                        config,
                        config.backbone.num_blocks,
                        {
                            "embedding": 0.3,
                            "blocks_0": 0.55,
                            "blocks_1": 0.40,
                            "blocks_2": 0.30,
                            "blocks_3": 0.40,
                            "blocks_4": 0.55,
                            "blocks_5": 0.625,
                        },
                    )
                )
            case "s":
                config.parameter_specific_optimizers.extend(
                    make_parameter_specific_optimizer_config(
                        config,
                        config.backbone.num_blocks,
                        {
                            "embedding": 0.3,
                            "blocks_0": 0.30,
                            "blocks_1": 0.40,
                            "blocks_2": 0.55,
                            "blocks_3": 0.625,
                        },
                    )
                )
            case _:
                raise ValueError(f"Invalid jmp_kind: {config.meta['jmp_kind']}")
    
    ## Energy Reference Optimization Config
    def parameter_specific_optimizers_energy_references_(
        config: base.FinetuneConfigBase,
        lr_multiplier: float = 0.1,
        wd: float | None = None,
    ):
        if not config.parameter_specific_optimizers:
            config.parameter_specific_optimizers = []

        if wd is None:
            wd = config.optimizer.weight_decay

        if energy_ref_heads := [
            t
            for t in config.graph_targets
            if isinstance(t, output_head.ReferencedScalarTargetConfig)
        ]:
            config.parameter_specific_optimizers.extend(
                parameter_specific_optimizer_config(
                    config,
                    [
                        {
                            "name": f"{energy_ref_head.name}.ref",
                            "lr_multiplier": lr_multiplier,
                            "weight_decay": wd,
                            "parameter_patterns": [
                                f"graph_outputs._module_dict.ft_mlp_{energy_ref_head.name}.references.*"
                            ],
                        }
                        for energy_ref_head in energy_ref_heads
                    ],
                )
            )

        elif allegro_heads := [
            t
            for t in config.graph_targets
            if isinstance(t, output_head.AllegroScalarTargetConfig)
        ]:
            config.parameter_specific_optimizers.extend(
                parameter_specific_optimizer_config(
                    config,
                    [
                        {
                            "name": f"{h.name}.scales",
                            "lr_multiplier": lr_multiplier,
                            "parameter_patterns": [
                                f"graph_outputs._module_dict.ft_mlp_{h.name}.per_atom_scales.*",
                                f"graph_outputs._module_dict.ft_mlp_{h.name}.per_atom_shifts.*",
                                *(
                                    [
                                        f"graph_outputs._module_dict.ft_mlp_{h.name}.pairwise_scales.*"
                                    ]
                                    if h.edge_level_energies
                                    else []
                                ),
                            ],
                        }
                        for h in allegro_heads
                    ],
                )
            )
        else:
            raise ValueError("No energy reference or allegro heads found")
        
    ## Layer Norm
    def ln_(
        config: base.FinetuneConfigBase,
        *,
        lr_multiplier: float | None,
    ):
        config.backbone.ln_per_layer = True
        config.backbone.scale_factor_to_ln = True

        if lr_multiplier is not None:
            if config.parameter_specific_optimizers is None:
                config.parameter_specific_optimizers = []

            config.parameter_specific_optimizers = [
                *parameter_specific_optimizer_config(
                    config,
                    [
                        {
                            "name": "ln",
                            "lr_multiplier": lr_multiplier,
                            "parameter_patterns": [
                                "backbone.h_lns.*",
                                "backbone.m_lns.*",
                                "backbone.*.scale*.ln.*",
                            ],
                        }
                    ],
                ),
                *config.parameter_specific_optimizers,
            ]

        config.name_parts.append("ln")

    ## Random Position Augmentation Config, Add Noise to Avoid Overfitting
    def pos_aug_(config: base.FinetuneConfigBase, *, std: float):
        config.pos_noise_augmentation = base.PositionNoiseAugmentationConfig(
            system_corrupt_prob=0.75,
            atom_corrupt_prob=0.5,
            noise_std=std,
        )
        config.name_parts.append(f"posaug_std{std}")

    def create_config(config_fn: Callable[[M.MatbenchDiscoveryConfig], None]):
        config = M.MatbenchDiscoveryConfig.draft()
        config.trainer.precision = "16-mixed-auto"
        config.trainer.set_float32_matmul_precision = "medium"
        config.project = "jmp_mptrj"
        config.name = "mptrj"
        config_fn(config)
        config.backbone.qint_tags = [0, 1, 2]
        config.primary_metric = nt.MetricConfig(
            name="matbench_discovery/force_mae", mode="min"
        )
        return config
    
    configs: list[tuple[M.MatbenchDiscoveryConfig, type[M.MatbenchDiscoveryModel]]] = []

    config = create_config(jmp_)
    config.parameter_specific_optimizers = []
    config.max_neighbors = M.MaxNeighbors(main=25, aeaint=20, aint=1000, qint=8)
    config.cutoffs = M.Cutoffs.from_constant(12.0)
    data_config_(config, batch_size=32, reference=None)
    optimization_config_(config, lr=1e-3, wd=0)
    grad_(config=config)
    output_heads_config_grad_(
        config,
        relaxed_energy=False,
        mace_energy_loss=True,
        mace_force_loss=True,
        energy_coefficient=1.0,
        force_coefficient=1.0,
        stress_coefficient=1.0,
    )
    parameter_specific_optimizers_energy_references_(config, lr_multiplier=0.1, wd=0.2)
    # pos_aug_(config, std=0.01)
    config.per_graph_radius_graph = True
    config.ignore_graph_generation_errors = True
    config.trainer.early_stopping = nt.model.EarlyStoppingConfig(
            patience=50, min_lr=1e-08
        )
    config.trainer.max_epochs = 200
    config = config.finalize()
    configs.append((config, M.MatbenchDiscoveryModel))
    
    model = M.MatbenchDiscoveryModel.construct_and_load_checkpoint(config)
    embedding = model.embedding
    backbone = model.backbone
    
    os.system("rm -r ./nshtrainer")
    return backbone, embedding