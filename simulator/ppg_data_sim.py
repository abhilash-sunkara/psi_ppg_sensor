import numpy as np
import pandas as pd
import neurokit2 as nk
import matplotlib.pyplot as plt

sampling_rate = 1000
duration = 10
ppg = nk.ppg_simulate(duration=duration, sampling_rate=sampling_rate, heart_rate=70)

time = np.linspace(0, duration, len(ppg), endpoint=False)
data = pd.DataFrame({"Time_s": time, "PPG": ppg})

data.to_csv("csv_files/simulated_ppg.csv", index=False)