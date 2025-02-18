#!/usr/bin/env ptargetthon3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 4 2019

@author: toshiki.ishikawa
"""
import warnings
warnings.simplefilter('ignore')

import os
import gc 
import sys
import datetime
import utils

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from tqdm import tqdm
from collections import defaultdict
from multiprocessing import cpu_count
from catboost import Pool, CatBoost

from sklearn.model_selection import StratifiedKFold, KFold 
from sklearn.metrics import roc_auc_score

utils.start(__file__)
#==============================================================================
# LOGGER
#==============================================================================
from logging import getLogger, FileHandler, Formatter, DEBUG
logger = getLogger(__name__)
logger.setLevel(DEBUG)

file_handler = FileHandler(os.path.join('logs', 'log_{}'.format(str(datetime.datetime.today().date()).replace('-', ''))))
formatter = Formatter('%(message)s')
file_handler.setFormatter(formatter)
file_handler.setLevel(DEBUG)

logger.addHandler(file_handler)
logger.propagate = False

#==============================================================================

PATH = os.path.join('..', 'data')

KEY = 'ID_code'

SEED = 6
# SEED = np.random.randint(9999)

NTHREAD = cpu_count()

NFOLDS = 5

# =============================================================================
# READ DATA
# =============================================================================
train = pd.read_csv(os.path.join(PATH, 'train.csv'))
test = pd.read_csv(os.path.join(PATH, 'test.csv'))

# =============================================================================
# ADD HANDCRAFTED FEATURES
# =============================================================================

# =============================================================================
# PREPROCESS
# =============================================================================
y = train['target']

not_use_cols = ['ID_code', 'target'] 
use_cols = [c for c in train.columns if c not in not_use_cols]

X = train[use_cols]
X_test = test[use_cols]

# =============================================================================
# PARAMS
# =============================================================================
params_in_train = {
    'early_stopping_rounds': 200,
    'verbose_eval': 500,
    'use_best_model': True,
}

params = {
    'boosting': 'gbdt',
    'bootstrap_type': 'Bayesian',
    'eval_metric': 'AUC',
    'objective': 'Logloss',
    'iterations': 100000,
    'max_depth': 6,
    'learning_rate': 0.01,
    # 'subsample': 0.6,
    'thread_count': cpu_count(),
    'verbose': 0,
    'random_seed': SEED, # int(2**fold_n),
}

# =============================================================================
# CV
# =============================================================================
skf = StratifiedKFold(n_splits=NFOLDS, shuffle=True, random_state=SEED)

oof = np.zeros(len(X))
predictions = np.zeros(len(X_test))
scores = []

for fold, (train_index, valid_index) in enumerate(skf.split(X, y)):
    print('fold: {}/{}'.format(fold+1, skf.n_splits))
    
    dtrain = Pool(data=X.iloc[train_index], label=y.iloc[train_index])
    dvalid = Pool(data=X.iloc[valid_index], label=y.iloc[valid_index])
    
    model = CatBoost(params)
    model = model.fit(dtrain, eval_set=[dtrain, dvalid], **params_in_train)
    oof[valid_index] = model.predict(dvalid)
    scores.append(roc_auc_score(y.iloc[valid_index], oof[valid_index])**0.5)

    predictions += model.predict(Pool(data=X_test)) / NFOLDS

    del model

cv_score = roc_auc_score(y, oof)**0.5
print('Shape: {}'.format(X.shape))
print('Num folds: {}'.format(NFOLDS))
print('Scores: mean {:.5f}, max {:.5f}, min {:.5f}, std {:.5f}'.format(
    np.mean(scores), np.max(scores), np.min(scores), np.std(scores)))
print('CV Score: {:<8.5f}'.format(cv_score))

logger.info('''
# ============================================================================= 
# SUMMARY                                                     
# =============================================================================
''')
logger.info('Shape: {}'.format(X.shape))
logger.info('Num folds: {}'.format(NFOLDS))
logger.info('Train Scores: mean {:.5f}, max {:.5f}, min {:.5f}, std {:.5f}'.format(
    np.mean(scores['train']), np.max(scores['train']), np.min(scores['train']), np.std(scores['train'])))
logger.info('Valid Scores: mean {:.5f}, max {:.5f}, min {:.5f}, std {:.5f}'.format(
    np.mean(scores['valid']), np.max(scores['valid']), np.min(scores['valid']), np.std(scores['valid'])))
logger.info('CV Score: {:<8.5f}'.format(cv_score))
logger.info('''
# ============================================================================= 
# END                                              
# =============================================================================
''')

submission = pd.read_csv(os.path.join(PATH, 'sample_submission.csv'))
submission['target'] = predictions
submission.to_csv('../submission/lightgbm.csv', index=False)

#==============================================================================
utils.end(__file__)