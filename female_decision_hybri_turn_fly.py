import numpy as np
from tqdm import trange
from gymnasium import spaces
from gymnasium.utils.env_checker import check_env

# from flygym.simulation import Fly
from abdomen_fly import AbdomenFly
from flygym.examples.common import PreprogrammedSteps
from flygym.examples.cpg_controller import CPGNetwork
from flygym.preprogrammed import get_cpg_biases


_tripod_phase_biases = get_cpg_biases("tripod")
_tripod_coupling_weights = (_tripod_phase_biases > 0) * 10
_default_correction_vectors = {
    "F": np.array([0, 0, 0, -0.02, 0, 0.016, 0]),
    "M": np.array([-0.015, 0, 0, 0.004, 0, 0.01, -0.008]),
    "H": np.array([0, 0, 0, -0.01, 0, 0.005, 0]),
}
_default_correction_rates = {"retraction": (500, 1000 / 3), "stumbling": (2000, 500)}
_contact_sensor_placements = tuple(
    f"{leg}{segment}"
    for leg in ["LF", "LM", "LH", "RF", "RM", "RH"]
    for segment in ["Tibia", "Tarsus1", "Tarsus2", "Tarsus3", "Tarsus4", "Tarsus5"]
)


class FemaleDecisionHybriTurnFly(AbdomenFly):
    def __init__(
        self,
        timestep,
        preprogrammed_steps=None,
        odor_dimensions=2,                    # relative to odor
        odor_threshold=[0.119, 0.03],        # relative to odor
        odor_own_smelling=0.1,                # relative to odor
        intrinsic_freqs=np.ones(6) * 12,
        intrinsic_amps=np.ones(6) * 1,
        phase_biases=_tripod_phase_biases,
        coupling_weights=_tripod_coupling_weights,
        convergence_coefs=np.ones(6) * 20,
        init_phases=None,
        init_magnitudes=None,
        stumble_segments=("Tibia", "Tarsus1", "Tarsus2"),
        stumbling_force_threshold=-1,
        correction_vectors=_default_correction_vectors,
        correction_rates=_default_correction_rates,
        amplitude_range=(-0.5, 1.5),
        draw_corrections=False,
        contact_sensor_placements=_contact_sensor_placements,
        seed=0,
        **kwargs,
    ):
        # Initialize core NMF simulation
        super().__init__(contact_sensor_placements=contact_sensor_placements, **kwargs)

        if preprogrammed_steps is None:
            preprogrammed_steps = PreprogrammedSteps()

        self.preprogrammed_steps = preprogrammed_steps
        self.intrinsic_freqs = intrinsic_freqs
        self.intrinsic_amps = intrinsic_amps
        self.phase_biases = phase_biases
        self.coupling_weights = coupling_weights
        self.convergence_coefs = convergence_coefs
        self.stumble_segments = stumble_segments
        self.stumbling_force_threshold = stumbling_force_threshold
        self.correction_vectors = correction_vectors
        self.correction_rates = correction_rates
        self.amplitude_range = amplitude_range
        self.draw_corrections = draw_corrections

        # Relative to odor
        self.odor_dimensions = odor_dimensions
        self.odor_threshold = odor_threshold
        self.odor_own_smelling = odor_own_smelling

        self.time_since_odor_high = 0

        # Define action and observation spaces
        self.action_space = spaces.Box(*amplitude_range, shape=(2,))

        # Initialize CPG network
        self.cpg_network = CPGNetwork(
            timestep=timestep,
            intrinsic_freqs=intrinsic_freqs,
            intrinsic_amps=intrinsic_amps,
            coupling_weights=coupling_weights,
            phase_biases=phase_biases,
            convergence_coefs=convergence_coefs,
            seed=seed,
        )
        self.cpg_network.reset(init_phases, init_magnitudes)

        # Initialize variables tracking the correction amount
        self.retraction_correction = np.zeros(6)
        self.stumbling_correction = np.zeros(6)

        # Find stumbling sensors
        self.stumbling_sensors = self._find_stumbling_sensor_indices()

        # Start by being a Hybrid Turning Fly
        self.hybrid_turning = True

    @property
    def timestep(self):
        return self.cpg_network.timestep

    def _find_stumbling_sensor_indices(self):
        stumbling_sensors = {leg: [] for leg in self.preprogrammed_steps.legs}
        for i, sensor_name in enumerate(self.contact_sensor_placements):
            leg = sensor_name.split("/")[1][:2]  # sensor_name: e.g. "Animat/LFTarsus1"
            segment = sensor_name.split("/")[1][2:]
            if segment in self.stumble_segments:
                stumbling_sensors[leg].append(i)
        stumbling_sensors = {k: np.array(v) for k, v in stumbling_sensors.items()}
        if any(
            v.size != len(self.stumble_segments) for v in stumbling_sensors.values()
        ):
            raise RuntimeError(
                "Contact detection must be enabled for all tibia, tarsus1, and tarsus2 "
                "segments for stumbling detection."
            )
        return stumbling_sensors

        
    def _retraction_rule_find_leg(self, obs):
        """Returns the index of the leg that needs to be retracted, or None
        if none applies."""
        end_effector_z_pos = obs["fly"][0][2] - obs["end_effectors"][:, 2]
        end_effector_z_pos_sorted_idx = np.argsort(end_effector_z_pos)
        end_effector_z_pos_sorted = end_effector_z_pos[end_effector_z_pos_sorted_idx]
        if end_effector_z_pos_sorted[-1] > end_effector_z_pos_sorted[-3] + 0.05:
            leg_to_correct_retraction = end_effector_z_pos_sorted_idx[-1]
        else:
            leg_to_correct_retraction = None
        return leg_to_correct_retraction

    def _stumbling_rule_check_condition(self, obs, leg):
        """Return True if the leg is stumbling, False otherwise."""
        # update stumbling correction amounts
        contact_forces = obs["contact_forces"][self.stumbling_sensors[leg], :]
        fly_orientation = obs["fly_orientation"]
        # force projection should be negative if against fly orientation
        force_proj = np.dot(contact_forces, fly_orientation)
        return (force_proj < self.stumbling_force_threshold).any()

    def _get_net_correction(self, retraction_correction, stumbling_correction):
        """Retraction correction has priority."""
        if retraction_correction > 0:
            return retraction_correction
        return stumbling_correction

    def _update_correction_amount(
        self, condition, curr_amount, correction_rates, viz_segment
    ):
        """Update correction amount and color code leg segment.

        Parameters
        ----------
        condition : bool
            Whether the correction condition is met.
        curr_amount : float
            Current correction amount.
        correction_rates : Tuple[float, float]
            Correction rates for increment and decrement.
        viz_segment : str
            Name of the segment to color code. If None, no color coding is
            done.

        Returns
        -------
        float
            Updated correction amount.
        """
        if condition:  # lift leg
            increment = correction_rates[0] * self.timestep
            new_amount = curr_amount + increment
            color = (0, 1, 0, 1)
        else:  # condition no longer met, lower leg
            decrement = correction_rates[1] * self.timestep
            new_amount = max(0, curr_amount - decrement)
            color = (1, 0, 0, 1)
        if viz_segment is not None:
            self.change_segment_color(viz_segment, color)
        return new_amount

    def reset(self, sim, seed=None, init_phases=None, init_magnitudes=None, **kwargs):
        obs, info = super().reset(sim, seed=seed, **kwargs)
        self.cpg_network.random_state = np.random.RandomState(seed)
        self.cpg_network.intrinsic_amps = self.intrinsic_amps
        self.cpg_network.intrinsic_freqs = self.intrinsic_freqs
        self.cpg_network.reset(init_phases, init_magnitudes)
        self.retraction_correction = np.zeros(6)
        self.stumbling_correction = np.zeros(6)
        return obs, info

    def pre_step(self, action, sim):
        """Step the simulation forward one timestep.

        Parameters
        ----------
        action : np.ndarray
            Array of shape (2,) containing descending signal encoding
            turning.
        """
        
        # make sure action shape is correct for hybrid turning or normal joint control
        if not self.hybrid_turning:
            assert isinstance(action, dict) and len(action)==2, f"Action must be a dictionary and of length 2, got {type(action)}."
            return super().pre_step(action, sim)
        else:
            assert action.shape == (2,), f"Action shape must be (2,), got {action.shape}."
            
        
        physics = sim.physics

        # update CPG parameters
        amps = np.repeat(np.abs(action[:, np.newaxis]), 3, axis=1).ravel()
        freqs = self.intrinsic_freqs.copy()
        freqs[:3] *= 1 if action[0] > 0 else -1
        freqs[3:] *= 1 if action[1] > 0 else -1
        self.cpg_network.intrinsic_amps = amps
        self.cpg_network.intrinsic_freqs = freqs

        # get current observation
        obs = super().get_observation(sim)

        # Retraction rule: is any leg stuck in a gap and needing to be retracted?
        leg_to_correct_retraction = self._retraction_rule_find_leg(obs)

        self.cpg_network.step()

        joints_angles = []
        adhesion_onoff = []
        for i, leg in enumerate(self.preprogrammed_steps.legs):
            # update retraction correction amounts
            self.retraction_correction[i] = self._update_correction_amount(
                condition=(i == leg_to_correct_retraction),
                curr_amount=self.retraction_correction[i],
                correction_rates=self.correction_rates["retraction"],
                viz_segment=f"{leg}Tibia" if self.draw_corrections else None,
            )
            # update stumbling correction amounts
            self.stumbling_correction[i] = self._update_correction_amount(
                condition=self._stumbling_rule_check_condition(obs, leg),
                curr_amount=self.stumbling_correction[i],
                correction_rates=self.correction_rates["stumbling"],
                viz_segment=f"{leg}Femur" if self.draw_corrections else None,
            )
            # get net correction amount
            net_correction = self._get_net_correction(
                self.retraction_correction[i], self.stumbling_correction[i]
            )

            # get target angles from CPGs and apply correction
            my_joints_angles = self.preprogrammed_steps.get_joint_angles(
                leg,
                self.cpg_network.curr_phases[i],
                self.cpg_network.curr_magnitudes[i],
            )
            my_joints_angles += net_correction * self.correction_vectors[leg[1]]
            joints_angles.append(my_joints_angles)

            # get adhesion on/off signal
            my_adhesion_onoff = self.preprogrammed_steps.get_adhesion_onoff(
                leg, self.cpg_network.curr_phases[i]
            )
            adhesion_onoff.append(my_adhesion_onoff)
        joints_angles = np.array(np.concatenate(joints_angles)).flatten()  
        
        # add joint angles for abdomen joints (A1A2, A3, A4, A5, A6)
        for _ in ["A1A2", "A3", "A4", "A5", "A6"]:
            joints_angles = np.append(joints_angles, 0)
        action = {
            "joints":joints_angles,
            "adhesion": np.array(adhesion_onoff).astype(int),
        }
        return super().pre_step(action, sim)
    
    def set_hybrid_turning(self, hybrid_turning):
        """
        Set the hybrid turning mode. hybrid_turning is a boolean variable
        """
        self.hybrid_turning = hybrid_turning

    def get_hybrid_turning(self):
        return self.hybrid_turning
    
    def get_female_mating_decision(self, odor_intensities, timestep, time_before_decision=1.0):
        """
        Returns a decision based on the odor intensities.
        The decision can be one of the following: 
         - "reject" : if aversive odor is detected
         - "accept" : if attractive odor is detected
         - "fly_close_but_no_decision" : if attractive odor is detected but not enough to make a decision
         - "fly_nearby" : if attractive odor is detected for a long time
         - "no_fly_nearby" : if no odor is detected
         
        Parameters
        ----------
        odor_intensities : np.ndarray
            Array of shape (4,) containing the intensities of the odors.
            The first two elements correspond to the attractive odor, and the
            last two elements correspond to the aversive odor.
        timestep : float
            The time elapsed since the last call to this method.
        time_before_decision : float
            The time in seconds before a decision is made.
        """
        I_reshaped = odor_intensities.reshape((self.odor_dimensions, 2, 2))
        odor_intesity_smelled = np.average(np.average(I_reshaped, axis=1, weights=[120, 1200]), axis=1) # axis 0: attractive odor, axis 1: aversive odor
        # Decision making
        if odor_intesity_smelled[0] > self.odor_threshold[0] or odor_intesity_smelled[1] > self.odor_threshold[1]:
            self.time_since_odor_high += timestep
            if self.time_since_odor_high >= time_before_decision: #in seconds
                if odor_intesity_smelled[1] > 0: # aversive odor
                    mating_decision = "reject"
                elif odor_intesity_smelled[0] > self.odor_own_smelling+0.01: # attractive odor (own smelling+margin)
                    mating_decision = "accept"
                else:
                    mating_decision = "fly_close_but_no_decision"
            else:
                mating_decision = "fly_nearby"
        else:
            self.time_since_odor_high = 0
            mating_decision = "no_fly_nearby"
        return mating_decision


if __name__ == "__main__":
    from flygym import Fly, Camera

    run_time = 2
    timestep = 1e-4
    contact_sensor_placements = [
        f"{leg}{segment}"
        for leg in ["LF", "LM", "LH", "RF", "RM", "RH"]
        for segment in ["Tibia", "Tarsus1", "Tarsus2", "Tarsus3", "Tarsus4", "Tarsus5"]
    ]

    # fly = HybridTurningFly(
    #     timestep=timestep,
    #     enable_adhesion=True,
    #     draw_adhesion=True,
    #     actuator_kp=20,
    #     contact_sensor_placements=contact_sensor_placements,
    #     spawn_pos=(0, 0, 0.2),
    # )

    # cam = Camera(fly=fly, camera_id="Animat/camera_top", play_speed=0.1)
    # sim = SingleFlySimulation(fly=fly, cameras=[cam], timestep=1e-4)
    # check_env(sim)

    # obs, info = sim.reset()
    # for i in trange(int(run_time / sim.timestep)):
    #     curr_time = i * sim.timestep
    #     if curr_time < 1:
    #         action = np.array([1.2, 0.2])
    #     else:
    #         action = np.array([0.2, 1.2])

    #     obs, reward, terminated, truncated, info = sim.step(action)
    #     sim.render()

    # cam.save_video("./outputs/hybrid_turning.mp4")
