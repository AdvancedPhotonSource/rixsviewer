import logging

import numpy as np
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def plot_peak_debug(x, centers, num_samples=5, row_indices=None):
    """
    Plots individual row profiles and marks the detected peak centers.

    Parameters:
    - x: The original 2D numpy array (m, n).
    - centers: The 1D array of calculated centers (m,).
    - num_samples: How many random rows to plot if row_indices is None.
    - row_indices: A list of specific row indices to inspect (e.g., [0, 10, 50]).
    """
    m, n = x.shape
    indices = np.arange(n)
    num_samples = max(1, min(num_samples, m))
    row_indices = list(np.arange(num_samples))

    plt.figure(figsize=(10, 2 * len(row_indices)))

    for i, row_idx in enumerate(row_indices):
        plt.subplot(len(row_indices), 1, i + 1)

        # Plot the raw data
        plt.plot(indices, x[row_idx], label=f"Row {row_idx}", color="steelblue", alpha=0.8)

        # Mark the detected center with a vertical line
        center_val = centers[row_idx]
        if not np.isnan(center_val):
            plt.axvline(x=center_val, color="red", linestyle="--", label=f"Center: {center_val:.2f}")
            # Add a point on the curve for visual confirmation
            # We use np.interp to find the height if the center is sub-pixel
            peak_height = np.interp(center_val, indices, x[row_idx])
            plt.scatter(center_val, peak_height, color="red", zorder=5)

        plt.legend(loc="upper right", fontsize="small")
        plt.grid(alpha=0.3)
        if i == len(row_indices) - 1:
            plt.xlabel("Index (n)")

    plt.tight_layout()
    plt.show()


def find_peaks(x, method="centroid", smooth_window=None, poly_order=2):
    """
    Finds peak centers for each row in a 2D array.

    Methods:
    - 'argmax': Fast, integer precision.
    - 'centroid': Sub-pixel precision, weighted average.
    - 'gaussian': Highest precision, fits a curve (slowest).
    """
    x = np.array(x).astype(np.float32)
    m, n = x.shape
    indices = np.arange(n)
    centers = np.zeros(m)

    robust_peak_value = np.percentile(x[x > 0], 99)
    robust_peak_value_per_row = np.percentile(x, 99, axis=1)
    valid_mask = robust_peak_value_per_row > robust_peak_value / 2.0
    # print(f"robust_peak_value: {robust_peak_value}")
    # print(f"robust_peak_value_per_row: {robust_peak_value_per_row}")
    # print(valid_mask)

    # 1. Optional Smoothing
    if smooth_window and smooth_window > poly_order:
        x = savgol_filter(x, window_length=smooth_window, polyorder=poly_order, axis=1)

    # 2. Baseline Subtraction (Crucial for Centroid/Fitting)
    # Subtracting the row minimum helps isolate the peak from the background
    x_clean = x - x.min(axis=1, keepdims=True)

    # 3. Method Selection
    if method == "argmax":
        centers = np.argmax(x_clean, axis=1)

    elif method == "centroid":
        row_sums = x_clean.sum(axis=1)
        # Avoid division by zero for flat rows
        centers = np.divide(np.sum(x_clean * indices, axis=1), row_sums, out=np.zeros(m), where=row_sums != 0)

    elif method == "gaussian":

        def gaussian_func(x_vals, amp, cen, sigma):
            return amp * np.exp(-((x_vals - cen) ** 2) / (2 * sigma**2))

        for i in range(m):
            row = x_clean[i]
            p0 = [row.max(), np.argmax(row), 2.0]  # Initial guess
            try:
                popt, _ = curve_fit(gaussian_func, indices, row, p0=p0)
                centers[i] = popt[1]
            except:
                centers[i] = np.nan  # Fallback if fit fails

    else:
        raise ValueError("Method must be 'argmax', 'centroid', or 'gaussian'")

    # plot_peak_debug(x[valid_mask], centers[valid_mask], num_samples=20)
    return centers, valid_mask


def percentile_clip(data, threshold=99):
    """
    Compute display intensity limits using percentile clipping.

    Calculates a (vmin, vmax) tuple suitable for image display by computing
    the given percentile of positive values.  Only the first frame is used
    for 3-D arrays.

    Parameters
    ----------
    data : numpy.ndarray
        Input array with ndim 2 or 3.  Pixels with value ``<= 0`` are
        excluded from the percentile calculation.
    threshold : float, optional
        Upper percentile used to clip hot pixels, by default ``99``.

    Returns
    -------
    tuple of (float, float)
        ``(0, vmax)`` where *vmax* is the *threshold*-th percentile of the
        positive pixels.  Returns ``(0, 0)`` when *data* is empty.
    """
    if data.size == 0:
        return (0, 0)
    if data.ndim == 2:
        mask = data > 0
        vmax = np.percentile(data[mask], threshold)
    elif data.ndim == 3:
        mask = data[0] > 0
        vmax = np.percentile(data[0][mask], threshold)
    return (0, vmax)


def bin_rixs_data(
    data,
    merixE,
    scan_type,
    DeltaD=0.022,
    RefL=70,
    fit_pixel_size=True,
    Eb=10,
    rowland_radius=1900,
    Ylow=0,
    Yhigh=256,
    noise_model="poisson",
    center_method="gaussian",
    **kwargs,
):
    """Compute the binned RIXS spectrum from a TIFF image stack.

    This is a pure function with no dependency on any dataset object.
    All data required for computation is passed in explicitly.

    Parameters
    ----------
    data : numpy.ndarray
        3-D array of shape ``(n_frames, height, width)``, dtype ``float32``.
    merixE : array-like of float
        Incident energy for each frame (keV), length ``n_frames``.
    scan_type : {'EnergyScan', 'SnapshotScan'}
        Scan classification:

        ``'EnergyScan'``
            Each frame has a different incident energy; frames are sorted and
            interpolated onto a common uniform energy grid before averaging.
        ``'SnapshotScan'``
            All frames share the same incident energy; no sorting or
            interpolation is performed.
    DeltaD : float, optional
        Nominal detector pixel pitch in the energy-dispersion direction (mm).
        Used when *fit_pixel_size* is ``False``.  Default ``0.022``.
    RefL : int, optional
        Reference pixel corresponding to the elastic peak (zero of the
        pixel-offset axis).  Default ``70``.
    fit_pixel_size : bool, optional
        When ``True`` and *scan_type* is ``'EnergyScan'``, estimate the
        effective pixel size by least-squares fitting.  Default ``True``.
    Eb : float, optional
        Analyzer backscattering energy in keV.  Default ``10``.
    rowland_radius : float, optional
        Rowland circle radius in mm.  Default ``1900``.
    Ylow : int, optional
        Lower Y-pixel bound (inclusive) for the row-summation region.
        Default ``0``.
    Yhigh : int, optional
        Upper Y-pixel bound (exclusive) for the row-summation region.
        Default ``256``.
    noise_model : {'poisson', 'gaussian'}, optional
        Statistical model for per-bin error estimation.  Default ``'poisson'``.
    center_method : str, optional
        Peak-finding method forwarded to :func:`find_peaks`.
        Default ``'gaussian'``.
    **kwargs
        Additional keyword arguments are silently ignored (allows extra
        metadata keys to be forwarded without error).

    Returns
    -------
    dict
        ``rawdata_lines``
            Per-frame ``[energy_axis, intensity]`` pairs before rebinning.
        ``binned_line``
            ``(bin_energy_axis, bin_data_mean, bin_data_err)`` on a uniform
            energy grid.
        ``DeltaD_fit``
            Effective pixel size used (fitted or nominal).
        ``summed_data``
            Sum of all frames (``SnapshotScan`` only; ``None`` otherwise).
        ``levels``
            ``(vmin, vmax)`` display limits for *summed_data*, or ``None``.
    """
    merixE = np.asarray(merixE, dtype=float)
    shape = data.shape  # (n_frames, height, width)

    assert Ylow >= 0 and Yhigh <= shape[1] and Ylow < Yhigh, "check Ylow and Yhigh and detector shape"
    data_1d = np.sum(data[:, Ylow:Yhigh, :], axis=1)

    # Pad pixel columns beyond 2*RefL with the column mean
    if 2 * RefL < shape[2]:
        data_1d[:, 2 * RefL :] = np.mean(data_1d[:, 2 * RefL])

    xaxis = np.arange(shape[2]) - RefL

    assert merixE.shape[0] == shape[0], "merixE and data must have the same number of frames"

    theta_b = np.arcsin(Eb / merixE)
    energy_cen = merixE.reshape(-1, 1)
    scale = np.array(Eb / (2 * rowland_radius) / np.tan(theta_b))

    if fit_pixel_size and scan_type == "SnapshotScan":
        logger.warning("fit_pixel_size is not implemented for SnapshotScan")
        fit_pixel_size = False

    if fit_pixel_size and scan_type == "EnergyScan":
        com_pixel, valid_mask = find_peaks(data_1d, method=center_method, smooth_window=3, poly_order=2)
        a_mat = np.array(com_pixel * scale).reshape(shape[0], 1)
        a_mat = np.hstack([a_mat, np.ones_like(a_mat)])
        effective_pixel_size, _ = np.linalg.lstsq(a_mat[valid_mask], energy_cen[valid_mask])[0]
        effective_pixel_size = float(effective_pixel_size)
        logger.info(f"Fitted effective pixel size: {effective_pixel_size} mm")
    else:
        effective_pixel_size = DeltaD

    energy_axis = energy_cen - np.outer(scale, xaxis) * effective_pixel_size

    if scan_type == "SnapshotScan":
        bin_energy_axis = energy_axis[0]
        bin_data = data_1d
        lines = [[bin_energy_axis, data_1d[n]] for n in range(shape[0])]
    else:
        for n in range(shape[0]):
            sort_idx = np.argsort(energy_axis[n])
            energy_axis[n] = energy_axis[n][sort_idx]
            data_1d[n] = data_1d[n][sort_idx]

        lines = [[energy_axis[n], data_1d[n]] for n in range(shape[0])]
        energy_min, energy_max = np.min(energy_axis), np.max(energy_axis)
        step = int((energy_max - energy_min) / np.mean(np.abs(np.diff(energy_axis, axis=1))))

        bin_energy_axis = np.linspace(energy_min, energy_max, step)
        bin_data = np.array(
            [np.interp(bin_energy_axis, energy_axis[n], data_1d[n], left=np.nan, right=np.nan) for n in range(shape[0])]
        )

    bin_data = np.array(bin_data)
    bin_data_sum = np.nansum(bin_data, axis=0)
    bin_data_cnt = np.sum(~np.isnan(bin_data), axis=0)
    bin_data_mean = bin_data_sum / np.clip(bin_data_cnt, a_min=1, a_max=None)

    assert noise_model in ("poisson", "gaussian"), "noise_model must be either 'poisson' or 'gaussian'"
    if noise_model == "poisson":
        bin_data_err = np.sqrt(bin_data_mean / bin_data_cnt)
    else:
        bin_data_err = np.nanstd(bin_data, axis=0) / np.sqrt(bin_data_cnt)

    if scan_type == "SnapshotScan":
        summed_data = np.sum(data, axis=0)
        levels = percentile_clip(summed_data)
    else:
        summed_data = None
        levels = None

    return {
        "rawdata_lines": lines,
        "binned_line": (bin_energy_axis, bin_data_mean, bin_data_err),
        "DeltaD_fit": effective_pixel_size,
        "summed_data": summed_data,
        "levels": levels,
    }
