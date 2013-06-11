"""
CanICA
"""

# Author: ALexandre Abraham, Gael Varoquaux,
# License: BSD 3 clause

import numpy as np
from scipy import stats

from sklearn.decomposition import fastica
from sklearn.externals.joblib import Memory
from sklearn.utils import check_random_state
from sklearn.utils.extmath import randomized_svd

from .multi_pca import MultiPCA


class CanICA(MultiPCA):
    """Perform Canonical Independent Component Analysis.

    Parameters
    ----------
    data: array-like, shape = [[n_samples, n_features], ...]
        Training vector, where n_samples is the number of samples,
        n_features is the number of features. There is one vector per
        subject.

    n_components: int
        Number of components to extract

    kurtosis_thr: boolean or float
        If kurtosis_thr is None, the algorithm is run regardless of the
        kurtosis. If it is False, then the algorithm will iter on the
        number of components to find a kurtosis greater than their number.
        If float, the kurtosis will additionally be thresholded by the
        given value.

    maps_only: boolean, optional
        If maps_only is true, the time-series corresponding to the
        spatial maps are not learned.

    random_state: int or RandomState
        Pseudo number generator state used for random sampling.


    """

    kurtosis_thr = None
    n_components = 20
    maps_only = True
    random_state = 0

    def _find_high_kurtosis(self, pcas, memory):
        random_state = check_random_state(self.random_state)

        if not self.kurtosis_thr:
            kurtosis_thr = -np.inf
        else:
            kurtosis_thr = self.kurtosis_thr
        n_components = self.n_components

        while n_components < 3 * self.n_components:
            group_maps = memory.cache(
                randomized_svd)(pcas, n_components)[0]
            group_maps = group_maps[:, :n_components]

            ica_maps = memory.cache(fastica)(group_maps, whiten=False,
                                             fun='cube',
                                             random_state=random_state)[2]
            ica_maps = ica_maps.T
            kurtosis = stats.kurtosis(ica_maps, axis=1)
            kurtosis_mask = kurtosis > kurtosis_thr
            if np.sum(kurtosis_mask) >= n_components:
                order = np.argsort(kurtosis)[::-1]
                ica_maps = ica_maps[order[:n_components]]
                break
            n_components += 1

            del group_maps
        else:
            raise ValueError('Could not find components with high-enough'
                             ' kurtosis')
        self.n_components_ = n_components
        return ica_maps

    def fit(self, data, y=None):

        MultiPCA.fit(self, data)

        self.memory = Memory(cachedir='nisl_cache')
        ica_maps = self._find_high_kurtosis(self.components_.T, self.memory)

        self.maps_ = ica_maps
        if not self.maps_only:
            # Relearn the time series
            self.learn_from_maps(data)
        return self

    def transform(self, X, y=None):
        """Apply un-mixing matrix "W" to X to recover the sources

            S = X * W.T
        """
        return np.dot(X, self.maps_.T)
