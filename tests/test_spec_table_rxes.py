# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.rxes_dataset import RixsRxesScanDataset
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline


def test_spec_table_constructs_rxes_dataset_for_rxesscan_rows(tmp_path):
    beamline = FakeBeamline(str(tmp_path))
    beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    beamline.run_scan(2)

    table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)

    assert isinstance(table.record[1], RixsRxesScanDataset)
    assert isinstance(table.record[2], RixsEnergyScanDataset)
