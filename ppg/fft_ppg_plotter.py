import tkinter as tk
import numpy as np
import time
import asyncio
import threading
import queue
import csv
from scipy.fft import fft
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from bleak import BleakScanner
from polar_python import PolarDevice

MAC_ADDRESS = "A0:9E:1A:C5:31:04"
SAMPLE_RATE = 55.0  

# Queue to pass data from ppg background thread to gui thread
data_queue = queue.Queue()
is_running = True 

start_time = None
csv_writer = None
csv_file_handle = None
sample_count = 0  

def ppg_handler(data):
    global sample_count

    for sample in data.samples:
        led1, led2, led3, ambient = sample[0], sample[1], sample[2], sample[3]
        
        current_time = sample_count * (1.0 / SAMPLE_RATE)
        sample_count += 1
        
        if csv_writer is not None:
            csv_writer.writerow([current_time, led1, led2, led3, ambient])
            
        data_queue.put((led1, led2, led3, ambient))

async def ble_loop():
    global csv_writer, csv_file_handle
    print(f"searching for {MAC_ADDRESS}")
    device = await BleakScanner.find_device_by_address(MAC_ADDRESS)
    
    if not device:
        print("sensor not found")
        return

    async with PolarDevice(device) as polar:
        print("starting PPG stream...\n")
        
        csv_file_handle = open("csv_files/ppg_data_log.csv", mode="w", newline="")
        csv_writer = csv.writer(csv_file_handle)
        csv_writer.writerow(["Time", "Led 1", "Led 2", "Led 3", "Ambient Light"])

        await polar.start_ppg_stream(ppg_handler, 55, 22, 4)
            
        try:
            while is_running:
                await asyncio.sleep(0.1)
        finally:
            print("Stopping stream...")
            await polar.stop_ppg_stream()
            csv_file_handle.close()
            print("Disconnected and saved CSV.")

def start_ble_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ble_loop())

root = tk.Tk()
root.title("Polar PPG Stream & Real-Time FFT (LF Modulation + HR)")
root.geometry("1000x780")

fig = Figure(figsize=(10, 7.5), dpi=100)
fig.subplots_adjust(hspace=0.35)

# sets up subplots, top is time domain, bottom is frequency
ax_time = fig.add_subplot(211)
ax_fft = fig.add_subplot(212)


WINDOW_SIZE = 1024  
FFT_WINDOW = 1024   
N_FFT = 4096        # 55 / 4096 = 0.0134 Hz bin resolution

x_data = np.arange(WINDOW_SIZE)
y_data1 = np.full(WINDOW_SIZE, np.nan)
y_data2 = np.full(WINDOW_SIZE, np.nan)
y_data3 = np.full(WINDOW_SIZE, np.nan)
y_data4 = np.full(WINDOW_SIZE, np.nan)

# precalculate fft bins
n = np.arange(N_FFT)
T = N_FFT / SAMPLE_RATE
freq = n / T
n_oneside = N_FFT // 2
f_oneside = freq[:n_oneside]

# Pre-calculate Hanning window for the 1024-sample data slice
# reduces spectral leakage
hann_win = np.hanning(FFT_WINDOW)

# Configure PPG Plot
ax_time.set_title("Real-Time PPG Signal (Mean-Centered)")
ax_time.set_xlim(0, WINDOW_SIZE)
ax_time.set_ylim(-5000, 5000)
ax_time.set_xlabel("Samples (55 Hz)")
ax_time.set_ylabel("ADC Amplitude")
ax_time.grid(True)

line1, = ax_time.plot(x_data, y_data1, animated=True, color='red', label='LED 1')
line2, = ax_time.plot(x_data, y_data2, animated=True, color='green', label='LED 2')
line3, = ax_time.plot(x_data, y_data3, animated=True, color='blue', label='LED 3')
line4, = ax_time.plot(x_data, y_data4, animated=True, color='orange', label='Ambient')
ax_time.legend(loc="upper right")

# Configure FFT Spectrum
ax_fft.set_title("One-Sided FFT Spectrum (0.1–0.3 Hz Modulation & 0.7–3.5 Hz HR)")
ax_fft.set_xlim(0, 4.5)  
ax_fft.set_ylim(0, 50000)
ax_fft.set_xlabel("Freq (Hz)")
ax_fft.set_ylabel("FFT Amplitude |X(freq)|")
ax_fft.grid(True)


ax_fft.axvspan(0.1, 0.3, color='cyan', alpha=0.18, label='Resp Band (0.1-0.3 Hz)')
ax_fft.axvspan(0.7, 3.5, color='red', alpha=0.08, label='HR Band (0.7-3.5 Hz)')

fft_zeros = np.zeros(n_oneside)
fft_line1, = ax_fft.plot(f_oneside, fft_zeros, animated=True, color='red', label='LED 1 FFT')
fft_line2, = ax_fft.plot(f_oneside, fft_zeros, animated=True, color='green', label='LED 2 FFT')
fft_line3, = ax_fft.plot(f_oneside, fft_zeros, animated=True, color='blue', label='LED 3 FFT')


status_text = ax_fft.text(
    0.58, 0.78, "Buffering FFT...", transform=ax_fft.transAxes,
    fontsize=10, fontweight='bold', animated=True,
    bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
)
ax_fft.legend(loc="upper right", fontsize=8)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

canvas.draw()
bg_time = canvas.copy_from_bbox(ax_time.bbox)
bg_fft = canvas.copy_from_bbox(ax_fft.bbox)

def on_resize(event):
    global bg_time, bg_fft
    canvas.draw()
    bg_time = canvas.copy_from_bbox(ax_time.bbox)
    bg_fft = canvas.copy_from_bbox(ax_fft.bbox)

canvas.mpl_connect('resize_event', on_resize)

def update_graph():
    global bg_time, bg_fft

    updates_made = False
    while not data_queue.empty():
        led1, led2, led3, ambient = data_queue.get()
        
        y_data1[:-1], y_data2[:-1], y_data3[:-1], y_data4[:-1] = (
            y_data1[1:], y_data2[1:], y_data3[1:], y_data4[1:]
        )
        y_data1[-1], y_data2[-1], y_data3[-1], y_data4[-1] = led1, led2, led3, ambient
        updates_made = True

    if updates_made:
        if np.isnan(y_data1[-1]):
            root.after(20, update_graph)
            return

    
        disp_y1 = y_data1 - np.nanmean(y_data1)
        disp_y2 = y_data2 - np.nanmean(y_data2)
        disp_y3 = y_data3 - np.nanmean(y_data3)
        disp_y4 = y_data4 - np.nanmean(y_data4)

        current_ymin, current_ymax = ax_time.get_ylim()
        min_val = min(np.nanmin(disp_y1), np.nanmin(disp_y2), np.nanmin(disp_y3), np.nanmin(disp_y4))
        max_val = max(np.nanmax(disp_y1), np.nanmax(disp_y2), np.nanmax(disp_y3), np.nanmax(disp_y4))
        margin = max(abs(max_val - min_val) * 0.2, 100)
        
        rescale_needed = False
        if max_val > current_ymax or min_val < current_ymin or (max_val - min_val) < (current_ymax - current_ymin) * 0.8:
            ax_time.set_ylim(min_val - margin, max_val + margin)
            rescale_needed = True

        line1.set_ydata(disp_y1)
        line2.set_ydata(disp_y2)
        line3.set_ydata(disp_y3)
        line4.set_ydata(disp_y4)

        # checks the amount of readings that are actual data 
        valid_count = np.sum(~np.isnan(y_data1))

        # Only generates fft if minimum sample size is reached
        if valid_count >= FFT_WINDOW:
            # gets last FFT_WINDOW number of samples
            win1 = y_data1[-FFT_WINDOW:]
            win2 = y_data2[-FFT_WINDOW:]
            win3 = y_data3[-FFT_WINDOW:]

            # mean centers and multiples hanning window
            sig1 = (win1 - np.mean(win1)) * hann_win
            sig2 = (win2 - np.mean(win2)) * hann_win
            sig3 = (win3 - np.mean(win3)) * hann_win

            # Runs fft on window/signal
            # Gets abs val of fft data
            X1 = np.abs(fft(sig1, n=N_FFT)[:n_oneside])
            X2 = np.abs(fft(sig2, n=N_FFT)[:n_oneside])
            X3 = np.abs(fft(sig3, n=N_FFT)[:n_oneside])

            fft_line1.set_ydata(X1)
            fft_line2.set_ydata(X2)
            fft_line3.set_ydata(X3)

            # rescaling code for max and min
            scale_mask = f_oneside >= 0.08
            fft_ymin, fft_ymax = ax_fft.get_ylim()
            max_fft = max(np.max(X1[scale_mask]), np.max(X2[scale_mask]), np.max(X3[scale_mask]), 100)
            if max_fft > fft_ymax or max_fft < fft_ymax * 0.8:
                ax_fft.set_ylim(0, max_fft * 1.25)
                rescale_needed = True
        
            

        if rescale_needed:
            canvas.draw()
            bg_time = canvas.copy_from_bbox(ax_time.bbox)
            bg_fft = canvas.copy_from_bbox(ax_fft.bbox)

        
        canvas.restore_region(bg_time)
        ax_time.draw_artist(line1)
        ax_time.draw_artist(line2)
        ax_time.draw_artist(line3)
        ax_time.draw_artist(line4)
        canvas.blit(ax_time.bbox)

       
        canvas.restore_region(bg_fft)
        ax_fft.draw_artist(fft_line1)
        ax_fft.draw_artist(fft_line2)
        ax_fft.draw_artist(fft_line3)
        ax_fft.draw_artist(status_text)
        canvas.blit(ax_fft.bbox)

        canvas.flush_events()
        
    root.after(20, update_graph)

def on_closing():
    global is_running
    print("Shutting down...")
    is_running = False
    
    def check_thread():
        if ble_thread.is_alive():
            root.after(100, check_thread)
        else:
            root.destroy()
            
    check_thread()

root.protocol("WM_DELETE_WINDOW", on_closing)

ble_thread = threading.Thread(target=start_ble_thread, daemon=True)
ble_thread.start()

update_graph()
root.mainloop()