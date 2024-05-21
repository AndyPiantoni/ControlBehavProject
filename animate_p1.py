import matplotlib.pyplot as plt
from matplotlib import animation
import numpy as np

timestep = 1e-4
decision_interval = 0.05
run_time = 6

def p1_control_signal(run_time: float, time_step: float) -> np.ndarray:
    """Returns a P1 signal [0,1].
    The control signal is a 2D array of shape (num_time_steps, 2)"""
    
    # P1 signal is a 2D array of shape (num_time_steps, 1)
    p1_signal = np.ones((int(run_time / time_step), 1))
    
    T_high = 1.5  # seconds
    T_low = 0.5  # seconds
    
    # Create a square wave signal with T_high and T_low= T_high/T_ratio
    signal_low = np.zeros(int(T_low / time_step))
    signal_high = np.ones(int(T_high / time_step))
    signal = np.concatenate([signal_high, signal_low])
    num_repeats = int(run_time / time_step / len(signal))
    p1_signal = np.tile(signal, num_repeats)
    # fille up the rest of the signal with ones (resting state)
    p1_signal = np.concatenate([p1_signal, np.ones(int(run_time / time_step) - len(p1_signal))])
    
    
    return p1_signal

def plot_signal(p1_signal, name: str):
    fig, ax = plt.subplots(1, 1, figsize=(5, 4), tight_layout=True)
    ax.plot(np.linspace(0, run_time, int(run_time / decision_interval)), p1_signal)
    ax.set_xlabel("Time[s]")
    ax.set_ylabel(name)
    ax.set_title(name)
    plt.grid()
    
# create subplot with size 16, 9
fig, ax = plt.subplots(1, 1, figsize=(16, 9), tight_layout=True)
plt.title("P1 signal")
p1_signal = p1_control_signal(run_time, decision_interval)
t = np.linspace(0, run_time, len(p1_signal))    


line2 = ax.plot(t[0], p1_signal[0])[0]
ax.set(xlim=[-0.2, 6.2], ylim=[-0.2, 1.2], xlabel='Time [s]', ylabel='P1 signal intensity')
plt.grid()


def update(frame):
    # update the line plot:
    line2.set_xdata(t[:frame])
    line2.set_ydata(p1_signal[:frame])
    return (line2)


ani = animation.FuncAnimation(fig=fig, func=update, frames=len(p1_signal), interval=int(2*decision_interval*1000))


# save the animation to mp4
writer = animation.FFMpegFileWriter(fps=int(1/(2*decision_interval)))
ani.save('p1_signal.mp4', writer='ffmpeg', fps=int(1/(2*decision_interval)))

# plt.show()