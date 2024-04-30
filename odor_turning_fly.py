from hybrid_turning_fly import HybridTurningFly
import numpy as np

class OdorTaxisFly(HybridTurningFly):
    def __init__(self, odor_dimensions, odor_gains, odor_threshold=0.15, decision_interval=0.05, **kwargs):
        super().__init__(**kwargs, enable_vision=True)
        self.odor_threshold = odor_threshold
        self.decision_interval = decision_interval
        self.odor_dimensions = odor_dimensions
        self.num_substeps = int(self.decision_interval / self.timestep)
        self.odor_gains = odor_gains
        
        assert len(odor_gains) == 2, "The number of odor gains should be 2 (one for attractive and one for aversive odors)"


    def process_odor_intensities(self, odor_intensities):
        I_reshaped = odor_intensities.reshape((self.odor_dimensions, 2, 2))
        I = np.average(I_reshaped, axis=1, weights=[120, 1200])
        # Calculate the left-right asymmetry in the odor intensities
        I_l, I_r = I[:, 0], I[:, 1]
        denom = (I_l + I_r) / 2 + 1e-6 # Avoid division by zero
        denom[denom == 0] = 1  # Avoid division by zero
        delta_I = (I_l - I_r) / denom

        # Calculate the weighted sum of the asymmetries for each odor
        s = np.dot(self.odor_gains, delta_I)

        # Calculate the turning bias
        b = np.tanh(s**2)

        control_signal = np.ones((2,))
        side_to_modulate = int(s > 0)
        modulation_amount = b * 0.8
        control_signal[side_to_modulate] -= modulation_amount
        
        if b == 0:
            control_signal = np.zeros((2,))
            
        # Set control signal to zero if attractive odor intensity is above a threshold
        if(I_l[0] > self.odor_threshold or I_r[0] > self.odor_threshold): 
            control_signal = np.zeros((2,))
            if not reached_odor_source:
                reached_odor_source = True
                print("Reached odor source!")
        return control_signal