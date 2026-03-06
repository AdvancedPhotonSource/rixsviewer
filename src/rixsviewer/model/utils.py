import logging

import numpy as np
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def _gaussian(x_vals, amp, cen, sigma):
    """Normalised Gaussian: amp * exp(-0.5 * ((x - cen) / sigma)^2)."""
    return amp * np.exp(-0.5 * ((x_vals - cen) / sigma) ** 2)


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
        for i in range(m):
            row = x_clean[i]
            p0 = [row.max(), np.argmax(row), 2.0]  # Initial guess
            try:
                popt, _ = curve_fit(_gaussian, indices, row, p0=p0)
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


def _preprocess_frames(data, Ylow, Yhigh, RefL):
    """Sum detector rows in the ROI, pad the reflectivity tail, build xaxis.

    Parameters
    ----------
    data : ndarray, shape (n_frames, height, width)
    Ylow, Yhigh : int  — inclusive/exclusive row bounds
    RefL : int         — reference pixel (elastic peak channel)

    Returns
    -------
    data_1d : ndarray, shape (n_frames, width)
    xaxis : ndarray, shape (width,)  — pixel offset from elastic peak
    """
    shape = data.shape
    assert Ylow >= 0 and Yhigh <= shape[1] and Ylow < Yhigh, "check Ylow and Yhigh and detector shape"

    data_1d = np.sum(data[:, Ylow:Yhigh, :], axis=1)

    if 2 * RefL < shape[2]:  # pad reflectivity tail beyond 2*RefL
        data_1d[:, 2 * RefL :] = np.mean(data_1d[:, 2 * RefL])

    xaxis = np.arange(shape[2]) - RefL
    return data_1d, xaxis


def _fit_pixel_size(data_1d, scale, energy_cen, scan_type, center_method, DeltaD):
    """Determine the effective detector pixel size (mm) by fitting elastic-peak
    positions vs. incident energy for an EnergyScan.

    Parameters
    ----------
    data_1d : ndarray, shape (n_frames, width)
    scale : ndarray, shape (n_frames,)  -- keV/mm dispersion scale per frame
    energy_cen : ndarray, shape (n_frames, 1)  -- incident energy per frame
    scan_type : str  -- 'EnergyScan' or 'SnapshotScan'
    center_method : str  -- peak-finding method for find_peaks
    DeltaD : float  -- nominal pixel pitch (mm), returned unchanged when not fitting

    Returns
    -------
    float
        Effective pixel size in mm.
    """
    n = data_1d.shape[0]
    if scan_type == "SnapshotScan":
        logger.warning("fit_pixel_size is not implemented for SnapshotScan")
        return float(DeltaD)

    com_pixel, valid_mask = find_peaks(data_1d, method=center_method, smooth_window=3, poly_order=2)
    a_mat = (com_pixel * scale).reshape(n, 1)
    a_mat = np.hstack([a_mat, np.ones_like(a_mat)])
    effective_pixel_size, _ = np.linalg.lstsq(a_mat[valid_mask], energy_cen[valid_mask])[0]
    effective_pixel_size = float(effective_pixel_size)
    logger.info(f"Fitted effective pixel size: {effective_pixel_size} mm")
    return effective_pixel_size


def _compute_energy_axis(data_1d, xaxis, merixE, Eb, rowland_radius, fit_pixel_size, scan_type, center_method, DeltaD):
    """Build per-pixel energy axes via Rowland geometry, fit DeltaD if needed,
    and align all frames onto a common energy grid.

    Parameters
    ----------
    data_1d : ndarray, shape (n_frames, width)
    xaxis   : ndarray, shape (width,)
    merixE  : ndarray, shape (n_frames,)  — incident energy per frame (keV)
    Eb      : float  — analyser backscattering energy (keV)
    rowland_radius : float  — Rowland circle radius (mm)
    fit_pixel_size : bool
    scan_type      : str   — ``'EnergyScan'`` or ``'SnapshotScan'``
    center_method  : str   — peak-finding method
    DeltaD         : float — nominal pixel pitch (mm)

    Returns
    -------
    lines           : list of [ndarray, ndarray]  — per-frame [E, I] pairs
    bin_energy_axis : ndarray  — common energy grid
    bin_data        : ndarray, shape (n_frames, n_bins)
    effective_pixel_size : float  — fitted or nominal DeltaD (mm)
    """
    n = data_1d.shape[0]
    assert merixE.shape[0] == n, "merixE and data must have the same number of frames"

    theta_b = np.arcsin(Eb / merixE)
    energy_cen = merixE.reshape(-1, 1)
    scale = Eb / (2 * rowland_radius) / np.tan(theta_b)

    if fit_pixel_size:
        effective_pixel_size = _fit_pixel_size(data_1d, scale, energy_cen, scan_type, center_method, DeltaD)
    else:
        effective_pixel_size = DeltaD

    energy_axis = energy_cen - np.outer(scale, xaxis) * effective_pixel_size

    if scan_type == "SnapshotScan":
        bin_energy_axis = energy_axis[0]
        bin_data = data_1d.copy()
        lines = [[bin_energy_axis, data_1d[i]] for i in range(n)]
    else:
        for i in range(n):
            idx = np.argsort(energy_axis[i])
            energy_axis[i] = energy_axis[i][idx]
            data_1d[i] = data_1d[i][idx]

        lines = [[energy_axis[i], data_1d[i]] for i in range(n)]
        e_min, e_max = np.min(energy_axis), np.max(energy_axis)
        step = int((e_max - e_min) / np.mean(np.abs(np.diff(energy_axis, axis=1))))

        bin_energy_axis = np.linspace(e_min, e_max, step)
        bin_data = np.array(
            [np.interp(bin_energy_axis, energy_axis[i], data_1d[i], left=np.nan, right=np.nan) for i in range(n)]
        )

    return lines, bin_energy_axis, np.array(bin_data), effective_pixel_size


def _reduce_frames(bin_data, noise_model):
    """Average aligned frames and estimate per-bin uncertainty.

    Parameters
    ----------
    bin_data : ndarray, shape (n_frames, n_bins)
        NaN marks bins with no coverage for a given frame.
    noise_model : {'poisson', 'gaussian'}

    Returns
    -------
    mean : ndarray, shape (n_bins,)
    err  : ndarray, shape (n_bins,)
    """
    assert noise_model in ("poisson", "gaussian"), "noise_model must be either 'poisson' or 'gaussian'"

    count = np.sum(~np.isnan(bin_data), axis=0)
    mean = np.nansum(bin_data, axis=0) / np.clip(count, a_min=1, a_max=None)

    if noise_model == "poisson":
        err = np.sqrt(mean / count)
    else:
        err = np.nanstd(bin_data, axis=0) / np.sqrt(count)

    return mean, err


def compute_fwhm(energy_axis, intensity, err=None):
    """Estimate the full-width at half-maximum (FWHM) of a spectral line.

    Attempts a Gaussian least-squares fit first.  If the fit fails (e.g.
    flat or noisy data) falls back to linear interpolation of the
    half-maximum crossings.

    Parameters
    ----------
    energy_axis : ndarray, shape (n,)
        Energy values (keV).  Must be monotonically increasing.
    intensity : ndarray, shape (n,)
        Spectral intensity, e.g. ``bin_data_mean`` from :func:`bin_rixs_data`.
    err : ndarray, shape (n,) or None, optional
        Per-point uncertainty used as weights (``1/err``) in the Gaussian fit.
        Ignored for the interpolation fallback.  Default ``None``.

    Returns
    -------
    tuple of (float or None, float or None)
        ``(fwhm, center)`` where *fwhm* is the full-width at half-maximum and
        *center* is the peak position, both in the same units as *energy_axis*
        (keV).  Either value is ``None`` when the estimate cannot be computed.
    """
    # --- clean up NaN / non-finite values ---
    mask = np.isfinite(intensity) & np.isfinite(energy_axis)
    x = energy_axis[mask]
    y = intensity[mask]
    if len(x) < 5:
        logger.warning("compute_fwhm: too few finite points to estimate FWHM")
        return None, None

    # subtract baseline (minimum) so the peak sits above zero
    y = y - y.min()
    peak_val = y.max()
    if peak_val == 0:
        return None, None

    # --- Gaussian fit ---
    p0 = [peak_val, x[np.argmax(y)], (x[-1] - x[0]) / 6]
    sigma_w = err[mask] if err is not None else None
    try:
        with np.errstate(all="ignore"):
            popt, _ = curve_fit(_gaussian, x, y, p0=p0, sigma=sigma_w, absolute_sigma=True, maxfev=2000)
        fwhm = 2.0 * np.sqrt(2.0 * np.log(2.0)) * abs(popt[2])
        center = float(popt[1])
        logger.info(f"FWHM (Gaussian fit): {fwhm:.6f} keV  center: {center:.6f} keV")
        return float(fwhm), center
    except Exception:
        pass  # fall through to interpolation fallback

    # --- interpolation fallback: find half-max crossings ---
    half = peak_val / 2.0
    above = y >= half
    edges = np.diff(above.astype(int))
    rise_idx = np.where(edges == 1)[0]
    fall_idx = np.where(edges == -1)[0]
    if len(rise_idx) == 0 or len(fall_idx) == 0 or rise_idx[0] >= fall_idx[-1]:
        logger.warning("compute_fwhm: half-max crossings not found")
        return None, None

    def _interp_crossing(i):
        """Linear interpolation of the x position where y crosses half."""
        dx = x[i + 1] - x[i]
        dy = y[i + 1] - y[i]
        return x[i] + dx * (half - y[i]) / dy if dy != 0 else x[i]

    x_left = _interp_crossing(rise_idx[0])
    x_right = _interp_crossing(fall_idx[-1])
    fwhm = x_right - x_left
    center = float((x_left + x_right) / 2.0)
    logger.info(f"FWHM (interpolation): {fwhm:.6f} keV  center: {center:.6f} keV")
    return float(fwhm), center


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

    Pure function — no dataset-object dependency.  Delegates to three helpers:

    1. :func:`_preprocess_frames`   — ROI sum + pixel-offset axis
    2. :func:`_compute_energy_axis` — Rowland calibration + grid alignment
    3. :func:`_reduce_frames`       — weighted mean + uncertainty

    Parameters
    ----------
    data : ndarray, shape (n_frames, height, width)
    merixE : array-like, shape (n_frames,)  — incident energy per frame (keV)
    scan_type : {'EnergyScan', 'SnapshotScan'}
    DeltaD : float   — nominal pixel pitch (mm). Default ``0.022``.
    RefL : int       — reference pixel (elastic peak). Default ``70``.
    fit_pixel_size : bool. Default ``True``.
    Eb : float       — backscattering energy (keV). Default ``10``.
    rowland_radius : float  — Rowland radius (mm). Default ``1900``.
    Ylow, Yhigh : int  — row-summation bounds. Default ``0``, ``256``.
    noise_model : {'poisson', 'gaussian'}. Default ``'poisson'``.
    center_method : str  — peak-finding method. Default ``'gaussian'``.
    **kwargs : silently ignored (allows metadata dicts to be forwarded).

    Returns
    -------
    dict with keys ``rawdata_lines``, ``binned_line``, ``DeltaD_fit``,
    ``summed_data``, ``levels``.
    """
    merixE = np.asarray(merixE, dtype=float)

    data_1d, xaxis = _preprocess_frames(data, Ylow, Yhigh, RefL)

    lines, bin_energy_axis, bin_data, effective_pixel_size = _compute_energy_axis(
        data_1d,
        xaxis,
        merixE,
        Eb,
        rowland_radius,
        fit_pixel_size,
        scan_type,
        center_method,
        DeltaD,
    )

    bin_data_mean, bin_data_err = _reduce_frames(bin_data, noise_model)

    fwhm, center = compute_fwhm(bin_energy_axis, bin_data_mean, bin_data_err)

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
        "fwhm": fwhm,
        "center": center,
    }
