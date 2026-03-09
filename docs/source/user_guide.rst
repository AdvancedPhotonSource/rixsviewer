==========
User Guide
==========

This guide explains how to use the RIXS Viewer graphical user interface (GUI) to visualize and process Resonance Inelastic X-ray Scattering (RIXS) data.

Starting the Application
========================

You can start the RIXS Viewer GUI from the command line:

.. code-block:: bash

    rixsviewer --specfile /path/to/data.spec --tiff-folder /path/to/tiff/folder

If you do not specify the command-line arguments, an empty GUI will open, and you can load the data manually.

1. Loading Data (SPEC File and TIFF Folder)
===========================================

The RIXS Viewer requires a SPEC file containing the scan metadata and a corresponding folder containing the TIFF images from the detector.

- **Set TIFF Folder**: Click the **Set TIFF Folder** button and browse to the directory containing your TIFF images.
- **Load SPEC File**: Click the **Load SPEC File** button and select your ``.spec`` or ``.spm3`` file.
- **Load Scan**: Click the **Load Scan** button to parse the SPEC file and load the list of available scans into the top table.

2. Auto-Update Mode
===================

When running experiments in real-time, you might want the viewer to update automatically as new points are collected or new scans are started.

- **Enable Auto-Update**: Check the **Auto-update** checkbox.
- **How it works**: The viewer will check the SPEC file for modifications every second. If new points are appended to the current scan, or a completely new scan is added, the application will automatically process the new frames and refresh the display. 
- While active, the scan table will permanently select the latest (last) scan in the file, making it ideal for monitoring an ongoing measurement.

3. Calibration (Fitting Pixel Size)
===================================

Calibration allows you to find the exact effective pixel size (``DeltaD``) or tilt angle by optimizing the spectral resolution (minimizing FWHM).

- **Requirement**: Calibration requires an **EnergyScan** to be selected.
- **Execution**: Select a target parameter (e.g., ``DeltaD`` or ``TiltAngle``) and click the **Fit Pixel Size** button. 
- **Under the hood**: The program performs a line search around an initial guessed parameter, evaluating the binned spectrum at each step and calculating the Full-Width at Half-Maximum (FWHM).
- **Result**: You will be presented with a plot of the sweep and the overlaid spectra. You will be prompted to apply the optimal result. Note that overriding the metadata from the file requires the metadata source to be set to **USER**.

4. The Binning Process
======================

The binning process collapses the 2D detector images into a 1D Energy vs. Intensity spectrum based on Rowland circle geometry.

- **Triggering Processing**: Select a scan and click **Process Binning** (this happens automatically when selecting a new scan or in auto-update mode).
- **Metadata Source**: You can choose where the parameters for binning come from:
  - ``SpecFile``: Read parameters stored directly in the SPEC file header.
  - ``PV``: Read live parameters via EPICS using channel access.
  - ``USER``: Use the manually entered parameters from the left-side property tree.
- **Binning Steps**: 
  1. For each frame, it sums the intensity across the defined vertical ROI (``Ylow`` to ``Yhigh``).
  2. The pixel numbers are mapped onto a calibrated energy axis using the incident energy, reference pixel (``RefL``), backscattering energy (``Eb``), Rowland radius (``Ra``), and effective pixel size (``DeltaD``).
  3. The individual frames are interpolated onto a common energy grid and summed/averaged to build the final spectrum.

5. Exporting Data
=================

You may save the processed, 1D binned spectra to disk for external analysis.

- **Save**: Click the **Save** button in the lower-left corner.
- **File Location**: By default, the result is written alongside the original SPEC file, named ``<original_spec_filename>_bindata_rixsviewer.spec``.
- **Format**: The file uses the standard SPEC format. Each saved spectrum is a new scan with standard headers (e.g., ``#S``, ``#L``). 
- **Columns**: The saved data generally includes ``Energy``, ``Intensity`` (normalized), ``Error``, ``Signal``, and ``Norm`` (total counts).

6. GUI Navigation (Scans and Frames)
====================================

The user interface is broken up into several interactable views.

- **Select Dataset**: The top pane contains a scan table displaying the Scan Number, Type, SPEC Points, and TIFF Points. Click any row to load and display that specific scan.
- **Select Frames**: Once a scan dataset is loaded, a 2D view of the detector is displayed on the right. Below this view is a horizontal slider. Use this slider to scroll through the individual detector frames (TIFF images) contained within the scan.
- By default, selecting a new dataset resets the frame view to the middle frame of the scan.
