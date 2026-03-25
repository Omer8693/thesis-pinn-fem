"""
fourier_pinn.py — Fourier Feature PINN Ağı
============================================
Motivasyon:
  Standart PINN'ler spektral önyargıdan (spectral bias) muzdariptir:
  düşük frekanslı bileşenleri iyi öğrenir ama yüksek frekanslı
  bileşenleri yavaş öğrenir. A356 quenching'de t=0-5s arasındaki
  hızlı soğuma yüksek frekanslı bir sinyal — standart ağ bunu geç öğrenir.

Çözüm (Tancik et al., 2020 — "Fourier Features Let Networks Learn High
Frequency Functions in Low Dimensional Domains"):
  Girişi (t, x, y) ham vermek yerine önce Fourier gömme uygula:
    γ(v) = [sin(2π·B·v), cos(2π·B·v)]    B ∈ R^{3×F}
  B'nin elemanları N(0, σ²) dağılımından çekilir.
  σ büyüdükçe yüksek frekans bileşenleri daha iyi öğrenilir.

Kullanım:
    arch = {"n_layers": 5, "neurons": [151]*5, "activation": "relu"}
    net  = FourierPINN(arch, sigma=10.0, n_fourier=64)
"""

import math
import torch
import torch.nn as nn
from typing import Dict, List

from src.config import DEVICE


# ─────────────────────────────────────────────────────────────
# Yardımcı: aktivasyon fonksiyonu seçimi
# ─────────────────────────────────────────────────────────────

def _get_activation(name: str) -> nn.Module:
    return {
        "tanh":  nn.Tanh(),
        "relu":  nn.ReLU(),
        "swish": nn.SiLU(),
        "gelu":  nn.GELU(),
        "elu":   nn.ELU(),
    }.get(name, nn.Tanh())


# ─────────────────────────────────────────────────────────────
# Fourier Gömme Katmanı
# ─────────────────────────────────────────────────────────────

class FourierEmbedding(nn.Module):
    """
    Sabit (eğitilmez) rastgele Fourier özellik gömme.

    Giriş : [N, d_in]   (örn. d_in=3 için t, x, y)
    Çıkış : [N, 2*F]    sin ve cos çiftleri

    B : [d_in, F] — N(0, σ²) dağılımından çekilir, sabit tutulur.

    Quenching için σ önerisi:
      - t ∈ [0, 30s]  → frekans ~1/3   → σ ≈ 5–10
      - x ∈ [0, 1.3m] → frekans ~1     → σ ≈ 5–10
      σ=10 her iki ölçek için makul bir başlangıç noktasıdır.
    """

    def __init__(self, d_in: int = 3, n_fourier: int = 64, sigma: float = 10.0):
        super().__init__()
        B = torch.randn(d_in, n_fourier) * sigma   # CPU'da oluştur, .to() ile taşınır
        self.register_buffer("B", B)   # eğitilmez ama state_dict'e kaydedilir
        self.out_dim = 2 * n_fourier

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [N, d_in]  →  [N, 2*F]"""
        proj = 2 * math.pi * x @ self.B          # [N, F]
        return torch.cat([torch.sin(proj), torch.cos(proj)], dim=-1)


# ─────────────────────────────────────────────────────────────
# Fourier Feature PINN
# ─────────────────────────────────────────────────────────────

class FourierPINN(nn.Module):
    """
    NAS tarafından bulunan mimariye Fourier gömme eklenmiş PINN.

    Mimari:
      (t,x,y) → normalize [0,1] → FourierEmbedding → MLP → T

    Koordinatlar ağ içinde [0,1]'e normalize edilir (scales parametresi).
    Bu sayede gerçek koordinatlarla çalışan fizik kaybı ile
    stabil Fourier gömme birlikte çalışır.

    Parametreler:
      arch      : NAS'tan gelen sözlük (n_layers, neurons, activation)
      sigma     : Fourier gömme bant genişliği [0,1] uzayında
      n_fourier : Fourier özellik sayısı (çıkış 2*n_fourier olur)
      scales    : her koordinat için normalizasyon ölçeği (örn. [30, 1.3, 0.6])
    """

    def __init__(self,
                 arch:      Dict,
                 sigma:     float = 1.0,
                 n_fourier: int   = 64,
                 scales:    List[float] = None):
        super().__init__()

        d_in = arch.get("n_input", 3)

        # Normalizasyon ölçekleri: her koordinatı [0,1]'e indirger
        if scales is None:
            scales = [1.0] * d_in
        scale_t = torch.tensor(scales, dtype=torch.float32).unsqueeze(0)  # [1, d_in]
        self.register_buffer("scale", scale_t)

        # n_fourier=0 → Fourier gömme yok, doğrudan normalize koordinatlar kullanılır
        if n_fourier > 0:
            self.embedding = FourierEmbedding(d_in=d_in, n_fourier=n_fourier, sigma=sigma)
            in_dim = self.embedding.out_dim
        else:
            self.embedding = None
            in_dim = d_in
        neurons: List[int] = arch["neurons"]
        act_name: str      = arch.get("activation", "tanh")

        layers = []
        prev   = in_dim
        for h in neurons:
            layers.append(nn.Linear(prev, h))
            layers.append(_get_activation(act_name))
            prev = h
        layers.append(nn.Linear(prev, arch.get("n_output", 1)))

        self.net = nn.Sequential(*layers)
        self._init_weights()

    def _init_weights(self):
        """Xavier uniform başlatma — tanh/relu için standart."""
        for m in self.net.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """
        coords : [N, d_in]  gerçek koordinatlar (t, x, y[, z])
        return : [N, 1]     sıcaklık tahmini T (°C)
        """
        x_norm = coords / self.scale.to(coords.device)   # [0,1] normalize
        if self.embedding is not None:
            x_enc = self.embedding(x_norm)
        else:
            x_enc = x_norm                                # Fourier yok — doğrudan kullan
        return self.net(x_enc)

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
