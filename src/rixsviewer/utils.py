import numpy as np
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt


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
