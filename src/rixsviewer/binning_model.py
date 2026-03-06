import numpy as np
import tifffile
from epics import caget, caget_many

from .process_parameters import params


class RixsBinningModel:
    def __init__(self):
        self.params = params
        self.params_map = {}
        for index, param in enumerate(self.params):
            self.params_map[param["name"]] = index
        self.param_tree = None  # Will be set by GUI to enable UI updates
        self.pv_info = [(p["pv"], p["name"]) for p in self.params if p["pv"] != "none"]

    def get_kwargs(self):
        """Get current parameter values as a dictionary for processing"""
        kwargs = {}
        for param in self.params:
            kwargs[param["name"]] = self._get_single_parameter(param["name"])
        return kwargs

    def put_kwargs(self, kwargs):
        for name, value in kwargs.items():
            self.put_single_parameter(name, value)

    def get_kwargs_from_pv(self, timeout=0.05):
        pvs, names = zip(*self.pv_info)
        values = caget_many(list(pvs), timeout=timeout, connection_timeout=timeout)

        for name, value in zip(names, values):
            # update the UI parameter tree if it's connected
            if name in ("Ylow", "Yhigh", "RefL"):
                value = int(value)
            if value is not None:
                self.put_single_parameter(name, value)
        return self.get_kwargs()

    def _get_single_parameter(self, name):
        return self.params[self.params_map[name]]["value"]

    def put_single_parameter(self, name, value):
        """Update a parameter value by name and sync with UI if connected

        Args:
            name: Parameter name to update
            value: New value for the parameter
        """
        if name in self.params_map:
            self.params[self.params_map[name]]["value"] = value
            # Update the UI parameter tree if it's connected
            if self.param_tree is not None:
                param = self.param_tree.child(name)
                if param is not None:
                    param.setValue(value)
        else:
            print(name, "not in params_map")
            print(self.params_map)

    def update_from_parameter(self, param, changes):
        """Update model attributes when parameter tree values change"""
        for param, change, data in changes:
            if change == "value":
                param_name = param.name()
                if param_name in self.params_map:
                    self.params[self.params_map[param_name]]["value"] = data
