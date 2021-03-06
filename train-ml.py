import pandas as pd
import numpy as np

import datetime
import time
import argparse

from numba import jit

from meta import train_dates, test_date, target_columns
from util import Dataset

from kaggle_util import Xgb

from sklearn.utils import resample


parser = argparse.ArgumentParser(description='Train model')
parser.add_argument('--optimize', action='store_true', help='optimize model params')
parser.add_argument('--threads', type=int, default=4, help='specify thread count')

args = parser.parse_args()


min_eval_date = '2016-05-28'

train_data = None
train_targets = None

old_sample_rate = 0.9

model = Xgb({
    'objective': 'multi:softprob',
    'eval_metric': 'mlogloss',
    'num_class': len(target_columns),
    'nthread': args.threads,
    'max_depth': 4,
}, 200)

param_grid = {'max_depth': (3, 8), 'min_child_weight': (1, 10), 'subsample': (0.5, 1.0), 'colsample_bytree': (0.5, 1.0)}

feature_parts = ['manual']
feature_names = sum(map(Dataset.get_part_features, feature_parts), [])


def densify(d):
    if hasattr(d, 'toarray'):
        return d.toarray()
    else:
        return d


def load_data(dt):
    idx = pd.read_pickle('cache/basic-%s.pickle' % dt).index
    data = [densify(Dataset.load_part(dt, p)) for p in feature_parts]

    return idx, np.hstack(data)


def prepare_data(data, targets):
    res_data = []
    res_targets = []

    for c in xrange(len(target_columns)):
        idx = targets[:, c] > 0
        cnt = idx.sum()

        if cnt > 0:
            res_data.append(data[idx])
            res_targets.append(np.full(cnt, c, dtype=np.uint8))

    if len(res_data) > 0:
        return np.vstack(res_data), np.hstack(res_targets)
    else:
        return np.zeros((0, data.shape[1])), np.zeros(0)


def add_to_train(data, targets):
    """ Train on encoded rows and their targets """

    global train_data, train_targets

    data, targets = prepare_data(data, targets)

    if train_data is None:
        train_data = data
        train_targets = targets
    else:
        if old_sample_rate < 1:  # Subsample old data
            train_data, train_targets = resample(train_data, train_targets, replace=False, n_samples=int(len(train_targets) * old_sample_rate), random_state=len(train_targets))

        train_data = np.vstack((train_data, data))
        train_targets = np.hstack((train_targets, targets))

    print "    Train data shape: %s" % str(train_data.shape)
    print "    Train targets shape: %s" % str(train_targets.shape)


def predict(data, prev_products, targets=None):
    """ Predict """

    shape = (data.shape[0], len(target_columns))

    if targets is None:
        pred = model.fit_predict(train=(train_data, train_targets), test=(data,), param_grid=param_grid, feature_names=feature_names)
    else:
        if args.optimize:
            model.optimize(train=(train_data, train_targets), val=prepare_data(data, targets), feature_names=feature_names)

        pred = model.fit_predict(train=(train_data, train_targets), val=prepare_data(data, targets), test=(data,), feature_names=feature_names)

    # Reshape scores, exclude previously bought products
    scores = pred['ptest'].reshape(shape) * (1 - prev_products)

    # Convert scores to predictions
    return np.argsort(-scores, axis=1)[:, :8]


@jit
def apk(actual, pred):
    m = actual.sum()

    if m == 0:
        return 0

    res = 0.0
    hits = 0.0

    for i, col in enumerate(pred):
        if i >= 7:
            break

        if actual[col] > 0:
            hits += 1
            res += hits / (i + 1.0)

    return res / min(m, 7)


def mapk(targets, predictions):
    total = 0.0

    for i, pred in enumerate(predictions):
        total += apk(targets[i], pred)

    return total / len(targets)


def generate_submission(pred):
    return [' '.join(target_columns[i] for i in p) for p in pred]


map_score = None

start_time = time.time()


for dt in train_dates[1:]:  # Skipping first date
    print "%ds, processing %s..." % (time.time() - start_time, dt)
    targets = Dataset.load_part(dt, 'targets').toarray()
    idx, data = load_data(dt)

    if dt >= min_eval_date:
        prev_products = Dataset.load_part(dt, 'prev-products').toarray()

        print "  Predicting..."

        predictions = predict(data, prev_products, targets)
        #print predictions
        map_score = mapk(targets, predictions)

        print "  MAP@7: %.7f" % map_score

    print "  Adding to train..."
    add_to_train(data, targets)


pred_name = 'ml-%s-%.7f' % (datetime.datetime.now().strftime('%Y%m%d-%H%M'), map_score)


if True:
    print "Processing test..."

    idx, data = load_data(test_date)

    prev_products = Dataset.load_part(test_date, 'prev-products').toarray()

    print "  Predicting..."
    pred = predict(data, prev_products)

    subm = pd.DataFrame({'ncodpers': idx, 'added_products': generate_submission(pred)})
    subm.to_csv('subm/%s.csv.gz' % pred_name, index=False, compression='gzip')

print "Prediction name: %s" % pred_name
print "Done."
