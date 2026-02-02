we should implement a converter from LED current to irradiance in W cm2

calibration is performed as follows:

1. we take a known silicon diode with area xcm . the data for the diode is in SiDiodeResponsivity.csv
2. we place it in the same position as the sample will be 
3. we illuminate it with the LED at different currents (e.g. 0.001, 0.005, 0.01, 0.02, 0.05, 0.1 A)
4. we measure the current from the diode
we calulate irradiance by multiplying the diode current by the responsivity of the diode at the wavelength of the LED
5. we save the calibration data in a file (make file calibration.csv with columns current and irradiance). premade file like this is in there calBLUE.txt

conversion:
in the recipe builder , users should be able to also pick bias irradiance or the bias current. If the irradiance is picked it is converted to LED current using the calibration data, and then the LED current is recorded in tha yaml file

in the protocol runner - the  users also should be able to ovveride the LED current using irradiance or current. 