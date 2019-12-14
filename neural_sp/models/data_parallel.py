#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2018 Kyoto University (Hirofumi Inaguma)
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

"""Custom class for data parallel training."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from torch.nn import DataParallel
from torch.nn.parallel.scatter_gather import gather


class CustomDataParallel(DataParallel):

    def __init__(self, module, device_ids=None, output_device=None, dim=0):
        super(CustomDataParallel, self).__init__(module, device_ids, output_device, dim)

    def gather(self, outputs, output_device):
        n_returns = len(outputs[0])
        n_gpus = len(outputs)
        if n_returns == 2:
            losses = [output[0] for output in outputs]
            observation_mean = {}
            for output in outputs:
                for k, v in output[1].items():
                    if v is None:
                        continue
                    if k not in observation_mean.keys():
                        observation_mean[k] = v
                    else:
                        observation_mean[k] += v
                observation_mean = {k: v / n_gpus for k, v in observation_mean.items()}
            return gather(losses, output_device, dim=self.dim).mean(), observation_mean
        else:
            raise ValueError(n_returns)
