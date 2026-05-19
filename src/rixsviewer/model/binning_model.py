from epics import caget_many

from .process_parameters import params


class RixsBinningModel:
    """
    Model class for managing RIXS binning parameters.

    This class handles the retrieval and storage of binning parameters,
    either from standard definitions or directly from PVs.
    """

    def __init__(self):
        """Initialize the RixsBinningModel and param map."""
        self.params = params
        self.params_map = {}
        for index, param in enumerate(self.params):
            self.params_map[param["name"]] = index
        self.pv_info = [(p["pv"], p["name"]) for p in self.params if p["pv"] != "none"]

    def get_kwargs(self):
        """
        Get current parameter values as a dictionary for processing.

        Returns
        -------
        dict
            A dictionary containing the current binning parameters.
        """
        kwargs = {}
        for param in self.params:
            kwargs[param["name"]] = self._get_single_parameter(param["name"])
        return kwargs

    def put_kwargs(self, kwargs):
        """
        Update multiple parameters in the model.

        Parameters
        ----------
        kwargs : dict
            A dictionary of parameter names and their new values.
        """
        for name, value in kwargs.items():
            self.put_single_parameter(name, value)

    def get_kwargs_from_pv(self, timeout=0.05):
        """
        Retrieve parameters from their associated PVs.

        Parameters
        ----------
        timeout : float, optional
            Timeout for the PV connection in seconds. Default is 0.05.

        Returns
        -------
        dict
            A dictionary of updated parameter values.
        """
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
        """
        Get the value of a single parameter.

        Parameters
        ----------
        name : str
            The name of the parameter.

        Returns
        -------
        any
            The value of the parameter.
        """
        return self.params[self.params_map[name]]["value"]

    def put_single_parameter(self, name, value):
        """
        Update a single parameter value in the model.

        Parameters
        ----------
        name : str
            Parameter name to update.
        value : any
            New value for the parameter.
        """
        if name in self.params_map:
            self.params[self.params_map[name]]["value"] = value
        else:
            print(name, "not in params_map")
            print(self.params_map)

    def update_from_parameter(self, param, changes):
        """
        Update model attributes when parameter tree values change.

        Parameters
        ----------
        param : pyqtgraph.parametertree.Parameter
            The parameter object that originated the change.
        changes : list of tuple
            A list of changes, where each change is a tuple of
            (param, change_type, data).
        """
        for param, change, data in changes:
            if change == "value":
                param_name = param.name()
                if param_name in self.params_map:
                    self.params[self.params_map[param_name]]["value"] = data
