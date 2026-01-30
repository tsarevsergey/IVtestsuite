as of now we have a version of software that works well with channel 1.
2 channel B2901A : USB0::2391::35864::MY51141849::0::INSTR
we need to implement more complex protocols with 2 channel operation for the SMU 2901B with 2 channels

the order of works

1. please create a backup copy of smu_controller 
2. please adjust the smu_controller based on your best knowledge and internet search to work with two channels
3. perform single measurements at 1V for 1 channel and 2nd channel. get a confirmation with me
onyl proceed after confirmation


4.after that please proceed for modification of basic API  (ivtest\WALKTHROUGHmd6.md, ivtest\WALKTHROUGHstep5.md ) commands to include number of channel

5. we thoroughly test every API if the channel selection works
6. we engineer a double protocol file where channel one turns on a steady voltage (8V) and keeps it during the scan of the second source