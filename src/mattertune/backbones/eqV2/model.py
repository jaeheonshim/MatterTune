from __future__ import annotations

import contextlib
import importlib.util
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import nshconfig as C
import nshconfig_extra as CE
import torch
import torch.nn as nn
from typing_extensions import assert_never, override

from ...finetune import properties as props
from ...finetune.base import FinetuneModuleBase, FinetuneModuleBaseConfig, ModelOutput
from ...registry import backbone_registry

if TYPE_CHECKING:
    from fairchem.core.models.equiformer_v2.prediction_heads.rank2 import (
        Rank2SymmetricTensorHead,
    )
    from torch_geometric.data import Batch
    from torch_geometric.data.data import BaseData

log = logging.getLogger(__name__)


class FAIRChemAtomsToGraphSystemConfig(C.Config):
    """Configuration for converting ASE Atoms to a graph for the FAIRChem model."""

    radius: float
    """The radius for edge construction."""
    max_num_neighbors: int
    """The maximum number of neighbours each node can send messages to."""


@backbone_registry.register
class EqV2BackboneConfig(FinetuneModuleBaseConfig):
    name: Literal["eqV2"] = "eqV2"
    """The type of the backbone."""

    checkpoint_path: Path | CE.CachedPath
    """The path to the checkpoint to load."""

    atoms_to_graph: FAIRChemAtomsToGraphSystemConfig
    """Configuration for converting ASE Atoms to a graph."""
    # TODO: Add functionality to load the atoms to graph config from the checkpoint

    @override
    @classmethod
    def model_cls(cls):
        return EqV2BackboneModule


def _combine_scalar_irrep2(stress_head: "Rank2SymmetricTensorHead", scalar, irrep2):
    # Change of basis to compute a rank 2 symmetric tensor

    vector = torch.zeros((scalar.shape[0], 3), device=scalar.device).detach()
    flatten_irreps = torch.cat([scalar.reshape(-1, 1), vector, irrep2], dim=1)
    stress = torch.einsum(
        "ab, cb->ca",
        stress_head.block.change_mat.to(flatten_irreps.device),
        flatten_irreps,
    )

    # stress = rearrange(
    #     stress,
    #     "b (three1 three2) -> b three1 three2",
    #     three1=3,
    #     three2=3,
    # ).contiguous()
    stress = stress.view(-1, 3, 3)

    return stress


def _get_backbone(hparams: EqV2BackboneConfig) -> nn.Module:
    from fairchem.core.common.registry import registry
    from fairchem.core.common.utils import update_config

    if isinstance(checkpoint_path := hparams.checkpoint_path, CE.CachedPath):
        checkpoint_path = checkpoint_path.resolve()

    checkpoint = None
    # Loads the config from the checkpoint directly (always on CPU).
    checkpoint = torch.load(checkpoint_path, map_location=torch.device("cpu"))
    config = checkpoint["config"]

    config["trainer"] = config.get("trainer", "ocp")

    if "model_attributes" in config:
        config["model_attributes"]["name"] = config.pop("model")
        config["model"] = config["model_attributes"]

    # Calculate the edge indices on the fly
    config["model"]["otf_graph"] = True

    ### backwards compatability with OCP v<2.0
    config = update_config(config)

    # Save config so obj can be transported over network (pkl)
    config["checkpoint"] = checkpoint_path
    del config["dataset"]["src"]

    # Import a bunch of modules so that the registry can find the classes
    import fairchem.core.models  # noqa: F401
    import fairchem.core.models.equiformer_v2
    import fairchem.core.models.equiformer_v2.equiformer_v2
    import fairchem.core.models.equiformer_v2.prediction_heads.rank2
    import fairchem.core.trainers

    trainer = registry.get_trainer_class(config["trainer"])(
        task=config.get("task", {}),
        model=config["model"],
        dataset=[config["dataset"]],
        outputs=config["outputs"],
        loss_functions=config["loss_functions"],
        evaluation_metrics=config["evaluation_metrics"],
        optimizer=config["optim"],
        identifier="",
        slurm=config.get("slurm", {}),
        local_rank=config.get("local_rank", 0),
        is_debug=config.get("is_debug", True),
        cpu=True,
        amp=config.get("amp", False),
        inference_only=True,
    )

    # Load the checkpoint
    if checkpoint_path is not None:
        try:
            trainer.load_checkpoint(checkpoint_path, checkpoint, inference_only=True)
        except NotImplementedError:
            log.warning(f"Unable to load checkpoint from {checkpoint_path}")

    # Now, extract the backbone from the trainer and delete the trainer
    from fairchem.core.trainers import OCPTrainer

    assert isinstance(trainer, OCPTrainer), "Only OCPTrainer is supported."
    assert (model := getattr(trainer, "_unwrapped_model", None)) is not None, (
        "The model could not be extracted from the trainer. "
        "Please report this issue."
    )

    # Make sure this is eqv2
    from fairchem.core.models.base import HydraModel

    assert isinstance(
        model, HydraModel
    ), f"Expected model to be of type HydraModel, but got {type(model)}"

    from fairchem.core.models.equiformer_v2.equiformer_v2 import EquiformerV2Backbone

    assert isinstance(
        backbone := model.backbone, EquiformerV2Backbone
    ), f"Expected backbone to be of type EquiformerV2Backbone, but got {type(backbone)}"

    return backbone


class EqV2BackboneModule(FinetuneModuleBase["BaseData", "Batch", EqV2BackboneConfig]):
    @override
    @classmethod
    def hparams_cls(cls):
        return EqV2BackboneConfig

    @override
    @classmethod
    def ensure_dependencies(cls):
        # Make sure the fairchem module is available
        if importlib.util.find_spec("fairchem") is None:
            raise ImportError(
                "The fairchem module is not installed. Please install it by running"
                " pip install fairchem-core."
            )

        # Make sure torch-geometric is available
        if importlib.util.find_spec("torch_geometric") is None:
            raise ImportError(
                "The torch-geometric module is not installed. Please install it by running"
                " pip install torch-geometric."
            )

    @override
    def requires_disabled_inference_mode(self):
        return False

    def _create_output_head(self, prop: props.PropertyConfig):
        match prop:
            case props.EnergyPropertyConfig():
                from fairchem.core.models.equiformer_v2.equiformer_v2 import (
                    EquiformerV2EnergyHead,
                )

                return EquiformerV2EnergyHead(self.backbone, reduce="sum")
            case props.ForcesPropertyConfig():
                assert (
                    not prop.conservative
                ), "Conservative forces are not supported for eqV2 (yet)"

                from fairchem.core.models.equiformer_v2.equiformer_v2 import (
                    EquiformerV2ForceHead,
                )

                return EquiformerV2ForceHead(self.backbone)
            case props.StressesPropertyConfig():
                assert (
                    not prop.conservative
                ), "Conservative stresses are not supported for eqV2 (yet)"

                from fairchem.core.models.equiformer_v2.prediction_heads.rank2 import (
                    Rank2SymmetricTensorHead,
                )

                return Rank2SymmetricTensorHead(
                    self.backbone,
                    output_name="stress",
                    use_source_target_embedding=True,
                    decompose=True,
                    extensive=False,
                )
            case props.GraphPropertyConfig():
                assert prop.reduction in ("sum", "mean"), (
                    f"Unsupported reduction: {prop.reduction} for eqV2. "
                    "Please use 'sum' or 'mean'."
                )
                from fairchem.core.models.equiformer_v2.equiformer_v2 import (
                    EquiformerV2EnergyHead,
                )

                return EquiformerV2EnergyHead(self.backbone, reduce=prop.reduction)
            case _:
                raise ValueError(
                    f"Unsupported property config: {prop} for eqV2"
                    "Please ask the maintainers of eqV2 for support"
                )

    @override
    def create_model(self):
        # Get the pre-trained backbone
        self.backbone = _get_backbone(self.hparams)

        # Create the output heads
        self.output_heads = nn.ModuleDict()
        for prop in self.hparams.properties:
            self.output_heads[prop.name] = self._create_output_head(prop)

    @override
    @contextlib.contextmanager
    def model_forward_context(self, data):
        yield

    @override
    def model_forward(self, batch, return_backbone_output=False):
        # Run the backbone
        emb = self.backbone(batch)

        # Feed the backbone output to the output heads
        predicted_properties: dict[str, torch.Tensor] = {}
        for name, head in self.output_heads.items():
            assert (
                prop := next(
                    (p for p in self.hparams.properties if p.name == name), None
                )
            ) is not None, (
                f"Property {name} not found in properties. "
                "This should not happen, please report this."
            )

            head_output: dict[str, torch.Tensor] = head(batch, emb)

            match prop:
                case props.EnergyPropertyConfig():
                    pred = head_output["energy"]
                case props.ForcesPropertyConfig():
                    pred = head_output["forces"]
                case props.StressesPropertyConfig():
                    # Convert the stress tensor to the full 3x3 form
                    stress_rank0 = head_output["stress_isotropic"]  # (bsz 1)
                    stress_rank2 = head_output["stress_anisotropic"]  # (bsz, 5)
                    pred = _combine_scalar_irrep2(head, stress_rank0, stress_rank2)
                case props.GraphPropertyConfig():
                    pred = head_output["energy"]
                case _:
                    assert_never(prop)

            predicted_properties[name] = pred

        pred_dict: ModelOutput = {"predicted_properties": predicted_properties}
        if return_backbone_output:
            pred_dict["backbone_output"] = emb

        return pred_dict

    @override
    def pretrained_backbone_parameters(self):
        return self.backbone.parameters()

    @override
    def output_head_parameters(self):
        for head in self.output_heads.values():
            yield from head.parameters()

    @override
    def cpu_data_transform(self, data):
        return data

    @override
    def collate_fn(self, data_list):
        from fairchem.core.datasets import data_list_collater

        return cast("Batch", data_list_collater(data_list, otf_graph=True))

    @override
    def gpu_batch_transform(self, batch):
        return batch

    @override
    def batch_to_labels(self, batch):
        HARDCODED_NAMES: dict[type[props.PropertyConfigBase], str] = {
            props.EnergyPropertyConfig: "energy",
            props.ForcesPropertyConfig: "forces",
            props.StressesPropertyConfig: "stress",
        }

        labels: dict[str, torch.Tensor] = {}
        for prop in self.hparams.properties:
            batch_prop_name = HARDCODED_NAMES.get(type(prop), prop.name)
            labels[prop.name] = batch[batch_prop_name]

        return labels

    @override
    def atoms_to_data(self, atoms, has_labels):
        from fairchem.core.preprocessing import AtomsToGraphs

        energy = False
        forces = False
        stress = False
        data_keys = None
        if has_labels:
            energy = any(
                isinstance(prop, props.EnergyPropertyConfig)
                for prop in self.hparams.properties
            )
            forces = any(
                isinstance(prop, props.ForcesPropertyConfig)
                for prop in self.hparams.properties
            )
            stress = any(
                isinstance(prop, props.StressesPropertyConfig)
                for prop in self.hparams.properties
            )
            data_keys = [
                prop.name
                for prop in self.hparams.properties
                if not isinstance(
                    prop,
                    (
                        props.EnergyPropertyConfig,
                        props.ForcesPropertyConfig,
                        props.StressesPropertyConfig,
                    ),
                )
            ]

        a2g = AtomsToGraphs(
            max_neigh=self.hparams.atoms_to_graph.max_num_neighbors,
            radius=self.hparams.atoms_to_graph.radius,
            r_energy=energy,
            r_forces=forces,
            r_stress=stress,
            r_data_keys=data_keys,
            r_distances=False,
            r_edges=False,
            r_pbc=True,
        )
        data = a2g.convert(atoms)

        # Reshape the cell and stress tensors to (1, 3, 3)
        #   so that they can be properly batched by the collate_fn.
        if hasattr(data, "cell"):
            data.cell = data.cell.reshape(1, 3, 3)
        if hasattr(data, "stress"):
            data.stress = data.stress.reshape(1, 3, 3)

        return data