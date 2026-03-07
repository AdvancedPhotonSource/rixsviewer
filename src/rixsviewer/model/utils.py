import logging
import warnings

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

logger = logging.getLogger(__name__)


def _gaussian(x_vals, amp, cen, sigma):
    """Normalised Gaussian: amp * exp(-0.5 * ((x - cen) / sigma)^2)."""
    return amp * np.exp(-0.5 * ((x_vals - cen) / sigma) ** 2)


def apply_subpixel_shear_3d(arr3d, ylow, yhigh, theta_deg, order=1):
    """
    Applies subpixel shearing to a specific row range across all frames in a 3D array.

    Parameters:
    - arr3d: 3d numpy array (N_frames, height, width)
    - ylow, yhigh: The range of rows to shear
    - theta_deg: Angle in degrees
    - order: Interpolation order (1 for linear, 3 for cubic)
    """
    if abs(theta_deg) < 1e-3:
        return arr3d
    theta = np.deg2rad(theta_deg)

    # result copy to keep original intact
    result = arr3d.copy()

    # Extract the volume of interest (VOI)
    # Shape: (N_frames, rows_in_range, width)
    voi = arr3d[:, ylow:yhigh, :]
    n_frames, rows, cols = voi.shape

    # Calculate the center row of the range
    center_y = (ylow + yhigh - 1) / 2.0

    # Create the coordinate grid for a single frame
    # yy: (rows, cols), xx: (rows, cols)
    yy, xx = np.indices((rows, cols), dtype=np.float64)

    # Calculate shift based on the global row index (ylow + yy)
    current_y_indices = ylow + yy
    shift = np.sin(theta) * (current_y_indices - center_y)

    # Prepare the 3D coordinates for map_coordinates
    # We need three arrays of shape (N_frames, rows, cols)

    # 1. Frame indices: each frame stays in its own plane
    # np.arange(n_frames)[:, None, None] creates shape (N_frames, 1, 1)
    # which broadcasts to (N_frames, rows, cols)
    f_coords = np.arange(n_frames)[:, None, None] * np.ones((1, rows, cols))

    # 2. Vertical indices: remain the same within the ROI
    y_coords = np.broadcast_to(yy, (n_frames, rows, cols))

    # 3. Horizontal indices: shifted by the calculated amount
    x_coords = np.broadcast_to(xx - shift, (n_frames, rows, cols))

    # Stack coordinates for map_coordinates: (3, N_frames, rows, cols)
    coords = np.array([f_coords, y_coords, x_coords])

    # Apply interpolation across the 3D volume
    sheared_voi = map_coordinates(voi, coords, order=order, mode="constant", cval=0.0)

    # Place back into the result array
    result[:, ylow:yhigh, :] = sheared_voi

    return result


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

    data_2d = np.sum(data[:, Ylow:Yhigh, :], axis=1)

    if 2 * RefL < shape[2]:  # pad reflectivity tail beyond 2*RefL
        data_2d[:, 2 * RefL :] = np.mean(data_2d[:, 2 * RefL])

    xaxis = np.arange(shape[2]) - RefL
    return data_2d, xaxis


def fit_pixel_size(
    data,
    merixE,
    scan_type,
    DeltaD=0.022,
    RefL=70,
    Eb=10,
    rowland_radius=1900,
    Ylow=0,
    Yhigh=256,
    center_method="gaussian",
    **kwargs,
):
    """Determine the effective detector pixel size (mm) from an EnergyScan.

    Pure function — no dataset-object dependency.

    Parameters
    ----------
    data : ndarray, shape (n_frames, height, width)
    merixE : array-like, shape (n_frames,)  — incident energy per frame (keV)
    scan_type : {'EnergyScan', 'SnapshotScan'}
    DeltaD : float   — nominal pixel pitch (mm). Default ``0.022``.
    RefL : int       — reference pixel (elastic peak). Default ``70``.
    Eb : float       — backscattering energy (keV). Default ``10``.
    rowland_radius : float  — Rowland radius (mm). Default ``1900``.
    Ylow, Yhigh : int  — row-summation bounds. Default ``0``, ``256``.
    center_method : str  — peak-finding method. Default ``'gaussian'``.
    **kwargs : silently ignored (allows metadata dicts to be forwarded).

    Returns
    -------
    float
        Effective pixel size in mm.
    """
    merixE = np.asarray(merixE, dtype=float)

    if scan_type == "SnapshotScan":
        logger.warning("fit_pixel_size is not implemented for SnapshotScan")
        return float(DeltaD)

    data_1d, _ = _preprocess_frames(data, Ylow, Yhigh, RefL)

    n = data_1d.shape[0]
    theta_b = np.arcsin(Eb / merixE)
    energy_cen = merixE.reshape(-1, 1)
    scale = Eb / (2 * rowland_radius) / np.tan(theta_b)

    com_pixel, valid_mask = find_peaks(data_1d, method=center_method, smooth_window=3, poly_order=2)
    a_mat = (com_pixel * scale).reshape(n, 1)
    a_mat = np.hstack([a_mat, np.ones_like(a_mat)])
    effective_pixel_size, _ = np.linalg.lstsq(a_mat[valid_mask], energy_cen[valid_mask])[0]
    effective_pixel_size = float(effective_pixel_size)
    logger.info(f"Fitted effective pixel size: {effective_pixel_size} mm")
    return effective_pixel_size


def _compute_energy_axis(data_2d, xaxis, merixE, Eb, rowland_radius, scan_type, DeltaD):
    """Build per-pixel energy axes via Rowland geometry and align all
    frames onto a common energy grid.

    Parameters
    ----------
    data_1d : ndarray, shape (n_frames, width)
    xaxis   : ndarray, shape (width,)
    merixE  : ndarray, shape (n_frames,)  — incident energy per frame (keV)
    Eb      : float  — analyser backscattering energy (keV)
    rowland_radius : float  — Rowland circle radius (mm)
    scan_type      : str   — ``'EnergyScan'`` or ``'SnapshotScan'``
    DeltaD         : float — nominal pixel pitch (mm)

    Returns
    -------
    lines           : list of [ndarray, ndarray]  — per-frame [E, I] pairs
    bin_energy_axis : ndarray  — common energy grid
    bin_data        : ndarray, shape (n_frames, n_bins)
    """
    n = data_2d.shape[0]
    assert merixE.shape[0] == n, "merixE and data must have the same number of frames"

    theta_b = np.arcsin(Eb / merixE)
    energy_cen = merixE.reshape(-1, 1)
    scale = Eb / (2 * rowland_radius) / np.tan(theta_b)

    energy_axis = energy_cen - np.outer(scale, xaxis) * DeltaD

    if scan_type == "SnapshotScan":
        bin_energy_axis = energy_axis[0]
        bin_data = data_2d.copy()
        lines = [[bin_energy_axis, data_2d[i]] for i in range(n)]
    else:
        for i in range(n):
            idx = np.argsort(energy_axis[i])
            energy_axis[i] = energy_axis[i][idx]
            data_2d[i] = data_2d[i][idx]

        lines = [[energy_axis[i], data_2d[i]] for i in range(n)]
        e_min, e_max = np.min(energy_axis), np.max(energy_axis)
        step = int((e_max - e_min) / np.mean(np.abs(np.diff(energy_axis, axis=1))))

        bin_energy_axis = np.linspace(e_min, e_max, step)
        bin_data = np.array(
            [np.interp(bin_energy_axis, energy_axis[i], data_2d[i], left=np.nan, right=np.nan) for i in range(n)]
        )

    return lines, bin_energy_axis, np.array(bin_data)


def _reduce_frames(bin_energy_axis, bin_data, noise_model, bin_pixel=1):
    """Average aligned frames and estimate per-bin uncertainty.

    Parameters
    ----------
    bin_energy_axis : ndarray, shape (n_bins,)
        Energy axis for binning.
    bin_data : ndarray, shape (n_frames, n_bins)
        NaN marks bins with no coverage for a given frame.
    noise_model : {'poisson', 'gaussian'}
    bin_pixel : int
        Number of pixels to bin together.
    Returns
    -------
    bin_energy_axis : ndarray, shape (n_bins,)
    mean : ndarray, shape (n_bins,)
    err  : ndarray, shape (n_bins,)
    """
    assert noise_model in ("poisson", "gaussian"), "noise_model must be either 'poisson' or 'gaussian'"

    count = np.sum(~np.isnan(bin_data), axis=0)
    mean = np.nansum(bin_data, axis=0) / np.clip(count, a_min=1, a_max=None)

    assert bin_pixel > 0 and isinstance(bin_pixel, int), "bin_pixel must be a positive integer"
    if bin_pixel > 1:
        n = (len(mean) // bin_pixel) * bin_pixel
        # Reshape bin_data to (n_frames, n_superbins, bin_pixel) for both branches
        bin_data_3d = bin_data[:, :n].reshape(bin_data.shape[0], -1, bin_pixel)
        mean = mean[:n].reshape(-1, bin_pixel).sum(axis=1)
        count = count[:n].reshape(-1, bin_pixel).sum(axis=1)  # total samples per super-bin
        bin_energy_axis = bin_energy_axis[:n].reshape(-1, bin_pixel).mean(axis=1)
    else:
        bin_data_3d = bin_data[:, :, np.newaxis]  # (n_frames, n_bins, 1) — trivially grouped

    if noise_model == "poisson":
        err = np.sqrt(mean / np.clip(count, a_min=1, a_max=None))
    else:
        # Pool all (frame × bin_pixel) samples per super-bin, then standard error of the mean
        pooled = bin_data_3d.reshape(-1, bin_data_3d.shape[1])  # (n_frames * bin_pixel, n_superbins)
        err = np.nanstd(pooled, axis=0) / np.sqrt(np.clip(count, a_min=1, a_max=None))

    return bin_energy_axis, mean, err


def _compute_fwhm_func(energy_axis, intensity, err=None):
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

    # Build sigma weights: must be strictly positive and finite
    sigma_w = None
    if err is not None:
        _w = err[mask].astype(float)
        if np.all(np.isfinite(_w)) and np.all(_w > 0):
            sigma_w = _w

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # suppress OptimizeWarning and numpy warnings
            popt, _ = curve_fit(_gaussian, x, y, p0=p0, sigma=sigma_w, absolute_sigma=True, maxfev=2000)
        fwhm = 2.0 * np.sqrt(2.0 * np.log(2.0)) * abs(popt[2])
        center = float(popt[1])
        # logger.info(f"FWHM (Gaussian fit): {fwhm:.6f} keV  center: {center:.6f} keV")
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
    Eb=10,
    rowland_radius=1900,
    Ylow=0,
    Yhigh=256,
    noise_model="poisson",
    bin_pixel=1,
    compute_fwhm=False,
    TiltAngle=0,
    TiltOrder=1,
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
    Eb : float       — backscattering energy (keV). Default ``10``.
    rowland_radius : float  — Rowland radius (mm). Default ``1900``.
    Ylow, Yhigh : int  — row-summation bounds. Default ``0``, ``256``.
    noise_model : {'poisson', 'gaussian'}. Default ``'poisson'``.
    **kwargs : silently ignored (allows metadata dicts to be forwarded).

    Returns
    -------
    dict with keys ``rawdata_lines``, ``binned_line``, ``DeltaD``,
    ``summed_data``, ``levels``.
    """
    merixE = np.asarray(merixE, dtype=float)

    data = apply_subpixel_shear_3d(data, Ylow, Yhigh, TiltAngle, TiltOrder)

    data_2d, xaxis = _preprocess_frames(data, Ylow, Yhigh, RefL)

    lines, bin_energy, bin_data = _compute_energy_axis(
        data_2d,
        xaxis,
        merixE,
        Eb,
        rowland_radius,
        scan_type,
        DeltaD,
    )

    bin_energy, bin_data_mean, bin_data_err = _reduce_frames(bin_energy, bin_data, noise_model, bin_pixel)

    if compute_fwhm:
        fwhm, center = _compute_fwhm_func(bin_energy, bin_data_mean, bin_data_err)
    else:
        fwhm, center = None, None

    if scan_type == "SnapshotScan":
        summed_data = np.sum(data, axis=0)
        levels = percentile_clip(summed_data)
    else:
        summed_data = None
        levels = None

    return {
        "rawdata_lines": lines,
        "binned_line": (bin_energy, bin_data_mean, bin_data_err),
        "DeltaD": DeltaD,
        "summed_data": summed_data,
        "levels": levels,
        "fwhm": fwhm,
        "center": center,
        "energy_resolution": round((bin_energy[1] - bin_energy[0]) * 1e6, 3),
    }
