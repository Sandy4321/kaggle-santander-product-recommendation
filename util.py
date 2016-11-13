import numpy as np
import scipy.sparse as sp

import cPickle as pickle

import os

cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')


def save_pickle(filename, data):
    with open(filename, 'w') as f:
        pickle.dump(data, f)


def load_pickle(filename):
    with open(filename) as f:
        return pickle.load(f)


def save_csr(filename, array):
    np.savez_compressed(filename, data=array.data, indices=array.indices, indptr=array.indptr, shape=array.shape)


def load_csr(filename):
    loader = np.load(filename)

    return sp.csr_matrix((loader['data'], loader['indices'], loader['indptr']), shape=loader['shape'])


class Dataset(object):

    part_types = {
        'basic': 'df',
        'targets': 'sp',
        'products': 'sp'
    }

    parts = part_types.keys()

    @classmethod
    def save_part_features(cls, part_name, features):
        save_pickle('%s/%s-features.pickle' % (cache_dir, part_name), features)

    @classmethod
    def get_part_features(cls, part_name):
        return load_pickle('%s/%s-features.pickle' % (cache_dir, part_name))

    @classmethod
    def load(cls, dt, parts):
        return cls(**{part_name: cls.load_part(dt, part_name) for part_name in parts})

    @classmethod
    def load_part(cls, dt, part_name):
        if cls.part_types[part_name] == 'sp':
            return load_csr('%s/%s-%s.npz' % (cache_dir, part_name, dt))
        else:
            return pd.read_pickle('%s/%s-%s.pickle' % (cache_dir, part_name, dt))

    @classmethod
    def save_part(cls, dt, part_name, part):
        if cls.part_types[part_name] == 'sp':
            save_csr('%s/%s-%s.npz' % (cache_dir, part_name, dt), part)
        elif self.part_types[part_name] == 'df':
            part.to_pickle('%s/%s-%s.pickle' % (cache_dir, part_name, dt))
        else:
            raise ValueError

    def __init__(self, **parts):
        self.parts = parts

    def __getitem__(self, key):
        return self.parts[key]

    def save(self, dt):
        for part_name in self.parts:
            self.save_part(dt, part_name, self.parts[part_name])