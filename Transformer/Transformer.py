"""
@Author:    Pshy Simon
@Date:  2020/10/1 0001 下午 03:20
@Description:
    Attention is all you need!
        在过去，很多自然语言处理中的任务都是使用的循环神经网络RNN来作为特征抽取器，将一段文本的信息编码到
        矩阵中，即Contextualized Vector，但是RNN有着一定的问题：
            (1).首先RNN的长程依赖问题仍没有得到很好的解决，LSTM仅仅只是减缓了长程依赖问题
            (2).RNN网络并不能并行计算，导致训练和推断耗时过长
        而Transformer则避免了这些问题
    Transformer的组件：
        1.词嵌入层：
            生成词嵌入层之后，将词嵌入层乘上sqrt(d_model)，然后将嵌入层映射成d_model维的向量
        2.位置编码层：
            由于这个网络没有循环网络和卷积网络，没有捕捉到位置相关的信息，所以要加入位置编码
        3.自注意力层：
            使用自注意力取代RNN
        4.前馈网络
            逐位置的变换
"""

import torch
import torch.nn as nn
import copy
import math
import torch.nn.functional as F

class Encoder(nn.Module):

    def __init__(self, layer, N):
        super().__init__()
        self.layers = nn.ModuleList([copy.deepcopy(layer) for _ in range(N)])
        self.norm = LayerNorm(layer.size)

    def forward(self, x, mask = None):
        for layer in self.layers:
            x = layer(x, mask)
        return self.norm(x)

class LayerNorm(nn.Module):

    def __init__(self, features, eps=1e-6):
        super().__init__()
        self.a_2 = nn.Parameter(torch.ones(features))
        self.b_2 = nn.Parameter(torch.zeros(features))
        self.eps = eps

    def forward(self, x):
        mean = x.mean(-1, keepdim=True)
        std = x.std(-1, keepdim=True)
        return self.a_2 * (x - mean) / (std + self.eps) + self.b_2


class EncoderLayer(nn.Module):

    def __init__(self, size, self_attn, feed_forward, dropout):
        super().__init__()
        self.self_attn = self_attn
        self.feed_forward = feed_forward
        self.size = size
        self.attn_ln = LayerNorm(size)
        self.ff_ln = LayerNorm(size)

    def forward(self, x, mask):
        norm_x = self.attn_ln(x)
        x = x + self.self_attn(norm_x, norm_x, norm_x, mask)
        norm_x = self.ff_ln(x)
        return x + self.feed_forward(norm_x)

        # x = self.sub_layer[0](x, lambda x:self.self_attn(x, x, x, mask))
        # return self.sub_layer[1](x, self.feed_forward)

def attention(query, key, value, mask=None, dropout=None):
    d_k = query.size(-1)
    scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(d_k)
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e9)
    p_attn = torch.softmax(scores, dim = -1)
    if dropout is not None:
        p_attn = dropout(p_attn)
    return torch.matmul(p_attn, value), p_attn


class MultiHeadAttention(nn.Module):
    def __init__(self, h, d_model, dropout=0.1):
        super().__init__()
        assert d_model % h == 0
        # We assume d_v always equals d_k
        self.d_k = d_model // h
        self.h = h
        self.linears = nn.ModuleList(copy.deepcopy(nn.Linear(d_model, d_model)) for _ in range(4))
        self.attn = None
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, query, key, value, mask=None):
        if mask is not None:
            # Same mask applied to all h heads.
            mask = mask.unsqueeze(1)
        nbatches = query.size(0)

        query, key, value = \
            [l(x).view(nbatches, -1, self.h, self.d_k).transpose(1, 2)
             for l, x in zip(self.linears, (query, key, value))]

        x, self.attn = attention(query, key, value, mask=mask,
                                 dropout=self.dropout)

        x = x.transpose(1, 2).contiguous() \
            .view(nbatches, -1, self.h * self.d_k)
        return self.linears[-1](x)

class PositionwiseFeedForward(nn.Module):
    def __init__(self, d_model, d_ff, dropout=0.1):
        super().__init__()
        self.w_1 = nn.Linear(d_model, d_ff)
        self.w_2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        return self.w_2(self.dropout(torch.relu(self.w_1(x))))

class Embeddings(nn.Module):
    def __init__(self, vocab, d_model):
        super(Embeddings, self).__init__()
        self.lut = nn.Embedding(vocab, d_model)
        self.d_model = d_model

    def forward(self, x):
        return self.lut(x) * math.sqrt(self.d_model)


class PositionalEncoding(nn.Module):

    def __init__(self, d_model, dropout, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        # Compute the positional encodings once in log space.
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) *
                             -(math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, X):
        X = X + self.pe[:, : X.size(1)].clone().detach().requires_grad_(False)
        return self.dropout(X)


class TransformerText(nn.Module):
    """ 用 Transformer 来作为特征抽取的基本单元 """

    def __init__(self,input_size, n_heads, n_layers, emd_dim, d_model, d_ff, output_dim, dropout):
        super(TransformerText, self).__init__()

        # # nn.Embedding()
        # self.word_embedding = Embeddings(d_model, 250000)
        # self.position_embedding = PositionalEncoding(d_model, dropout)

        # nn.Embedding.from_pretrain()
        self.word_embedding = Embeddings(input_size, emd_dim)
        self.position_embedding = PositionalEncoding(emd_dim, dropout)

        self.trans_linear = nn.Linear(emd_dim, d_model)

        multi_attn = MultiHeadAttention(n_heads, d_model)
        feed_forward = PositionwiseFeedForward(d_model, d_ff, dropout)

        self.encoder = Encoder(EncoderLayer(d_model, multi_attn, feed_forward, dropout), n_layers)
        self.fc = nn.Linear(d_model, output_dim)

    def forward(self, text):

        embeddings = self.word_embedding(text)
        # embeddings: [batch_size, sent_len, emd_dim]
        embeddings = self.position_embedding(embeddings)
        # embeddings: [batch_size, sent_len, dim]

        embeddings = self.trans_linear(embeddings)

        embeddings = self.encoder(embeddings)
        # embeddings: [batch_size, sent_len, d_model]

        features = embeddings[:, -1, :]
        # features: [batch_size, d_model]

        return self.fc(features)

