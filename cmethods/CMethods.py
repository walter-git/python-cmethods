#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2023 Benjamin Thomas Schwertfeger
# Github: https://github.com/btschwertfeger
#

r"""
    Module to apply different bias correction techniques to time-series climate data

    T = Temperatures ($T$)
    X = Some climate variable ($X$)
    h = historical
    p = scenario; future; predicted
    obs = observed data ($T_{obs,h}$)
    simh = modeled data with same time period as obs ($T_{sim,h}$)
    simp = data to correct (predicted simulated data) ($T_{sim,p}$)
    F = Cumulative Distribution Function
    \mu = mean
    \sigma = standard deviation
    i = index
    _{m} = long-term monthly interval
"""
import multiprocessing
from typing import List, Union

import numpy as np
import xarray as xr
from tqdm import tqdm

__author__ = "Benjamin Thomas Schwertfeger"
__copyright__ = __author__
__email__ = "development@b-schwertfeger.de"
__link__ = "https://b-schwertfeger.de"
__github__ = "https://github.com/btschwertfeger/python-cmethods"


class UnknownMethodError(Exception):
    """
    Exception raised for errors if unknown method called in CMethods class.
    """

    def __init__(self, method: str, available_methods: list):
        super().__init__(
            f'Unknown method "{method}"! Available methods: {available_methods}'
        )


class CMethods:
    """
    The CMethods class serves a collection of bias correction procedures to adjust
    time-series of climate data. It accept no parameters but must be instantiated
    to apply the bias correction techniques.

    The following bias correction techniques are available:
        Scaling-based techniques:
            * Linear Scaling :func:`cmethods.CMethods.CMethods.linear_scaling`
            * Vairance Scaling :func:`cmethods.CMethods.CMethods.variance_scaling`
            * Delta (change) Method :func:`cmethods.CMethods.CMethods.delta_method`

        Distribution-based techniques:
            * Quantile Mapping :func:`cmethods.CMethods.CMethods.quantile_mapping`
            * Quantile Delta Mapping :func:`cmethods.CMethods.CMethods.quantile_delta_mapping`

    Except for the Variance Scaling all methods can be applied on both, interval- and ratio- based
    variables. The Variance Scaling can only be applied on interval-based variables.
    """

    SCALING_METHODS = ["linear_scaling", "variance_scaling", "delta_method"]
    DISTRIBUTION_METHODS = ["quantile_mapping", "quantile_delta_mapping"]

    CUSTOM_METHODS = SCALING_METHODS + DISTRIBUTION_METHODS
    METHODS = CUSTOM_METHODS

    ADDITIVE = ["+", "add"]
    MULTIPLICATIVE = ["*", "mult"]

    MAX_SCALING_FACTOR = 10

    def __init__(self):
        pass

    @classmethod
    def get_available_methods(cls) -> list:
        """
        Function to return the available adjustment methods of the CMethods class.

        :return: List of available bias correction methods
        :rtype: List[str]

        .. code-block:: python
            :linenos:
            :caption: Example: Get available methods

            >>> from cmethods.CMethods import CMethods
            >>> CMethods().get_available_methods()
            [
                "linear_scaling", "variance_scaling", "delta_method",
                "quantile_mapping", "quantile_delta_mapping"
            ]
        """
        return cls.METHODS

    @classmethod
    def get_function(cls, method: str):
        """
        Returns the bias correction function corresponding to the ``method`` name.

        :param method: The method name to get the function for
        :type method: str
        :raises UnknownMethodError: If the function is not implemented
        :return: The function of the corresponding method
        :rtype: function
        """
        if method == "linear_scaling":
            return cls.linear_scaling
        if method == "variance_scaling":
            return cls.variance_scaling
        if method == "delta_method":
            return cls.delta_method
        if method == "quantile_mapping":
            return cls.quantile_mapping
        if method == "empirical_quantile_mapping":
            return cls.empirical_quantile_mapping
        if method == "quantile_delta_mapping":
            return cls.quantile_delta_mapping
        raise UnknownMethodError(method, cls.METHODS)

    @classmethod
    def adjust_3d(
        cls,
        method: str,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        n_quantiles: int = 100,
        kind: str = "+",
        group: Union[str, None] = None,
        n_jobs: int = 1,
        **kwargs,
    ) -> xr.core.dataarray.Dataset:
        """
        Function to apply a bias correction method on 3-dimensional climate data.

        :param method: The bias correction method to use
        :type method: str
        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param n_quantiles: Number of quantiles to respect. Only applies to
            distribution-based bias correction techniques, defaults to 100
        :type n_quantiles: int, optional
        :param kind: The kind of adjustment - additive or multiplicative, defaults to "+"
        :type kind: str, optional
        :param group: The grouping base, Only applies to scaling-based techniques, defaults to None
        :type group: Union[str, None], optional
        :param n_jobs: Number of parallels jobs to run the correction, defaults to 1
        :type n_jobs: int, optional
        :raises UnknownMethodError: If the correction method is not implemented
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.Dataset

        .. code-block:: python
            :linenos:
            :caption: Example application - 3-dimensinoal bias correction

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimensions "time", "lat", and "lon"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()

            '''
            In the following the Quantile Delta Mapping techniques is applied on
            3-dimensional time-series data sets containing the variable "tas". The
            parameter "kind" is not specified, since the additive ("+") kind is the default.
            When adjusting ratio-based variables like precipitation, the multiplicative
            variant ("*") should be used. In addition "n_jobs" is set to 4 which means that
            four processes are used. This can improve the overall execution time.

            After the execution, "qdm_adjusted" contains the fully bias-corrected
            data - with the same shape, resolution, dimensions, coordinates and
            attributes.
            '''
            >>> qdm_adjusted = cm.adjust_3d(
            ...     method = "quantile_delta_mapping",
            ...     obs = obs[variable],
            ...     simh = simh[variable],
            ...     simp = simp[variable],
            ...     n_quantiles = 250,
            ...     n_jobs = 4
            ... )

            '''
            The next exampke shows how to apply the Linear Scaling bias correction
            techqnique based on long-term monthly means.
            '''
            >>> ls_adjusted = cm.adjust_3d(
            ...     method="linear_scaling",
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ...     group="time.month",
            ...     kind="+"
            ... )
        """
        obs = obs.transpose("lat", "lon", "time")
        simh = simh.transpose("lat", "lon", "time")
        simp = simp.transpose("lat", "lon", "time").load()

        result = simp.copy(deep=True)
        len_lat, len_lon = len(simp.lat), len(simp.lon)

        if method in cls.CUSTOM_METHODS:
            if n_jobs == 1:
                method = cls.get_function(method)
                for lat in tqdm(range(len_lat)):
                    for lon in range(len_lon):
                        result[lat, lon] = method(
                            obs=obs[lat, lon],
                            simh=simh[lat, lon],
                            simp=simp[lat, lon],
                            group=group,
                            kind=kind,
                            n_quantiles=n_quantiles,
                            **kwargs,
                        )
            else:
                try:
                    pool = multiprocessing.Pool(processes=n_jobs)
                    # with multiprocessing.Pool(processes=n_jobs) as pool:
                    # conntext manager is not used because than the coverage does not work.
                    # this may change when upgrading to only support Python 3.11+
                    params: List[dict] = [
                        {
                            "method": method,
                            "obs": obs[lat],
                            "simh": simh[lat],
                            "simp": simp[lat],
                            "group": group,
                            "kind": kind,
                            "n_quaniles": n_quantiles,
                            "kwargs": kwargs,
                        }
                        for lat in range(len_lat)
                    ]
                    for lat, corrected in enumerate(pool.map(cls.pool_adjust, params)):
                        result[lat] = corrected
                finally:
                    pool.close()
                    pool.join()

            return result.transpose("time", "lat", "lon")
        raise UnknownMethodError(method, cls.METHODS)

    @classmethod
    def pool_adjust(cls, params: dict) -> np.array:
        """
        Adjustment along the longitudes for one specific latitude
        used by :func:`cmethods.CMethods.CMethods.adjust_3d`
        as callback function for :class:`multiprocessing.Pool`.

        **Not intended to be executed somwhere else.**

        :params params: The method specific parameters
        :type params: dict
        :raises UnknownMethodError: If the specified method is not implemented
        :return: The bias-corrected time series as 2-dimensional (longitudes x time)
            numpy array
        :rtype: np.array
        """
        kwargs = params.get("kwargs", {})

        result = params["simp"].copy(deep=True).load()
        len_lon = len(params["obs"].lon)

        func_adjustment = None
        if params["method"] in cls.CUSTOM_METHODS:
            func_adjustment = cls.get_function(params["method"])
            kwargs["n_quantiles"] = params.get("n_quantiles", 100)
            kwargs["kind"] = params.get("kind", "+")
            for lon in range(len_lon):
                result[lon] = func_adjustment(
                    obs=params["obs"][lon],
                    simh=params["simh"][lon],
                    simp=params["simp"][lon],
                    group=params.get("group", None),
                    **kwargs,
                )
            return np.array(result)

        raise UnknownMethodError(params["method"], cls.METHODS)

    @classmethod
    def grouped_correction(
        cls,
        method: str,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        group: str,
        kind: str = "+",
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        """Method to adjust 1 dimensional climate data while respecting adjustment groups.

        ----- P A R A M E T E R S -----
            method (str): adjustment method name
            obs (xarray.core.dataarray.DataArray): observed / obserence Data
            simh (xarray.core.dataarray.DataArray): simulated historical Data
            simp (xarray.core.dataarray.DataArray): future simulated Data
            method (str): Scaling method (e.g.: 'linear_scaling')
            group (str): [optional]  Group / Period (either: 'time.month', 'time.year' or 'time.dayofyear')

        ----- R E T U R N -----

            xarray.core.dataarray.DataArray: Adjusted data

        """

        func_adjustment = cls.get_function(method)
        result = simp.copy(deep=True).load()
        groups = simh.groupby(group).groups

        for month in groups.keys():
            m_obs, m_simh, m_simp = [], [], []

            for i in groups[month]:
                m_obs.append(obs[i])
                m_simh.append(simh[i])
                m_simp.append(simp[i])

            computed_result = func_adjustment(
                obs=m_obs, simh=m_simh, simp=m_simp, kind=kind, group=None, **kwargs
            )
            for i, index in enumerate(groups[month]):
                result[index] = computed_result[i]

        return result

    # ? -----========= L I N E A R - S C A L I N G =========------
    @classmethod
    def linear_scaling(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        group: Union[str, None] = "time.month",
        kind: str = "+",
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        r"""
        The Linear Scaling bias correction technique can be applied on interval- and
        ratio-based climate variables to minimize deviations in the mean values
        between predicted and observed time-series of past and future time periods.

        Since the multiplicative scaling can result in very high scaling factors,
        a maximum scaling factor of 10 is set. This can be changed by passing
        another value to the optional `max_scaling_factor` argument.

        This method must be applied on a 1-dimensional data set i.e., there is only one
        time-series passed for each of ``obs``, ``simh``, and ``simp``.

        The Linear Scaling bias correction technique implemented here is based on the
        method described in the equations of Teutschbein, Claudia and Seibert, Jan (2012)
        *"Bias correction of regional climate model simulations for hydrological climate-change
        impact studies: Review and evaluation of different methods"*
        (https://doi.org/10.1016/j.jhydrol.2012.05.052). In the following the equations
        for both additive and multiplicative Linear Scaling are shown:

        **Additive**:

            In Linear Scaling, the long-term monthly mean (:math:`\mu_m`) of the modeled data :math:`T_{sim,h}` is subtracted
            from the long-term monthly mean of the reference data :math:`T_{obs,h}` at time step :math:`i`.
            This difference in month-dependent long-term mean is than added to the long-term monthly mean for time step :math:`i`,
            in the time-series that is to be adjusted (:math:`T_{sim,p}`).

            .. math::

                X^{*LS}_{sim,p}(i) = X_{sim,p}(i) + \mu_{m}(X_{obs,h}(i)) - \mu_{m}(X_{sim,h}(i))


        **Multiplicative**:

            The multiplicative Linear Scaling differs from the additive variant in such way, that the changes are not computed
            in absolute but in relative values.

            .. math::

                X^{*LS}_{sim,h}(i) = X_{sim,h}(i) \cdot \left[\frac{\mu_{m}(X_{obs,h}(i))}{\mu_{m}(X_{sim,h}(i))}\right]


        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param group: The grouping defines the basis of the mean, defaults to ``time.month``
        :type group: Union[str, None], optional
        :param kind: The kind of the correction, additive for interval- and multiplicative
            for ratio-based variables, defaults to ``+``
        :type kind: str, optional
        :raises NotImplementedError: If the kind is not in (``+``, ``*``, ``add``, ``mult``)
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray

        .. code-block:: python
            :linenos:
            :caption: Example: Linear Scaling

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimension "time"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()
            >>> ls_adjusted = cm.linear_scaling(
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ...     kind="+"
            ... )
        """
        if group is not None:
            return cls.grouped_correction(
                method="linear_scaling",
                obs=obs,
                simh=simh,
                simp=simp,
                group=group,
                kind=kind,
                **kwargs,
            )
        if kind in cls.ADDITIVE:
            return np.array(simp) + (np.nanmean(obs) - np.nanmean(simh))  # Eq. 1
        if kind in cls.MULTIPLICATIVE:
            adj_scaling_factor = cls.get_adjusted_scaling_factor(
                np.nanmean(obs) / np.nanmean(simh),
                kwargs.get("max_scaling_factor", cls.MAX_SCALING_FACTOR),
            )
            return np.array(simp) * adj_scaling_factor  # Eq. 2
        raise NotImplementedError(
            f"{kind} not available for linear_scaling. Use '+' or '*' instead."
        )

    # ? -----========= V A R I A N C E - S C A L I N G =========------
    @classmethod
    def variance_scaling(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        group: Union[str, None] = "time.month",
        kind: str = "+",
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        r"""
        The Variance Scaling bias correction technique can be applied on interval-based
        climate variables to minimize deviations in the mean and variance
        between predicted and observed time-series of past and future time periods.

        This method must be applied on a 1-dimensional data set i.e., there is only one
        time-series passed for each of ``obs``, ``simh``, and ``simp``.

        The Variance Scaling bias correction technique implemented here is based on the
        method described in the equations of Teutschbein, Claudia and Seibert, Jan (2012)
        *"Bias correction of regional climate model simulations for hydrological climate-change
        impact studies: Review and evaluation of different methods"*
        (https://doi.org/10.1016/j.jhydrol.2012.05.052). In the following the equations
        of the Variance Scaling approach are shown:

        **(1)** First, the modeled data of the control and scenario period must be bias-corrected using
        the Linear Scaling technique. This corrects the deviation in the mean.

        .. math::

            X^{*LS}_{sim,h}(i) = X_{sim,h}(i) + \mu_{m}(X_{obs,h}(i)) - \mu_{m}(X_{sim,h}(i))

            X^{*LS}_{sim,p}(i) = X_{sim,p}(i) + \mu_{m}(X_{obs,h}(i)) - \mu_{m}(X_{sim,h}(i))


        **(2)** In the second step, the time-series are shifted to a zero mean. This enables the adjustment
        of the standard deviation in the following step.

        .. math::

            X^{VS(1)}_{sim,h}(i) = X^{*LS}_{sim,h}(i) - \mu_{m}(X^{*LS}_{sim,h}(i))

            X^{VS(1)}_{sim,p}(i) = X^{*LS}_{sim,p}(i) - \mu_{m}(X^{*LS}_{sim,p}(i))


        **(3)** Now the standard deviation (so variance too) can be scaled.

        .. math::

            X^{VS(2)}_{sim,p}(i) = X^{VS(1)}_{sim,p}(i) \cdot \left[\frac{\sigma_{m}(X_{obs,h}(i))}{\sigma_{m}(X^{VS(1)}_{sim,h}(i))}\right]


        **(4)** Finally the prevously removed mean is shifted back

        .. math::

            X^{*VS}_{sim,p}(i) = X^{VS(2)}_{sim,p}(i) + \mu_{m}(X^{*LS}_{sim,p}(i))


        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param group: The grouping defines the basis of the mean, defaults to ``time.month``
        :type group: Union[str, None], optional
        :param kind: The kind of the correction, additive for interval-based variables,
            no other kind is available so far, defaults to ``+``
        :type kind: str, optional
        :raises NotImplementedError: If the kind is not in (``+``, ``add``)
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray

        .. code-block:: python
            :linenos:
            :caption: Example: Variance Scaling

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimension "time"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()
            >>> vs_adjusted = cm.variance_scaling(
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ... )
        """
        if group is not None:
            return cls.grouped_correction(
                method="variance_scaling",
                obs=obs,
                simh=simh,
                simp=simp,
                group=group,
                kind=kind,
                **kwargs,
            )
        if kind in cls.ADDITIVE:
            LS_simh = cls.linear_scaling(obs, simh, simh, group=None)  # Eq. 1
            LS_simp = cls.linear_scaling(obs, simh, simp, group=None)  # Eq. 2

            VS_1_simh = LS_simh - np.nanmean(LS_simh)  # Eq. 3
            VS_1_simp = LS_simp - np.nanmean(LS_simp)  # Eq. 4

            adj_scaling_factor = cls.get_adjusted_scaling_factor(
                np.std(obs) / np.std(VS_1_simh),
                kwargs.get("max_scaling_factor", cls.MAX_SCALING_FACTOR),
            )

            VS_2_simp = VS_1_simp * adj_scaling_factor  # Eq. 5
            return VS_2_simp + np.nanmean(LS_simp)  # Eq. 6

        raise NotImplementedError(
            f"{kind} not available for variance_scaling. Use '+' instead."
        )

    # ? -----========= D E L T A - M E T H O D =========------
    @classmethod
    def delta_method(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        group: Union[str, None] = "time.month",
        kind: str = "+",
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        r"""
        The Delta Method bias correction technique can be applied on interval- and
        ratio-based climate variables to minimize deviations in the mean values
        between predicted and observed time-series of past and future time periods.

        Since the multiplicative scaling can result in very high scaling factors,
        a maximum scaling factor of 10 is set. This can be changed by passing
        another value to the optional `max_scaling_factor` argument.

        This method must be applied on a 1-dimensional data set i.e., there is only one
        time-series passed for each of ``obs``, ``simh``, and ``simp``.

        The Delta Method bias correction technique implemented here is based on the
        method described in the equations of Beyer, R. and Krapp, M. and Manica, A. (2020)
        *"An empirical evaluation of bias correction methods for palaeoclimate simulations"*
        (https://doi.org/10.5194/cp-16-1493-2020). In the following the equations
        for both additive and multiplicative Delta Method are shown:

        **Additive**:

            The Delta Method looks like the Linear Scaling method but the important difference is, that the Delta method
            uses the change between the modeled data instead of the difference between the modeled and reference data of the control
            period. This means that the long-term monthly mean (:math:`\mu_m`) of the modeled data of the control period :math:`T_{sim,h}`
            is subtracted from the long-term monthly mean of the modeled data from the scenario period :math:`T_{sim,p}` at time step :math:`i`.
            This change in month-dependent long-term mean is than added to the long-term monthly mean for time step :math:`i`,
            in the time-series that represents the reference data of the control period (:math:`T_{obs,h}`).

            .. math::

                X^{*DM}_{sim,p}(i) = X_{obs,h}(i) + \mu_{m}(X_{sim,p}(i)) - \mu_{m}(X_{sim,h}(i))


        **Multiplicative**:

            The multiplicative variant behaves like the additive, but with the difference that the change is computed using the relative change
            instead of the absolute change.

            .. math::

                X^{*DM}_{sim,p}(i) = X_{obs,h}(i) \cdot \left[\frac{ \mu_{m}(X_{sim,p}(i)) }{ \mu_{m}(X_{sim,h}(i))}\right]


        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param group: The grouping defines the basis of the mean, defaults to ``time.month``
        :type group: Union[str, None], optional
        :param kind: The kind of the correction, additive for interval- and multiplicative
            for ratio-based variables, defaults to ``+``
        :type kind: str, optional
        :raises NotImplementedError: If the kind is not in (``+``, ``*``, ``add``, ``mult``)
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray

        .. code-block:: python
            :linenos:
            :caption: Example: Delta Method

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimension "time"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()
            >>> dm_adjusted = cm.delta_method(
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ... )
        """
        if group is not None:
            return cls.grouped_correction(
                method="delta_method",
                obs=obs,
                simh=simh,
                simp=simp,
                group=group,
                kind=kind,
                **kwargs,
            )
        if kind in cls.ADDITIVE:
            return np.array(obs) + (np.nanmean(simp) - np.nanmean(simh))  # Eq. 1
        if kind in cls.MULTIPLICATIVE:
            adj_scaling_factor = cls.get_adjusted_scaling_factor(
                np.nanmean(simp) / np.nanmean(simh),
                kwargs.get("max_scaling_factor", cls.MAX_SCALING_FACTOR),
            )
            return np.array(obs) * adj_scaling_factor  # Eq. 2
        raise NotImplementedError(
            f"{kind} not available for delta_method. Use '+' or '*' instead."
        )

    # ? -----========= Q U A N T I L E - M A P P I N G =========------
    @classmethod
    def quantile_mapping(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        n_quantiles: int,
        kind: str = "+",
        detrended: bool = False,
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        r"""
        The Quantile Mapping bias correction technique can be used to minimize distributional
        biases between modeled and observed time-series climate data. Its interval-independant
        behaviour ensures that the whole time series is taken into account to redistribute
        its values, based on the distributions of the modeled and observed/reference data of the
        control period.

        This method must be applied on a 1-dimensional data set i.e., there is only one
        time-series passed for each of ``obs``, ``simh``, and ``simp``.

        The Quantile Mapping technique implemented here is based on the equations of
        Alex J. Cannon and Stephen R. Sobie and Trevor Q. Murdock (2015) *"Bias Correction of GCM
        Precipitation by Quantile Mapping: How Well Do Methods Preserve Changes in Quantiles
        and Extremes?"* (https://doi.org/10.1175/JCLI-D-14-00754.1).

        Since the regular Quantile Mapping is bounded to the value range of the modeled data of
        the control period, the *Detrended* Quantile Mapping approach can be used by setting the
        ``detrended`` argument to ``True``. Detrending means, that the values of :math:`X_{sim,p}`
        are shifted to the value range of :math:`X_{sim,h}` before the Quantile Mapping is applied.
        After the Quantile Mapping was applied, the mean is shifted back. Since it does not make sens
        to take the whole mean to rescale the data, the month-dependent long-term mean is used.

        In the following the equations of Alex J. Cannon (2015) are shown (without detrending):

        **Additive**:

            .. math::

                X^{*QM}_{sim,p}(i) = F^{-1}_{obs,h} \left\{F_{sim,h}\left[X_{sim,p}(i)\right]\right\}

        **Multiplicative**:

            .. math::

                X^{*QM}_{sim,p}(i) = F^{-1}_{obs,h}\Biggl\{F_{sim,h}\left[\frac{\mu{X_{sim,h}} \cdot \mu{X_{sim,p}(i)}}{\mu{X_{sim,p}(i)}}\right]\Biggr\}\frac{\mu{X_{sim,p}(i)}}{\mu{X_{sim,h}}}


        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param n_quantiles: Number of quantiles to respect/use
        :type n_quantiles: int
        :param kind: The kind of the correction, additive for interval- and multiplicative
            for ratio-based variables, defaults to ``+``
        :type kind: str, optional
        :param detrended: If the extremes should be respected by applying month-dependent
            detrending before and after applying the Quantile Mapping
        :type detrended: bool, optional
        :raises NotImplementedError: If the kind is not in (``+``, ``*``, ``add``, ``mult``)
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray

        .. code-block:: python
            :linenos:
            :caption: Example: Quantile Mapping

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimension "time"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()
            >>> qm_adjusted = cm.quantile_mapping(
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ...     n_quantiles=250
            ... )
        """
        res = simp.copy(deep=True)
        obs, simh, simp = np.array(obs), np.array(simh), np.array(simp)

        global_max = max(np.amax(obs), np.amax(simh))
        global_min = min(np.amin(obs), np.amin(simh))
        wide = abs(global_max - global_min) / n_quantiles
        xbins = np.arange(global_min, global_max + wide, wide)

        cdf_obs = cls.get_cdf(obs, xbins)
        cdf_simh = cls.get_cdf(simh, xbins)

        if detrended:
            # detrended => shift mean of $X_{sim,p}$ to range of $X_{sim,h}$ to adjust extremes
            for _, idxs in res.groupby("time.month").groups.items():
                m_simh, m_simp = [], []
                for idx in idxs:
                    m_simh.append(simh[idx])
                    m_simp.append(simp[idx])

                m_simh = np.array(m_simh)
                m_simp = np.array(m_simp)
                m_simh_mean = np.nanmean(m_simh)
                m_simp_mean = np.nanmean(m_simp)

                if kind in cls.ADDITIVE:
                    epsilon = np.interp(
                        m_simp - m_simp_mean + m_simh_mean, xbins, cdf_simh
                    )  # Eq. 1
                    X = (
                        cls.get_inverse_of_cdf(cdf_obs, epsilon, xbins)
                        + m_simp_mean
                        - m_simh_mean
                    )  # Eq. 1

                elif kind in cls.MULTIPLICATIVE:
                    epsilon = np.interp(  # Eq. 2
                        (m_simh_mean * m_simp) / m_simp_mean,
                        xbins,
                        cdf_simh,
                        left=kwargs.get("val_min", 0.0),
                        right=kwargs.get("val_max", None),
                    )
                    X = np.interp(epsilon, cdf_obs, xbins) * (
                        m_simp_mean / m_simh_mean
                    )  # Eq. 2
                for i, idx in enumerate(idxs):
                    res.values[idx] = X[i]
            return res

        if kind in cls.ADDITIVE:
            epsilon = np.interp(simp, xbins, cdf_simh)  # Eq. 1
            res.values = cls.get_inverse_of_cdf(cdf_obs, epsilon, xbins)  # Eq. 1
            return res

        if kind in cls.MULTIPLICATIVE:
            epsilon = np.interp(  # Eq. 2
                simp,
                xbins,
                cdf_simh,
                left=kwargs.get("val_min", 0.0),
                right=kwargs.get("val_max", None),
            )
            res.values = cls.get_inverse_of_cdf(cdf_obs, epsilon, xbins)  # Eq. 2
            return res

        raise NotImplementedError(
            f"{kind} for quantile_mapping is not available. Use '+' or '*' instead."
        )

    # ? -----========= E M P I R I C A L - Q U A N T I L E - M A P P I N G =========------
    @classmethod
    def empirical_quantile_mapping(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        n_quantiles: int = 100,
        extrapolate: Union[str, None] = None,
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        """
        Method to adjust 1-dimensional climate data by empirical quantile mapping

        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param n_quantiles: Number of quantiles to respect/use, defaults to ``100``
        :type n_quantiles: int, optional
        :type kind: str, optional
        :param extrapolate: Bounded range or extrapolate, defaults to ``None``
        :type extrapolate: Union[str, None], optional
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray
        :raises NotImplementedError: This method is not implemented
        """
        raise NotImplementedError(
            "Not implemented; please have a look at: https://svn.oss.deltares.nl/repos/openearthtools/trunk/python/applications/hydrotools/hydrotools/statistics/bias_correction.py "
        )

    # ? -----========= Q U A N T I L E - D E L T A - M A P P I N G =========------
    @classmethod
    def quantile_delta_mapping(
        cls,
        obs: xr.core.dataarray.DataArray,
        simh: xr.core.dataarray.DataArray,
        simp: xr.core.dataarray.DataArray,
        n_quantiles: int,
        kind: str = "+",
        **kwargs,
    ) -> xr.core.dataarray.DataArray:
        r"""
        The Quantile Delta Mapping bias correction technique can be used to minimize distributional
        biases between modeled and observed time-series climate data. Its interval-independant
        behaviour ensures that the whole time series is taken into account to redistribute
        its values, based on the distributions of the modeled and observed/reference data of the
        control period. In contrast to the regular Quantile Mapping (:func:`cmethods.CMethods.CMethods.quantile_mapping`)
        the Quantile Delta Mapping also takes the change between the modeled data of the control and scenario
        period into account.

        This method must be applied on a 1-dimensional data set i.e., there is only one
        time-series passed for each of ``obs``, ``simh``, and ``simp``.

        The Quantile Delta Mapping technique implemented here is based on the equations of
        Tong, Y., Gao, X., Han, Z. et al. (2021) *"Bias correction of temperature and precipitation
        over China for RCM simulations using the QM and QDM methods"*. Clim Dyn 57, 1425–1443
        (https://doi.org/10.1007/s00382-020-05447-4). In the following the additive and multiplicative
        variant are shown.

        **Additive**:

            **(1.1)** In the first step the quantile value of the time step :math:`i` to adjust is stored in
            :math:`\varepsilon(i)`.

            .. math::

                \varepsilon(i) = F_{sim,p}\left[X_{sim,p}(i)\right], \hspace{1em} \varepsilon(i)\in\{0,1\}


            **(1.2)** The bias corrected value at time step :math:`i` is now determined by inserting the
            quantile value into the inverse cummulative distribution function of the reference data of the control
            period. This results in a bias corrected value for time step :math:`i` but still without taking the
            change in modeled data into account.

            .. math::

                X^{QDM(1)}_{sim,p}(i) = F^{-1}_{obs,h}\left[\varepsilon(i)\right]


            **(1.3)** The :math:`\Delta(i)` represents the absolute change in quantiles between the modeled value
            in the control and scenario period.

            .. math::

                 \Delta(i) & = F^{-1}_{sim,p}\left[\varepsilon(i)\right] - F^{-1}_{sim,h}\left[\varepsilon(i)\right] \\[1pt]
                           & = X_{sim,p}(i) - F^{-1}_{sim,h}\left\{F^{}_{sim,p}\left[X_{sim,p}(i)\right]\right\}


            **(1.4)** Finally the previously calculated change can be added to the bias-corrected value.

            .. math::

                X^{*QDM}_{sim,p}(i) = X^{QDM(1)}_{sim,p}(i) + \Delta(i)


        **Multiplicative**:

            The first two steps of the multiplicative Quantile Delta Mapping bias correction technique are the
            same as for the additive variant.

            **(2.3)** The :math:`\Delta(i)` in the multiplicative Quantile Delta Mapping is calulated like the
            additive variant, but using the relative than the absolute change.

                .. math::

                    \Delta(i) & = \frac{ F^{-1}_{sim,p}\left[\varepsilon(i)\right] }{ F^{-1}_{sim,h}\left[\varepsilon(i)\right] } \\[1pt]
                              & = \frac{ X_{sim,p}(i) }{ F^{-1}_{sim,h}\left\{F^{}_{sim,p}\left[X_{sim,p}(i)\right]\right\} }


            **(2.4)** The relative change between the modeled data of the control and scenario period is than
            multiplicated with the bias-corrected value (see **1.2**).

                .. math::

                    X^{*QDM}_{sim,p}(i) = X^{QDM(1)}_{sim,p}(i) \cdot \Delta(i)


        :param obs: The reference data set of the control period
            (in most cases the observational data)
        :type obs: xr.core.dataarray.DataArray
        :param simh: The modeled data of the control period
        :type simh: xr.core.dataarray.DataArray
        :param simp: The modeled data of the scenario period (this is the data set
            on which the bias correction takes action)
        :type simp: xr.core.dataarray.DataArray
        :param n_quantiles: Number of quantiles to respect/use
        :type n_quantiles: int
        :param kind: The kind of the correction, additive for interval- and multiplicative
            for ratio-based variables, defaults to ``+``
        :type kind: str, optional
        :raises NotImplementedError: If the kind is not in (``+``, ``*``, ``add``, ``mult``)
        :return: The bias-corrected time series
        :rtype: xr.core.dataarray.DataArray

        .. code-block:: python
            :linenos:
            :caption: Example: Quantile Delta Mapping

            >>> import xarray as xr
            >>> from cmethods.CMethods import CMethods

            >>> # Note: The data sets must contain the dimension "time"
            >>> #       for the respective variable.
            >>> obsh = xr.open_dataset("path/to/reference_data-control_period.nc")
            >>> simh = xr.open_dataset("path/to/modeled_data-control_period.nc")
            >>> simp = xr.open_dataset("path/to/the_dataset_to_adjust-scenario_period.nc")
            >>> variable = "tas" # temperatures

            >>> cm = CMethods()
            >>> qdm_adjusted = cm.quantile_delta_mapping(
            ...     obs=obs[variable],
            ...     simh=simh[variable],
            ...     simp=simp[variable],
            ...     n_quantiles=250
            ... )
        """
        if kind in cls.ADDITIVE:
            res = simp.copy(deep=True)
            obs, simh, simp = (
                np.array(obs),
                np.array(simh),
                np.array(simp),
            )  # to achieve higher accuracy
            global_max = kwargs.get("global_max", max(np.amax(obs), np.amax(simh)))
            global_min = kwargs.get("global_min", min(np.amin(obs), np.amin(simh)))
            wide = abs(global_max - global_min) / n_quantiles
            xbins = np.arange(global_min, global_max + wide, wide)

            cdf_obs = cls.get_cdf(obs, xbins)
            cdf_simh = cls.get_cdf(simh, xbins)
            cdf_simp = cls.get_cdf(simp, xbins)

            # calculate exact cdf values of $F_{sim,p}[T_{sim,p}(t)]$
            epsilon = np.interp(simp, xbins, cdf_simp)  # Eq. 1.1
            QDM1 = cls.get_inverse_of_cdf(cdf_obs, epsilon, xbins)  # Eq. 1.2
            delta = simp - cls.get_inverse_of_cdf(cdf_simh, epsilon, xbins)  # Eq. 1.3
            res.values = QDM1 + delta  # Eq. 1.4
            return res

        if kind in cls.MULTIPLICATIVE:
            res = simp.copy(deep=True)
            obs, simh, simp = np.array(obs), np.array(simh), np.array(simp)
            global_max = kwargs.get("global_max", max(np.amax(obs), np.amax(simh)))
            wide = global_max / n_quantiles
            xbins = np.arange(kwargs.get("global_min", 0.0), global_max + wide, wide)

            cdf_obs = cls.get_cdf(obs, xbins)
            cdf_simh = cls.get_cdf(simh, xbins)
            cdf_simp = cls.get_cdf(simp, xbins)

            epsilon = np.interp(simp, xbins, cdf_simp)  # Eq. 1.1
            QDM1 = cls.get_inverse_of_cdf(cdf_obs, epsilon, xbins)  # Eq. 1.2

            with np.errstate(divide="ignore", invalid="ignore"):
                delta = simp / cls.get_inverse_of_cdf(
                    cdf_simh, epsilon, xbins
                )  # Eq. 2.3
            delta[np.isnan(delta)] = 0

            res.values = QDM1 * delta  # Eq. 2.4
            return res
        raise NotImplementedError(
            f"{kind} not available for quantile_delta_mapping. Use '+' or '*' instead."
        )

    # * -----========= G E N E R A L  =========------
    @staticmethod
    def get_pdf(x: Union[list, np.array], xbins: Union[list, np.array]) -> np.array:
        r"""
        Compuites and returns the the probability density function :math:`P(x)`
        of ``x`` based on ``xbins``.

        :param x: The vector to get :math:`P(x)` from
        :type x: Union[list, np.array]
        :param xbins: The boundaries/bins of :math:`P(x)`
        :type xbins: Union[list, np.array]
        :return: The probability densitiy function of ``x``
        :rtype: np.array

        .. code-block:: python
            :linenos:
            :caption: Compute the probability density function :math:`P(x)`

            >>> from cmethods.CMethods import CMethods
            >>> cm = CMethods()
            >>> x = [1, 2, 3, 4, 5, 5, 5, 6, 7, 8, 9, 10]
            >>> xbins = [0, 3, 6, 10]
            >>> print(cm.get_pdf(x=x, xbins=xbins))
            [2, 5, 5]
        """
        pdf, _ = np.histogram(x, xbins)
        return pdf

    @staticmethod
    def get_cdf(x: Union[list, np.array], xbins: Union[list, np.array]) -> np.array:
        r"""
        Computes and returns returns the cumulative distribution function :math:`F(x)`
        of ``x`` based on ``xbins``.

        :param x: Vector to get :math:`F(x)` from
        :type x: Union[list, np.array]
        :param xbins: The boundaries/bins of :math:`F(x)`
        :type xbins: Union[list, np.array]
        :return: The cumulative distribution function of ``x``
        :rtype: np.array


        .. code-block:: python
            :linenos:
            :caption: Compute the cmmulative distribution function :math:`F(x)`

            >>> from cmethods.CMethods import CMethods
            >>> cm = CMethods()
            >>> x = [1, 2, 3, 4, 5, 5, 5, 6, 7, 8, 9, 10]
            >>> xbins = [0, 3, 6, 10]
            >>> print(cm.get_cdf(x=x, xbins=xbins))
            [0, 2, 7, 12]
        """
        pdf, _ = np.histogram(x, xbins)
        return np.insert(np.cumsum(pdf), 0, 0.0)

    @staticmethod
    def get_inverse_of_cdf(
        base_cdf: Union[list, np.array],
        insert_cdf: Union[list, np.array],
        xbins: Union[list, np.array],
    ) -> np.array:
        r"""
        Returns the inverse cumulative distribution function of with the following
        :math:`F^{-1}_{x}\left[y\right]` where :math:`x` represents ``base_cdf`` and
        ``insert_cdf`` is represented by :math:`y`.

        :param base_cdf: The basis
        :type base_cdf: Union[list, np.array]
        :param insert_cdf: The CDF that gets inserted
        :type insert_cdf: Union[list, np.array]
        :param xbins: Probability boundaries
        :type xbins: Union[list, np.array]
        :return: The inverse CDF
        :rtype: np.array
        """
        return np.interp(insert_cdf, base_cdf, xbins)

    @staticmethod
    def get_adjusted_scaling_factor(
        factor: Union[int, float], max_scaling_factor: Union[int, float]
    ) -> float:
        r"""
        Returns:
            - :math:`x` if :math:`-|y| \le x \le |y|`,
            - :math:`|y|` if :math:`x > |y|`, or
            - :math:`-|y|` if :math:`x < -|y|`

            where:
                - :math:`x` is ``factor``
                - :math:`y` is ``max_scaling_factor``.

        :param factor: The value to check for
        :type factor: Union[int, float]
        :param max_scaling_factor: The maximum/minimum allowed value
        :type max_scaling_factor: Union[int, float]
        :return: The correct value
        :rtype: float
        """
        if factor > 0 and factor > abs(max_scaling_factor):
            return abs(max_scaling_factor)
        if factor < 0 and factor < -abs(max_scaling_factor):
            return -abs(max_scaling_factor)
        return factor
