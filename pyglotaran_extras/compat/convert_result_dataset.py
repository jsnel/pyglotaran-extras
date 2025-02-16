"""Convert a new pyglotaran (result) dataset to a version compatible with pyglotaran-extras."""

from __future__ import annotations

import xarray as xr
from glotaran.project.result import Result

from pyglotaran_extras.compat.compat_result import CompatResult


def _adjust_fitted_data(ds: xr.Dataset, *, cleanup: bool = False) -> None:
    """Rename fit to fitted_data."""
    if "fit" in ds.data_vars:
        ds["fitted_data"] = ds["fit"]
        if cleanup:
            ds = ds.drop_vars("fit")


def _adjust_concentrations(ds: xr.Dataset, *, cleanup: bool = False) -> None:
    """Adjust the concentrations to spectra names."""
    # Check for species associated concentration variables
    for var in ds.data_vars:
        if "species_associated_concentration" in var or "species_concentration" in var:
            full_var_name = var  # Capture the full variable name
            ds["species_concentration"] = ds[full_var_name]
            if cleanup:
                ds = ds.drop_vars(full_var_name)


def _adjust_estimations_to_spectra(ds: xr.Dataset, *, cleanup: bool = False) -> None:
    """Adjust the estimations to spectra names and flatten data."""
    # Check for kinetic associated estimation variables
    for var in ds.data_vars:
        if "kinetic_associated_estimation" in var or "kinetic_associated_amplitude" in var:
            # Extract the data
            data = ds[var].to_numpy()
            # Reshape the data to match the desired shape
            for activation_id in range(data.shape[0]):
                reshaped_data = data[activation_id, :, :]
                # Update the dataset with the reshaped data
                ds[f"decay_associated_spectra_mc{activation_id+1}"] = (
                    ("spectral", f"component_mc{activation_id+1}"),
                    reshaped_data,
                )
            if cleanup:
                # Remove the original variable after adjustment
                ds = ds.drop_vars(var)

    # Check for species associated estimation variables
    for var in ds.data_vars:
        if "species_associated_estimation" in var or "species_associated_amplitude" in var:
            full_var_name = var  # Capture the full variable name
            ds["species_associated_spectra"] = ds[full_var_name]
            if cleanup:
                ds = ds.drop_vars(full_var_name)

    # Check for damped oscillation associated estimation variables
    for var in ds.data_vars:
        if (
            "damped_oscillation_associated_estimation" in var
            or "damped_oscillation_associated_amplitude" in var
        ):
            full_var_name = var  # Capture the full variable name
            ds["damped_oscillation_associated_spectra"] = ds[full_var_name]
            if cleanup:
                ds = ds.drop_vars(full_var_name)


def _adjust_activation_to_irf(ds: xr.Dataset, *, cleanup: bool = False) -> None:
    """Adjust the activation to the corresponding IRF."""
    if "gaussian_activation_center" in ds:
        values = ds.gaussian_activation_center.to_numpy().flatten()
        ds["irf_center"] = values[0]
        if cleanup:
            # ds = ds.drop_vars("gaussian_activation_center")  # noqa: ERA001
            pass  # only cleanup if we have converted all irf aspects
    if "gaussian_activation_width" in ds:
        values = ds.gaussian_activation_width.to_numpy().flatten()
        ds["irf_width"] = values[0]
        if cleanup:
            # ds = ds.drop_vars("gaussian_activation_width")  # noqa: ERA001
            pass
    if "gaussian_activation_scale" in ds:
        values = ds.gaussian_activation_scale.to_numpy().flatten()
        ds["irf_scale"] = values[0]
        if cleanup:
            # ds = ds.drop_vars("gaussian_activation_scale")  # noqa: ERA001
            pass
    if "gaussian_activation_function" in ds:
        values = ds.gaussian_activation_function.to_numpy()
        ds["irf"] = xr.DataArray(
            values,
            coords={
                "irf_nr": ds["gaussian_activation"].to_numpy() - 1,
                "time": ds["time"].to_numpy(),
            },
        )
        if cleanup:
            # ds = ds.drop_vars("gaussian_activation_function")  # noqa: ERA001
            pass
    if "gaussian_activation_dispersion" in ds:
        values = ds.gaussian_activation_dispersion.to_numpy()[0]
        ds["irf_center_location"] = xr.DataArray(
            values,
            coords={
                "irf_nr": ds["gaussian_activation_part"].to_numpy(),
                "spectral": ds["spectral"].to_numpy(),
            },
        )
        if cleanup:
            # ds = ds.drop_vars("gaussian_activation_dispersion")  # noqa: ERA001
            pass


def convert(input: xr.Dataset | Result, cleanup: bool = False) -> xr.Dataset | CompatResult:
    """Convert a glotaran Result or xarray Dataset to a different format.

    Parameters
    ----------
    input : xr.Dataset or Result
        The input object to be converted.
    cleanup : bool, optional
        Whether or not to perform cleanup after the conversion. Default is False.

    Returns
    -------
    xr.Dataset or Result
        The converted object.

    Raises
    ------
    ValueError
        If the input is not a Result or a Dataset.

    Examples
    --------
    >>> result = Result(...)
    >>> converted_result = convert(result, cleanup=True)
    >>> dataset = xr.open_dataset('input_dataset.nc')
    >>> converted_dataset = convert(dataset)
    """
    if isinstance(input, Result):
        return convert_result(input, cleanup=cleanup)
    if isinstance(input, xr.Dataset):
        return convert_dataset(input, cleanup=cleanup)
    msg = "input must be either a Result or a Dataset"
    raise ValueError(msg)


def convert_dataset(dataset: xr.Dataset, cleanup: bool = False) -> xr.Dataset:
    """Convert the dataset format used in staging (to be v0.8) to the format of main (v0.7)."""

    # Create a copy of the staging dataset to avoid modifying the original
    converted_ds = dataset.copy()

    _adjust_activation_to_irf(converted_ds, cleanup=cleanup)
    _adjust_estimations_to_spectra(converted_ds, cleanup=cleanup)
    _adjust_concentrations(converted_ds, cleanup=cleanup)
    _adjust_fitted_data(converted_ds, cleanup=cleanup)

    if (
        "weighted_root_mean_square_error" not in converted_ds.attrs
        and "root_mean_square_error" in converted_ds.attrs
    ):
        converted_ds.attrs["weighted_root_mean_square_error"] = converted_ds.attrs[
            "root_mean_square_error"
        ]

    # variable_mapping = {"species_associated_estimation": "species_associated_spectra"} # noqa: ERA001, E501
    # converted_ds = converted_ds.rename_vars({**variable_mapping}) # noqa: ERA001

    # more conversions
    return converted_ds


def convert_result(result: Result, cleanup: bool = False) -> CompatResult:
    """Convert the result format used in staging (to be v0.8) to the format of main (v0.7)."""

    converted_result = CompatResult.from_result(result)

    # convert the datasets
    for key in converted_result.optimization_results:
        converted_result.optimization_results[key] = convert_dataset(
            converted_result.optimization_results[key], cleanup=cleanup
        )

    # convert the parameters
    return converted_result
