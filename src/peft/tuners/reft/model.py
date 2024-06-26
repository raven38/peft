# Copyright 2023-present the HuggingFace Inc. team.
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
import re
from typing import Union

import torch
from torch import nn

from peft.tuners.lycoris_utils import LycorisConfig, LycorisTuner
from peft.utils import (
    TRANSFORMERS_MODELS_TO_LOREFT_TARGET_MODULES_MAPPING,
)

from .layer import Linear, LoReftLayer


class LoReftModel(LycorisTuner):
    """
    LoReFT model from a pretrained model.

    Args:
        model (`torch.nn.Module`): The model to which the adapter tuner layers will be attached.
        config ([`LoReftConfig`]): The configuration of the LoReft model.
        adapter_name (`str`): The name of the adapter, defaults to `"default"`.

    Returns:
        `torch.nn.Module`: The LoReft model.

    Example:
        ```py
        >>> from diffusers import StableDiffusionPipeline
        >>> from peft import LoReftModel, LoReftConfig

        >>> config_te = LoReftConfig(
        ...     r=8,
        ...     target_modules=["k_proj", "q_proj", "v_proj", "out_proj", "fc1", "fc2"],
        ...     dropout=0.0,
        ... )
        >>> config_unet = LoReftConfig(
        ...     r=8,
        ...     target_modules=[
        ...         "proj_in",
        ...         "proj_out",
        ...         "to_k",
        ...         "to_q",
        ...         "to_v",
        ...         "to_out.0",
        ...         "ff.net.0.proj",
        ...         "ff.net.2",
        ...     ],
        ...     dropout=0.0,
        ... )

        >>> model = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5")
        >>> model.text_encoder = LoReftModel(model.text_encoder, config_te, "default")
        >>> model.unet = LoReftModel(model.unet, config_unet, "default")
        ```

    **Attributes**:
        - **model** ([`~torch.nn.Module`]) -- The model to be adapted.
        - **peft_config** ([`LoReftConfig`]): The configuration of the LoReFT model.
    """


    prefix: str = "reft_"
    layers_mapping: dict[type[torch.nn.Module], type[LoReftLayer]] = {
        torch.nn.Linear: Linear,
    }

    def _create_and_replace(
        self,
        config: LycorisConfig,
        adapter_name: str,
        target: Union[LoReftLayer, nn.Module],
        target_name: str,
        parent: nn.Module,
        current_key: str,
    ) -> None:
        """
        A private method to create and replace the target module with the adapter module.
        """

        # Regexp matching - Find key which matches current target_name in patterns provided
        pattern_keys = list(config.rank_pattern.keys())
        target_name_key = next(filter(lambda key: re.match(rf"(.*\.)?{key}$", current_key), pattern_keys), target_name)

        kwargs = config.to_dict()
        kwargs["r"] = config.rank_pattern.get(target_name_key, config.r)

        if isinstance(target, LoReftLayer):
            target.update_layer(adapter_name, **kwargs)
        else:
            new_module = self._create_new_module(config, adapter_name, target, **kwargs)
            self._replace_module(parent, target_name, new_module, target)

    @staticmethod
    def _prepare_adapter_config(peft_config, model_config):
        if peft_config.target_modules is None:
            if model_config["model_type"] not in TRANSFORMERS_MODELS_TO_LOREFT_TARGET_MODULES_MAPPING:
                raise ValueError("Please specify `target_modules` in `peft_config`")
            peft_config.target_modules = set(
                TRANSFORMERS_MODELS_TO_LOREFT_TARGET_MODULES_MAPPING[model_config["model_type"]]
            )
        return peft_config
