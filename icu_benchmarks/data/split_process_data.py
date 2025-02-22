import logging
import gin
import json
import hashlib
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
import pickle

from sklearn.model_selection import StratifiedKFold, KFold

from icu_benchmarks.data.preprocessor import Preprocessor, DefaultClassificationPreprocessor
from icu_benchmarks.contants import RunMode
from .constants import DataSplit as Split, DataSegment as Segment, VarType as Var


@gin.configurable("preprocess")
def preprocess_data(
    data_dir: Path,
    file_names: dict[str] = gin.REQUIRED,
    preprocessor: Preprocessor = DefaultClassificationPreprocessor,
    use_static: bool = True,
    vars: dict[str] = gin.REQUIRED,
    seed: int = 42,
    debug: bool = False,
    cv_repetitions: int = 5,
    repetition_index: int = 0,
    cv_folds: int = 5,
    load_cache: bool = False,
    generate_cache: bool = False,
    fold_index: int = 0,
    pretrained_imputation_model: str = None,
    runmode: RunMode = RunMode.classification,
) -> dict[dict[pd.DataFrame]]:
    """Perform loading, splitting, imputing and normalising of task data.

    Args:
        preprocessor: Define the preprocessor.
        data_dir: Path to the directory holding the data.
        file_names: Contains the parquet file names in data_dir.
        vars: Contains the names of columns in the data.
        seed: Random seed.
        debug: Load less data if true.
        cv_repetitions: Number of times to repeat cross validation.
        repetition_index: Index of the repetition to return.
        cv_folds: Number of folds to use for cross validation.
        load_cache: Use cached preprocessed data if true.
        generate_cache: Generate cached preprocessed data if true.
        fold_index: Index of the fold to return.
        pretrained_imputation_model: pretrained imputation model to use. if None, standard imputation is used.

    Returns:
        Preprocessed data as DataFrame in a hierarchical dict with features type (STATIC) / DYNAMIC/ OUTCOME
            nested within split (train/val/test).
    """

    cache_dir = data_dir / "cache"

    if not use_static:
        file_names.pop(Segment.static)
        vars.pop(Segment.static)

    dumped_file_names = json.dumps(file_names, sort_keys=True)
    dumped_vars = json.dumps(vars, sort_keys=True)

    logging.log(logging.INFO, f"Using preprocessor: {preprocessor.__name__}")
    preprocessor = preprocessor(use_static_features=use_static)
    if isinstance(preprocessor, DefaultClassificationPreprocessor):
        preprocessor.set_imputation_model(pretrained_imputation_model)

    hash_config = f"{preprocessor.to_cache_string()}{dumped_file_names}{dumped_vars}{debug}".encode("utf-8")
    cache_filename = f"s_{seed}_r_{repetition_index}_f_{fold_index}_d_{debug}_{hashlib.md5(hash_config).hexdigest()}"
    cache_file = cache_dir / cache_filename

    if load_cache:
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                logging.info(f"Loading cached data from {cache_file}.")
                return pickle.load(f)
        else:
            logging.info(f"No cached data found in {cache_file}, loading raw features.")

    # Read parquet files into pandas dataframes and remove the parquet file from memory
    logging.info(f"Loading data from directory {data_dir.absolute()}")
    data = {f: pq.read_table(data_dir / file_names[f]).to_pandas(self_destruct=True) for f in file_names.keys()}

    # Generate the splits
    logging.info("Generating splits.")
    data = make_single_split(
        data, vars, cv_repetitions, repetition_index, cv_folds, fold_index, seed=seed, debug=debug, runmode=runmode
    )

    # Apply preprocessing
    data = preprocessor.apply(data, vars)

    # Generate cache
    if generate_cache:
        caching(cache_dir, cache_file, data, load_cache)
    else:
        logging.info("Cache will not be saved.")

    logging.info("Finished preprocessing.")

    return data


def make_single_split(
    data: dict[pd.DataFrame],
    vars: dict[str],
    cv_repetitions: int,
    repetition_index: int,
    cv_folds: int,
    fold_index: int,
    seed: int = 42,
    debug: bool = False,
    runmode: RunMode = RunMode.classification,
) -> dict[dict[pd.DataFrame]]:
    """Randomly split the data into training, validation, and test set.

    Args:
        runmode: Run mode. Can be one of the values of RunMode
        data: dictionary containing data divided int OUTCOME, STATIC, and DYNAMIC.
        vars: Contains the names of columns in the data.
        cv_repetitions: Number of times to repeat cross validation.
        repetition_index: Index of the repetition to return.
        cv_folds: Number of folds for cross validation.
        fold_index: Index of the fold to return.
        seed: Random seed.
        debug: Load less data if true.

    Returns:
        Input data divided into 'train', 'val', and 'test'.
    """
    # ID variable
    id = vars[Var.group]

    # Get stay IDs from outcome segment
    stays = pd.Series(data[Segment.outcome][id].unique(), name=id)

    if debug:
        # Only use 1% of the data
        stays = stays.sample(frac=0.01, random_state=seed)

    # If there are labels, and the task is classification, use stratified k-fold
    if Var.label in vars and runmode is RunMode.classification:
        # Get labels from outcome data (takes the highest value (or True) in case seq2seq classification)
        labels = data[Segment.outcome].groupby(id).max()[vars[Var.label]].reset_index(drop=True)
        if labels.value_counts().min() < cv_folds:
            raise Exception(
                f"The smallest amount of samples in a class is: {labels.value_counts().min()}, "
                f"but {cv_folds} folds are requested. Reduce the number of folds or use more data."
            )
        outer_cv = StratifiedKFold(cv_repetitions, shuffle=True, random_state=seed)
        inner_cv = StratifiedKFold(cv_folds, shuffle=True, random_state=seed)

        dev, test = list(outer_cv.split(stays, labels))[repetition_index]
        dev_stays = stays.iloc[dev]
        train, val = list(inner_cv.split(dev_stays, labels.iloc[dev]))[fold_index]
    else:
        # If there are no labels, or the task is regression, use regular k-fold.
        outer_cv = KFold(cv_repetitions, shuffle=True, random_state=seed)
        inner_cv = KFold(cv_folds, shuffle=True, random_state=seed)

        dev, test = list(outer_cv.split(stays))[repetition_index]
        dev_stays = stays.iloc[dev]
        train, val = list(inner_cv.split(dev_stays))[fold_index]

    split = {
        Split.train: dev_stays.iloc[train],
        Split.val: dev_stays.iloc[val],
        Split.test: stays.iloc[test],
    }
    data_split = {}

    for fold in split.keys():  # Loop through splits (train / val / test)
        # Loop through segments (DYNAMIC / STATIC / OUTCOME)
        # set sort to true to make sure that IDs are reordered after scrambling earlier
        data_split[fold] = {
            data_type: data[data_type].merge(split[fold], on=id, how="right", sort=True) for data_type in data.keys()
        }

    return data_split


def caching(cache_dir, cache_file, data, use_cache, overwrite=True):
    if use_cache and (not overwrite or not cache_file.exists()):
        if not cache_dir.exists():
            cache_dir.mkdir()
        cache_file.touch()
        with open(cache_file, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        logging.info(f"Cached data in {cache_file}.")
