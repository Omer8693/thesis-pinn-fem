"""
sa_trainer.py — Self-Adaptive PINN Eğitici
============================================
Standart AdamTrainer'dan farkı:
  1. İki ayrı parametre grubu:
       - model_params : θ  → gradient DESCENT  (lr_model)
       - sa_params    : λ  → gradient ASCENT    (lr_lambda)
     λ parametreleri zor kısıtlara otomatik ağırlık verir.

  2. CosineAnnealingWarmRestarts zamanlayıcı:
       T_0=5000, T_mult=2  →  5k, 10k, 20k epoch'ta yeniden başlar
     Warm restart sayesinde yerel minimumdan çıkılır.

  3. L2 doğrulama — her val_every epoch'ta ölçülür ve kaydedilir.
"""

import time
from copy import deepcopy
from typing import Callable, Dict, Optional

import numpy as np
import torch
import torch.nn as nn

from src.config import DEVICE


class SATrainer:
    """
    Self-Adaptive PINN eğitici.

    Parametreler:
      model      : FourierPINN
      sa_weights : SelfAdaptiveWeights (kayıp fonksiyonuna gömülü)
      loss_fn    : SAQuenchingLoss — (model, batch) → (loss, details)
      lr_model   : θ için öğrenme hızı (varsayılan: 1e-3)
      lr_lambda  : λ için öğrenme hızı (varsayılan: 1e-4, daha yavaş)
      T_0        : CosineAnnealing ilk periyot
      T_mult     : Her yeniden başlamada periyot çarpanı
    """

    def __init__(self,
                 model:      nn.Module,
                 sa_weights: nn.Module,
                 loss_fn:    Callable,
                 lr_model:   float = 1e-3,
                 lr_lambda:  float = 1e-4,
                 T_0:        int   = 5000,
                 T_mult:     int   = 2):

        self.model      = model
        self.sa_weights = sa_weights
        self.loss_fn    = loss_fn
        self.history    = {"loss": [], "l2": [], "lambda_phys": [],
                           "lambda_bc": [], "lambda_ic": []}

        # İki ayrı parametre grubu — θ düşük LR, λ daha düşük LR
        self.optimizer = torch.optim.Adam([
            {"params": model.parameters(),      "lr": lr_model},
            {"params": sa_weights.parameters(), "lr": lr_lambda},
        ])

        # StepLR — Level 1 ile aynı (step=1000, gamma=0.9)
        # PINN'ler için CosineWarmRestart KÖTÜ: LR spike'ları minimuı bozar
        self.scheduler = torch.optim.lr_scheduler.StepLR(
            self.optimizer, step_size=1000, gamma=0.9
        )

    def _ascent_step(self):
        """λ parametreleri descent kullanır (ascent eğitimi dengesizleştiriyor).
        Farklı LR ile descent: ağırlıklar yavaş uyum sağlar."""
        pass  # artık sadece descent kullanılıyor

    def train(self,
              get_batch:  Callable,
              n_epochs:   int = 30_000,
              val_fn:     Optional[Callable] = None,
              val_every:  int = 500,
              print_every: int = 1000,
              ) -> Dict:
        # Epoch sayısından büyük olmasın
        val_every   = min(val_every,   max(1, n_epochs // 10))
        print_every = min(print_every, max(1, n_epochs // 5))

        print(f"\n{'═'*54}")
        print(f"  SA-PINN + FOURIER TRAINING  ({n_epochs:,} epochs)")
        print(f"{'═'*54}")

        t0         = time.time()
        best_l2    = float("inf")
        best_state = None

        for epoch in range(1, n_epochs + 1):
            self.model.train()
            self.sa_weights.train()

            batch = get_batch(epoch)

            self.optimizer.zero_grad()
            loss, details = self.loss_fn(self.model, batch)
            loss.backward()

            # θ: descent, λ: ascent
            self._ascent_step()

            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            self.scheduler.step()

            self.history["loss"].append(details["L_total"])
            self.history["lambda_phys"].append(details["lambda_phys"])
            self.history["lambda_bc"].append(details["lambda_bc"])
            self.history["lambda_ic"].append(details["lambda_ic"])

            # Doğrulama
            if val_fn is not None and epoch % val_every == 0:
                l2 = val_fn(self.model)
                self.history["l2"].append({"epoch": epoch, "l2": l2})
                if l2 < best_l2:
                    best_l2    = l2
                    best_state = deepcopy(self.model.state_dict())

            # Ekran çıktısı
            if epoch % print_every == 0:
                elapsed = time.time() - t0
                l2_str  = f"{best_l2:.4f}" if best_l2 < 1e9 else "—"
                w       = self.sa_weights.weights_dict()
                print(
                    f"  ep {epoch:6d}/{n_epochs} | "
                    f"loss={details['L_total']:.3e} | "
                    f"L2={l2_str} | "
                    f"λ=({w['lambda_phys']:.1f},{w['lambda_bc']:.1f},{w['lambda_ic']:.1f}) | "
                    f"{elapsed:.0f}s"
                )

        # En iyi ağırlıkları geri yükle
        if best_state is not None:
            self.model.load_state_dict(best_state)

        print(f"\n  Eğitim tamamlandı — en iyi L2 = {best_l2:.4f}")
        return {"best_l2": best_l2, "history": self.history}
