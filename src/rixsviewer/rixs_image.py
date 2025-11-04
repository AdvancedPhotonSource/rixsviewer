import tifffile
import numpy


class RixsBinningModel:
    def __init__(self):
        self.params = self.get_parameters()
        self.params_map = {}
        for index, param in enumerate(self.params):
            self.params_map[param["name"]] = index

    def get_parameter(self, name):
        return self.params[self.params_map[name]]["value"]

    def update_from_parameter(self, param, changes):
        """Update model attributes when parameter tree values change"""
        for param, change, data in changes:
            if change == "value":
                param_name = param.name()
                if param_name in self.params_map:
                    self.params[self.params_map[param_name]]["value"] = data

    def get_parameters(self):
        # Parameters formatted for pyqtgraph ParameterTree
        params = [
            {
                "name": "threshold",
                "type": "int",
                "value": 192,
                "suffix": " cts",
                "tip": "The threshold for the intensity; pixels above this value are ignored",
                "pv": "none",
            },
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
                "value": 256,
                "suffix": " pixel",
                "tip": "The maximum Y pixel to include in the spectra",
                "pv": "none",
            },
            {
                "name": "RefL",
                "type": "float",
                "value": 128,
                "suffix": " pixel",
                "tip": "Pixel number in the center of the energy dispersion on the lambda detector",
                "pv": "none",
            },
            {
                "name": "Acrystalsize",
                "type": "float",
                "value": 1.0,
                "suffix": " mm",
                "tip": "Dice size of analyzer",
                "pv": "none",
            },
            {
                "name": "Eb",
                "type": "float",
                "value": 10,
                "suffix": " keV",
                "tip": "Backscattering energy of analyzer",
                "pv": "27idmot1:Merix_E0",
            },
            {
                "name": "Ra",
                "type": "float",
                "value": 3.0,
                "suffix": " mm",
                "tip": "Radius of Rowland circle",
                "pv": "27idmot1:Merix_RA",
            },
            {
                "name": "DeltaD",
                "type": "float",
                "value": 55e-3,
                "suffix": " mm",
                "tip": "Detector pixel width in the energy dispersion direction",
                "pv": "none",
            },
            {
                "name": "E",
                "type": "float",
                "value": 10.0,
                "suffix": " keV",
                "tip": "Current energy of analyzer",
                "pv": "27idmot1:Merix_E.VAL",
            },
            {
                "name": "ThetaB",
                "type": "float",
                "value": 30.0,
                "suffix": " μrad",
                "tip": "Bragg angle of analyzer",
                "pv": "27idmot1:Merix_Theta.VAL",
            },
        ]
        return params
