import os
import gin
import torch
import logging
import pandas as pd
from torch.optim import Adam
from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint, TQDMProgressBar
from pytorch_lightning.loggers import TensorBoardLogger, WandbLogger
from torch.utils.data import DataLoader
from pathlib import Path

from icu_benchmarks.wandb_utils import set_wandb_run_name
from icu_benchmarks.data.loader import ClassificationDataset, ImputationDataset
from icu_benchmarks.models.utils import save_config_file, JSONMetricsLogger
from icu_benchmarks.contants import RunMode
from icu_benchmarks.data.constants import DataSplit as Split


@gin.configurable("train_common")
def train_common(
    data: dict[str, pd.DataFrame],
    log_dir: Path,
    load_weights: bool = False,
    source_dir: Path = None,
    reproducible: bool = True,
    mode: str = RunMode.classification,
    model: object = gin.REQUIRED,
    weight: str = None,
    optimizer: type = Adam,
    batch_size=64,
    epochs=1000,
    patience=20,
    min_delta=1e-5,
    test_on: str = Split.test,
    use_wandb: bool = True,
    cpu: bool = False,
    num_workers: int = min(len(os.sched_getaffinity(0)), torch.cuda.device_count() * 4 * int(torch.cuda.is_available()), 16),
):
    """Common wrapper to train all benchmarked models.

    Args:
        data: Dict containing data to be trained on.
        log_dir: Path to directory where model output should be saved.
        load_weights: If set to true, skip training and load weights from source_dir instead.
        source_dir: If set to load weights, path to directory containing trained weights.
        reproducible: If set to true, set torch to run reproducibly.
        mode: Mode of the model. Can be one of the values of RunMode.
        model: Model to be trained.
        weight: Weight to be used for the loss function.
        optimizer: Optimizer to be used for training.
        batch_size: Batch size to be used for training.
        epochs: Number of epochs to train for.
        patience: Number of epochs to wait before early stopping.
        min_delta: Minimum change in loss to be considered an improvement.
        test_on: If set to "test", evaluate the model on the test set. If set to "val", evaluate on the validation set.
        use_wandb: If set to true, log to wandb.
        num_workers: Number of workers to use for data loading.
    """
    logging.info(f"Training model: {model.__name__}")
    DatasetClass = ImputationDataset if mode == RunMode.imputation else ClassificationDataset

    logging.info(f"Logging to directory: {log_dir}")
    save_config_file(log_dir)  # We save the operative config before and also after training

    train_dataset = DatasetClass(data, split=Split.train)
    val_dataset = DatasetClass(data, split=Split.val)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
    )

    data_shape = next(iter(train_loader))[0].shape
    logging.info(f"performing task on model {model.__name__}...")

    model = model(optimizer=optimizer, input_size=data_shape, epochs=epochs)
    model.set_weight(weight, train_dataset)
    if load_weights:
        if source_dir.exists():
            # if not model.needs_training:
            checkpoint = torch.load(source_dir / "model.ckpt")
            # else:
            model = model.load_state_dict(checkpoint["state_dict"])
        else:
            raise Exception(f"No weights to load at path : {source_dir}")
    
    model.set_trained_columns(train_dataset.get_feature_names())

    loggers = [TensorBoardLogger(log_dir), JSONMetricsLogger(log_dir)]
    if use_wandb:
        run_name = f"{type(model).__name__}"
        loggers.append(WandbLogger(run_name, save_dir=log_dir))
        set_wandb_run_name(run_name)

    trainer = Trainer(
        # model=model,
        max_epochs=epochs if model.needs_training else 1,
        callbacks=[
            EarlyStopping(monitor="val/loss", min_delta=min_delta, patience=patience, strict=False),
            ModelCheckpoint(log_dir, filename="model", save_top_k=1, save_last=True),
            TQDMProgressBar(refresh_rate=min(50, len(train_loader) // 2)),
        ],
        # precision=16,
        accelerator="auto" if not cpu else "cpu",
        devices=max(torch.cuda.device_count(), 1),
        deterministic=reproducible,
        benchmark=not reproducible,
        logger=loggers,
        num_sanity_val_steps=0,
        log_every_n_steps=1 if model.needs_fit else 100,
    )

    if model.needs_fit:
        logging.info("fitting model to data...")
        model.fit(train_dataset, val_dataset)
        try:
            torch.save(model, log_dir / "last.ckpt")
        except Exception as e:
            logging.error(f"Cannot save model to path {str((log_dir / 'last.ckpt').resolve())}: {e}")
        logging.info("fitting complete!")

    if model.needs_training:
        logging.info("Training model.")
        trainer.fit(model, train_dataloaders=train_loader, val_dataloaders=val_loader)
        logging.info("Training complete.")


    test_dataset = DatasetClass(data, split=test_on)
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size * 4,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    ) if model.needs_training else DataLoader([test_dataset.to_tensor()], batch_size=1)

    model.set_weight("balanced", train_dataset)
    test_loss = trainer.test(
        model,
        dataloaders=test_loader,
    )[0]["test/loss"]
    save_config_file(log_dir)
    return test_loss
