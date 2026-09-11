# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.binning_model import RixsBinningModel


def test_tilt_angle_has_a_pv_assigned():
    model = RixsBinningModel()
    pv_by_name = dict((name, pv) for pv, name in model.pv_info)
    assert pv_by_name.get("TiltAngle") == "27idmot1:TiltAngle"
