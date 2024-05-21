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

    
def animate_p1(run_time, decision_interval):
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
    #writer = animation.FFMpegFileWriter(fps=int(1/(2*decision_interval)))
    # ani.save('p1_signal.mp4', writer='ffmpeg', fps=int(1/(2*decision_interval)))

    plt.show()
    
    
def animation_odor(obs_history, timestep, odor_dimensions):
    import pickle
    new_obs_history = None
    with open("obs_history_attractive.pkl", "rb") as f:
        new_obs_history = pickle.load(f)

    print("Loaded")
    obs_history = new_obs_history[::100]
    
    timestep = timestep * 100
    
    odor_history_fly0 = [np.average(obs_history[i]["male"]["odor_intensity"].reshape((odor_dimensions, 2, 2)), axis=1) for i in range(len(obs_history))]
    odor_l_history = [odor_history_fly0[i][:, 0] for i in range(len(odor_history_fly0))]
    odor_r_history = [odor_history_fly0[i][:, 1] for i in range(len(odor_history_fly0))]

    odor_history_fly1 = [np.average(obs_history[i]["female"]["odor_intensity"].reshape((odor_dimensions, 2, 2)), axis=1) for i in range(len(obs_history))]
    odor_l_history_fly1 = [odor_history_fly1[i][:, 0] for i in range(len(odor_history_fly1))]
    odor_r_history_fly1 = [odor_history_fly1[i][:, 1] for i in range(len(odor_history_fly1))]

    plot_odor_l = np.array(odor_l_history)
    male_odor_l_att = plot_odor_l[:, 0]
    male_odor_l_av = plot_odor_l[:, 1]
    plot_odor_r = np.array(odor_r_history)
    male_odor_r_att = plot_odor_r[:, 0]
    male_odor_r_av = plot_odor_r[:, 1]
    
    fig, ax = plt.subplots(1, 2, figsize=(16, 9), tight_layout=True)
    time = np.linspace(0, (timestep*len(odor_history_fly0)), len(odor_history_fly0))
    
    ax[0].title.set_text("Odor intensity fly 0 (male)")
    line1 = ax[0].plot(time[0], male_odor_l_att[0], label=["att_l"])[0]
    line2 = ax[0].plot(time[0], male_odor_l_av[0], label=["av_l"])[0]
    line3 = ax[0].plot(time[0], male_odor_r_att[0], label=["att_r"])[0]
    line4 = ax[0].plot(time[0], male_odor_r_av[0], label=["av_r"])[0]
    
    ax[0].set_xlabel("Time [s]")
    ax[0].set_ylabel("Odor intensity")
    ax[0].set(xlim=[-0.2, time[-1]+0.2], ylim=[-0.005, np.max(odor_l_history) + 0.005])
    ax[0].legend()

    plot_odor_l = np.array(odor_l_history_fly1)
    female_odor_l_att = plot_odor_l[:, 0]
    female_odor_l_av = plot_odor_l[:, 1]
    plot_odor_r = np.array(odor_r_history_fly1)
    female_odor_r_att = plot_odor_r[:, 0]
    female_odor_r_av = plot_odor_r[:, 1]
    
    ax[1].title.set_text("Odor intensity fly 1 (female)")
    line5 = ax[1].plot(time[0], female_odor_l_att[0], label=["att_l"])[0]
    line6 = ax[1].plot(time[0], female_odor_l_av[0], label=["av_l"])[0]
    line7 = ax[1].plot(time[0], female_odor_r_att[0], label=["att_r"])[0]
    line8 = ax[1].plot(time[0], female_odor_r_av[0], label=["av_r"])[0]
    
    ax[1].set_xlabel("Time [s]")
    ax[1].set_ylabel("Odor intensity")
    ax[1].set(xlim=[-0.2, time[-1]+0.2], ylim=[-0.005, np.max(odor_l_history) + 0.005])
    ax[1].legend()  

    print(f"total frames: {len(obs_history)}")
    def update(frame):
        # update the line plot:
        # print fram/total frames with return carriage
        print(f"\r{frame}/{len(obs_history)}", end="")
        line1.set_xdata(time[:frame])
        line1.set_ydata(male_odor_l_att[:frame])
        line2.set_xdata(time[:frame])
        line2.set_ydata(male_odor_l_av[:frame])
        line3.set_xdata(time[:frame])
        line3.set_ydata(male_odor_r_att[:frame])
        line4.set_xdata(time[:frame])
        line4.set_ydata(male_odor_r_av[:frame])
        
        line5.set_xdata(time[:frame])
        line5.set_ydata(female_odor_l_att[:frame])
        line6.set_xdata(time[:frame])
        line6.set_ydata(female_odor_l_av[:frame])
        line7.set_xdata(time[:frame])
        line7.set_ydata(female_odor_r_att[:frame])
        line8.set_xdata(time[:frame])
        line8.set_ydata(female_odor_r_av[:frame])
        
        return (line1, line2, line3, line4, line5, line6, line7, line8)


    print("Animating")
    ani = animation.FuncAnimation(fig=fig, func=update, frames=len(obs_history), interval=2*timestep*1000)


    # save the animation to mp4
    writer = animation.FFMpegFileWriter(fps=int(1/(2*timestep)))
    ani.save('odor_intensities_animated_attractive.mp4', writer='ffmpeg', fps=int(1/(2*timestep)))
    
    # plt.show()
    
# animation_odor(None, timestep, 2)