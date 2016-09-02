#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: residuals_analysis.py
Author: naught101
Email: naught101@email.com
Github: https://github.com/naught101/
Description: TODO: File description

Usage:
    residuals_analysis.py <plot_type> <site> [<var>]
    residuals_analysis.py (-h | --help | --version)

Options:
    plot_type     "scatter" or "hexbin"
    site          name of a PALS site, or "all"
    var           name of a driving variable, or "all"
    -h, --help    Show this screen and exit.
"""

from docopt import docopt

import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from pals_utils import data as pud

from scripts.lag_average_assessment import rolling_mean


def get_lagged_df(df, lags=['30min', '2h', '6h', '2d', '7d', '30d', '90d']):
    """Get lagged variants of variables"""

    data = {}
    for v in df.columns:
        data[v] = pd.DataFrame(
            np.concatenate([rolling_mean(df[[v]].values, l) for l in lags], axis=1),
            columns=lags, index=df.index)
    return pd.concat(data, axis=1)


def time_fmt(t):
    if 'min' in t:
        return "000.00:{m:02}".format(m=int(t.rstrip('min')))
    elif 'h' in t:
        return "000.{h:02}:00".format(h=int(t.rstrip('h')))
    elif 'd' in t:
        return "{d:03}.00:00".format(d=int(t.rstrip('d')))


def threekm27_residuals(sites, var):
    """Save 3km27 residuals and met to a csv."""

    met_vars = ['SWdown', 'Tair', 'RelHum', 'Wind', 'Rainf']
    flux_vars = ['Qle', 'Qh']

    flux_df = (pud.get_flux_df(sites, flux_vars, name=True, qc=True)
                  .reorder_levels(['site', 'time'])
                  .sort_index())
    threekm27 = (pud.get_pals_benchmark_df('3km27', sites, ['Qle', 'Qh'])
                    .sort_index())
    residuals = (threekm27 - flux_df)
    residuals.columns = ['3km27 %s residual' % v for v in residuals.columns]

    if var in met_vars:
        forcing = (pud.get_met_df(sites, [var], name=True, qc=True)
                      .reorder_levels(['site', 'time'])
                      .sort_index())
    else:
        forcing = (pud.get_flux_df(sites, [var], name=True, qc=True)
                      .reorder_levels(['site', 'time'])
                      .sort_index())

    lagged_forcing = forcing.groupby(level='site').apply(get_lagged_df)

    lagged_forcing.columns = ["{v} {t} mean".format(v=c[0], t=time_fmt(c[1])) for c in lagged_forcing.columns.values]

    out_df = pd.concat([residuals, lagged_forcing], axis=1)

    return out_df


def scatter(df, x, y):
    return df[[x, y]].dropna().plot.scatter(x, y, s=3, alpha=0.2, edgecolors='face')


def hexbin(df, x, y):
    return df[[x, y]].dropna().plot.hexbin(x, y, bins='log')

def regplot(df, x, y):
    subset = df[[x, y]].dropna().sample(10000)
    return sns.regplot(x, y, data=subset,
                       n_boot=200, truncate=True,
                       scatter_kws=dict(alpha=0.2),
                       line_kws=dict(color='red'))

def regplot2(df, x, y, order=4):
    subset = df[[x, y]].dropna().sample(10000)

    poly = np.poly1d(np.polyfit(subset[x], subset[y], order))
    RSS = ((subset[y] - poly(subset[x])) ** 2).sum()
    SStot = ((subset[y] - subset[y].mean()) ** 2).sum()
    R2 = 1 - RSS /  SStot

    ax = subset.plot.scatter(x, y, s=3, alpha=0.2, edgecolors='face')
    x_plot = np.linspace(subset[x].min(), subset[x].max(), 1000)
    plt.plot(x_plot, poly(x_plot), color='red')
    plt.text(0.7, 0.9, "poly(%d), R2: %0.2f" % (order, R2),
             transform=ax.transAxes)


def plot_stuff(plot_type, site, var):
    """Plots some stuff, you know?"""

    if site == 'all':
        sites = ["Amplero", "Blodgett", "Bugac", "ElSaler", "ElSaler2",
                 "Espirra", "FortPeck", "Harvard", "Hesse", "Howard", "Howlandm",
                 "Hyytiala", "Kruger", "Loobos", "Merbleue", "Mopane", "Palang",
                 "Sylvania", "Tumba", "UniMich"]
    else:
        sites = [site]

    if var == 'all' or var is None:
        variables = ['Qle', 'Qh', 'SWdown', 'Tair', 'RelHum', 'Wind', 'Rainf']
    else:
        variables = [var]

    for var in variables:
        out_df = threekm27_residuals(sites, var)

        # out_df.dropna().to_csv('Tumba3km27residuals_lagged.csv')

        y_vars = ['3km27 %s residual' % v for v in ['Qle', 'Qh']]
        x_vars = list(set(out_df.columns).difference(y_vars))

        if plot_type == 'scatter':
            plot_fn = scatter
        if plot_type == 'hexbin':
            plot_fn = hexbin
        if plot_type == 'regplot':
            plot_fn = regplot
        if plot_type == 'regplot2':
            plot_fn = regplot2

        for y in y_vars:
            for x in x_vars:
                try:
                    plot_fn(out_df, x, y)
                    plt.title("{y} by {x} at site: {s}".format(x=x, y=y, s=site))
                    path = 'plots/lag plots {pt}'.format(pt=plot_type)
                    os.makedirs(path, exist_ok=True)
                    plt.savefig('{p}/{s} {y} by {x} {pt}.png'.format(s=site, x=x, y=y, pt=plot_type, p=path))
                    print("%s: %s by %s" % (plot_type, y, x))
                    plt.close()
                except Exception as e:
                    print('%s for %s by %s failed - %s' % (plot_type, y, x, e))


def main(args):

    plot_stuff(args['<plot_type>'], args['<site>'], args['<var>'])

    return


if __name__ == '__main__':
    args = docopt(__doc__)

    main(args)