I am going to be developing the MCP server to control SMU units, that are compatible with PY visa.

The background for the SMU control is already implemented files "SMU 1_SMU_Direct_Control.py" and "smu_controller.py" located in the root folder of the project.The MCP server will be compatible with the SMU from keysight and keythley. The testing willbe performed on 1 channel SMU B2901A from Keysight. The MCP server should be compatible with 2 channel SMU too

The Ai agent/model should be able to communicate with the MCP server to run the SMU and receive feedback about current status of the SMU, current task running, and receive the data from the SMU.

the MCP server should support following options for measurements:

single point I,V
mode control (current source, voltage source)
IV sweep (current sweep, voltage sweep)
list sweep (current list, voltage list)

paremeters for sweeps:
integration time, number of points, start, stop, step, sweep direction, distribution of points (log, linear)

default mode for IV sweeps is a list sweep, with a pregenerated list of points, and integration time.

the MCP sever should return data in json format.
after it is done, the MCP server should be added to local skills list so the agent can communicate and perform IV sweep.

the MCP server should follow standard practices for functioning MCP servers. it will be running on a local computer, same as future software pieces. 