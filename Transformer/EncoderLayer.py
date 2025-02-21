"""
@Author:    Pshy Simon
@Date:  2020/10/1 0001 下午 08:44
@Description:
   编码器层
"""

import torch
import torch.nn as nn
from .MultiHeadAttention import MultiHeadAttention
from .PositionwiseFeedforward import PositionwiseFeedforward

class EncoderLayer(nn.Module):

    def __init__(self, config):
        super().__init__()
        self.attn = MultiHeadAttention(config)
        self.pf = PositionwiseFeedforward(config)
        self.attn_ln = nn.LayerNorm(config.size)
        self.pf_ln = nn.LayerNorm(config.size)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x, mask = None):
        norm_x = self.attn_ln(x)
        x = x + self.attn(norm_x, mask)
        norm_x = self.pf_ln(x)
        return x + self.pf(norm_x)

