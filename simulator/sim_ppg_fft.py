import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.fft import fft

# Load the saved CSV
df = pd.read_csv("simulated_ppg.csv")

# Optional: Remove DC offset (mean) so the 0 Hz spike doesn't dwarf the heart rate peak
signal = df['PPG'] - np.mean(df['PPG'])

# Compute FFT
X = fft(signal.values)
N = len(X)
n = np.arange(N)

# Get the sampling rate (nk.ppg_simulate defaults to 1000 Hz)
sr = 1000
T = N / sr
freq = n / T

# Get the one-sided spectrum
n_oneside = N // 2
f_oneside = freq[:n_oneside]

# Plot the spectrum
plt.figure(figsize=(12, 6))
plt.plot(f_oneside, np.abs(X[:n_oneside]), 'b')
plt.xlim(0, 10)  # Zoom into 0-10 Hz where physiological PPG frequencies live
plt.xlabel('Freq (Hz)')
plt.ylabel('FFT Amplitude |X(freq)|')
plt.title('One-Sided FFT Spectrum of Simulated PPG')
plt.grid(True, alpha=0.3)
plt.show()