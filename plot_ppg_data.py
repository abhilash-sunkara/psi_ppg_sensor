import tkinter as tk
import numpy as np
import time
import asyncio
import threading
import queue
import csv
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from bleak import BleakScanner
from polar_python import PolarDevice

MAC_ADDRESS = "A0:9E:1A:C5:31:04"

# Queue to pass data from ppg background thread to gui thread
# Thread safe to prevent dropped packets if gui tries to read while ppg thread is updating it
data_queue = queue.Queue()
is_running = True 

start_time = None
csv_writer = None
csv_file_handle = None

sample_count = 0  

# Async handler to deal with ppg data and push to queue
def ppg_handler(data):
    global sample_count

    # BLE devices don't continuously send data but instead bundle them into packets
    # Using the normal timestamp gives each packet the same time which wouldn't work for gui and data processing
    # Polar verity always samples at 55hz so tracking sample count and calculating from that gives an accurate time

    # Iterate through the batch of samples
    for sample in data.samples:
        led1, led2, led3, ambient = sample[0], sample[1], sample[2], sample[3]
        
        # Calculate exact timestamp: 1 second / 55 samples = ~0.01818 seconds per sample
        current_time = sample_count * (1.0 / 55.0)
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
        
        csv_file_handle = open("ppg_data_log.csv", mode="w", newline="")
        csv_writer = csv.writer(csv_file_handle)
        csv_writer.writerow(["Time", "Led 1", "Led 2", "Led 3", "Ambient Light"])

        # start stream, 55 is hertz, 22 is bit resolution, 4 is number of channels
        await polar.start_ppg_stream(ppg_handler, 55, 22, 4)
            
        try:
            while is_running:
                await asyncio.sleep(0.1)
        finally:
            print("Stopping stream...")
            await polar.stop_ppg_stream()
            csv_file_handle.close()
            print("Disconnected and saved CSV.")

# creates a new async thread and runs ble_loop() until it ends
# ble_loop() only ends when is_running is set to false when tkinter gui is closed
def start_ble_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ble_loop())

root = tk.Tk()
root.title("Polar PPG Stream")
root.geometry("800x500")

fig = Figure(figsize=(8, 5), dpi=100)
ax = fig.add_subplot(111)

WINDOW_SIZE = 1000  
x_data = np.arange(WINDOW_SIZE)

y_data1 = np.full(WINDOW_SIZE, np.nan)
y_data2 = np.full(WINDOW_SIZE, np.nan)
y_data3 = np.full(WINDOW_SIZE, np.nan)
y_data4 = np.full(WINDOW_SIZE, np.nan)

ax.set_xlim(0, WINDOW_SIZE)
ax.set_ylim(0, 100000)  
ax.grid(True)

line1, = ax.plot(x_data, y_data1, animated=True, color='red', label='LED 1')
line2, = ax.plot(x_data, y_data2, animated=True, color='green', label='LED 2')
line3, = ax.plot(x_data, y_data3, animated=True, color='blue', label='LED 3')
line4, = ax.plot(x_data, y_data4, animated=True, color='orange', label='Ambient')
ax.legend(loc="upper right")

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

canvas.draw()
background = canvas.copy_from_bbox(ax.bbox)

def update_graph():
    global background

    # Moves old data to left and puts new data to the end of the graph to make the scrolling animation
    # updates_made allows for gui loop to only update if new data is detected
    updates_made = False
    while not data_queue.empty():
        led1, led2, led3, ambient = data_queue.get()
        
        y_data1[:-1], y_data2[:-1], y_data3[:-1], y_data4[:-1] = y_data1[1:], y_data2[1:], y_data3[1:], y_data4[1:]
        
        y_data1[-1], y_data2[-1], y_data3[-1], y_data4[-1] = led1, led2, led3, ambient
        updates_made = True

    if updates_made:
        if np.isnan(y_data1[-1]):
            root.after(20, update_graph)
            return

        # mean centering algorithm removes the baseline offset of the light and shows the fluctuations
        # which is the actual "flow of blood" that affects the light
        disp_y1 = y_data1 - np.nanmean(y_data1)
        disp_y2 = y_data2 - np.nanmean(y_data2)
        disp_y3 = y_data3 - np.nanmean(y_data3)
        disp_y4 = y_data4 - np.nanmean(y_data4)


        # Dynamic scaling to check if window needs to resize the y-axis
        current_ymin, current_ymax = ax.get_ylim()
        min_val = min(np.nanmin(disp_y1), np.nanmin(disp_y2), np.nanmin(disp_y3), np.nanmin(disp_y4))
        max_val = max(np.nanmax(disp_y1), np.nanmax(disp_y2), np.nanmax(disp_y3), np.nanmax(disp_y4))
        
        margin = max(abs(max_val - min_val) * 0.2, 100)
        
        if max_val > current_ymax or min_val < current_ymin:
            ax.set_ylim(min_val - margin, max_val + margin)
            canvas.draw()
            background = canvas.copy_from_bbox(ax.bbox)

        # Adds new data into matplotlib line data
        line1.set_ydata(disp_y1)
        line2.set_ydata(disp_y2)
        line3.set_ydata(disp_y3)
        line4.set_ydata(disp_y4)

        # Only redraws the plot lines not the plot background, grid or axes
        canvas.restore_region(background)
        ax.draw_artist(line1)
        ax.draw_artist(line2)
        ax.draw_artist(line3)
        ax.draw_artist(line4)
        canvas.blit(ax.bbox)
        canvas.flush_events()
        
    root.after(20, update_graph)

# intercepts close button and safely closes csv connection 
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

# starts ble and gui loops
ble_thread = threading.Thread(target=start_ble_thread, daemon=True)
ble_thread.start()

update_graph()
root.mainloop()