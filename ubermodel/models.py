#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: models.py
Author: ned haughton
Email: ned@nedhaughton.com
Github: https://github.com/naught101
Description:
"""

import yaml
import sys

from sklearn.linear_model import LinearRegression
from sklearn.cluster import MiniBatchKMeans
from collections import OrderedDict

from pals_utils.constants import MET_VARS
from ubermodel.clusterregression import ModelByCluster
from ubermodel.transforms import MissingDataWrapper, LagAverageWrapper

from sklearn.pipeline import make_pipeline


#################
# Model loaders
#################

def get_model(name):
    """returns a scikit-learn style model/pipeline

    :name: model name
    :returns: scikit-learn style mode/pipeline

    """

    try:
        model = get_model_from_def(name)
    except Exception:
        try:
            model = get_model_from_yaml(name)
        except KeyError:
            sys.exit("Unknown model {n}".format(n=name))

    if not hasattr(model, 'name'):
        model.name = name

    return model


def get_model_from_def(name):
    """returns a scikit-learn style model/pipeline

    :name: model name
    :returns: scikit-learn style mode/pipeline

    """
    if name == '1lin':
        model = MissingDataWrapper(LinearRegression())
        model.forcing_vars = ['SWdown']
    if name == '3km27':
        model = MissingDataWrapper(ModelByCluster(MiniBatchKMeans(27),
                                                  LinearRegression()))
        model.forcing_vars = ['SWdown', 'Tair', 'RelHum']
    if name == '3km233':
        model = MissingDataWrapper(ModelByCluster(MiniBatchKMeans(233),
                                                  LinearRegression()))
        model.forcing_vars = ['SWdown', 'Tair', 'RelHum']
    if name == '3km27_lag':
        model_dict = {
            'variable': ['SWdown', 'Tair', 'RelHum'],
            'clusterregression': {
                'class': MiniBatchKMeans,
                'args': {
                    'n_clusters': 27}
            },
            'class': LinearRegression,
            'lag': {
                'periods': 1,
                'freq': 'D'}
        }
        model = MissingDataWrapper(get_model_from_dict(model_dict))
        model.forcing_vars = ['SWdown', 'Tair', 'RelHum']
    if name == '5km27_lag':
        var_lags = OrderedDict()
        [var_lags.update({v: ['cur', '2d', '7d']}) for v in ['SWdown', 'Tair', 'RelHum', 'Wind']]
        var_lags.update({'Rainf': ['cur', '2d', '7d', '30d', '90d']})
        model = LagAverageWrapper(var_lags,
                                  MissingDataWrapper(ModelByCluster(MiniBatchKMeans(27),
                                                                    LinearRegression()))
                                  )
        model.forcing_vars = ['SWdown', 'Tair', 'RelHum', 'Wind', 'Rainf']
    else:
        raise Exception("unknown model")

    return model


def get_model_from_yaml(name):
    """return a model as defines in model_search.yaml

    :returns: sklearn model pipeline

    """
    with open('data/model_search.yaml') as f:
        model_dict = yaml.load(f)[name]

    return get_model_from_dict(model_dict)


def get_model_from_dict(model_dict):
    """Return a sklearn model pipeline from a model_dict"""

    pipe_list = []

    if 'transforms' in model_dict:
        # For basic scikit-learn transforms
        transforms = model_dict['transforms'].copy()
        if 'scaler' in transforms:
            scaler = transforms.pop('scaler')
            pipe_list.append(get_scaler(scaler))
        if 'pca' in transforms:
            transforms.pop('pca')
            pipe_list.append(get_pca())
        if 'poly' in transforms:
            args = transforms.pop('poly')
            pipe_list.append(get_poly(args))
        if len(transforms) > 0:
            raise Exception("unknown transforms: %s" % repr(transforms))

    if 'args' in model_dict:
        model = get_model_class(model_dict['class'], model_dict['args'])
    else:
        model = get_model_class(model_dict['class'])

    if 'clusterregression' in model_dict:
        from ubermodel.clusterregression import ModelByCluster
        clusterer = model_dict['clusterregression']['class']
        cluster_args = model_dict['clusterregression']['args']
        model = ModelByCluster(
            get_clusterer(clusterer, cluster_args),
            model)

    pipe_list.append(model)

    pipe = make_pipeline(*pipe_list)

    if 'lag' in model_dict:
        params = model_dict['lag']
        pipe = get_lagger(pipe, params)
    elif 'markov' in model_dict:
        params = model_dict['markov']
        pipe = get_markov_wrapper(pipe, params)

    if 'forcing_vars' in model_dict:
        pipe.forcing_vars = model_dict['forcing_vars']
    else:
        print("Warning: no forcing vars, using defaults (all)")
        pipe.forcing_vars = MET_VARS

    return pipe


def get_lagger(pipe, kwargs):
    """Return a Lag wrapper for a pipeline."""
    from .transforms import LagWrapper
    return LagWrapper(pipe, **kwargs)


def get_markov_wrapper(pipe, kwargs):
    """Return a markov wrapper for a pipeline."""
    from .transforms import MarkovWrapper
    return MarkovWrapper(pipe, **kwargs)


def get_clusterer(name, kwargs):
    """Return a scikit-learn clusterer from name and args."""

    if name == 'KMeans':
        from sklearn.cluster import KMeans
        return KMeans(**kwargs)
    if name == 'MiniBatchKMeans':
        from sklearn.cluster import KMeans
        return KMeans(**kwargs)


def get_scaler(scaler):
    """get a sklearn scaler from a scaler name

    :scaler: scaler identifier, one of ['standard', 'minmax']
    :returns: sklearn scaler

    """
    if scaler == 'standard':
        from sklearn.preprocessing import StandardScaler
        return StandardScaler()
    if scaler == 'minmax':
        from sklearn.preprocessing import MinMaxScaler
        return MinMaxScaler()


def get_pca():
    """get a PCA decomposition
    :returns: sklearn PCA decomposer

    """
    from sklearn.decomposition import PCA
    return PCA()


def get_poly(kwargs):
    """get a PolynomialFeatures transform

    :kwargs: arguments to PolynomialFeatures
    :returns: PolynomialFeatures instance

    """
    from sklearn.preprocessing import PolynomialFeatures
    return PolynomialFeatures(**kwargs)


def get_model_class(class_name, kwargs={}):
    """return a scikit-learn model class, and the required arguments

    :class_name: name of the model class
    :returns: model class object
    """
    # , Perceptron, PassiveAggressiveRegressor
    # , NuSVR, LinearSVR

    if class_name == 'LinearRegression':
        from sklearn.linear_model import LinearRegression
        return LinearRegression(**kwargs)

    if class_name == 'SGDRegressor':
        from sklearn.linear_model import SGDRegressor
        return SGDRegressor(**kwargs)

    if class_name == 'SVR':
        from sklearn.svm import SVR
        return SVR(**kwargs)

    if class_name == 'DecisionTreeRegressor':
        from sklearn.tree import DecisionTreeRegressor
        return DecisionTreeRegressor(**kwargs)

    if class_name == 'ExtraTreesRegressor':
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor(**kwargs)

    if class_name == 'KNeighborsRegressor':
        from sklearn.neighbors import KNeighborsRegressor
        return KNeighborsRegressor(**kwargs)

    if class_name == 'MLPRegressor':
        from sklearn.neural_network import MLPRegressor
        return MLPRegressor(**kwargs)

    raise Exception("Unknown Model class")
