import tifffile
import numpy


class RixsBinningModel:
    def __init__(self):
        self.params = self.get_parameters()

    def get_parameters(self):
        # Parameters formatted for pyqtgraph ParameterTree
        params = [
            {
                "name": "Ylow",
                "type": "int",
                "value": 0,
                "suffix": " pixel",
                "tip": "The minimum Y pixel to include in the spectra",
                "pv": "none",
            },
            {
                "name": "Yhigh",
                "type": "int",
                "value": 0,
                "suffix": " pixel",
                "tip": "The maximum Y pixel to include in the spectra",
                "pv": "none",
            },
            {
                "name": "RefL",
                "type": "float",
                "value": 0,
                "suffix": " pixel",
                "tip": "Pixel number in the center of the energy dispersion on the lambda detector",
                "pv": "none",
            },
            {
                "name": "Acrystalsize",
                "type": "float",
                "value": 0,
                "suffix": " mm",
                "tip": "Dice size of analyzer",
                "pv": "none",
            },
            {
                "name": "Eb",
                "type": "float",
                "value": 0,
                "suffix": " keV",
                "tip": "Backscattering energy of analyzer",
                "pv": "27idmot1:Merix_E0",
            },
            {
                "name": "Ra",
                "type": "float",
                "value": 0,
                "suffix": " mm",
                "tip": "Radius of Rowland circle",
                "pv": "27idmot1:Merix_RA",
            },
            {
                "name": "DeltaD",
                "type": "float",
                "value": 0,
                "suffix": " mm",
                "tip": "Detector pixel width in the energy dispersion direction",
                "pv": "none",
            },
            {
                "name": "E",
                "type": "float",
                "value": 0,
                "suffix": " keV",
                "tip": "Current energy of analyzer",
                "pv": "27idmot1:Merix_E.VAL",
            },
            {
                "name": "ThetaB",
                "type": "float",
                "value": 0,
                "suffix": " μrad",
                "tip": "Bragg angle of analyzer",
                "pv": "27idmot1:Merix_Theta.VAL",
            },
        ]
        return params


class RixsTiffImage:
    def __init__(self, fname):
        self.fname = fname
        self._image = tifffile.imread(fname)

    def get_image(self):
        return self._image

    def model(self):
        pass
