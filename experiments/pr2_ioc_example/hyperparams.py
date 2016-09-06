""" Hyperparameters for PR2 trajectory optimization experiment. """
from __future__ import division

from datetime import datetime
import os.path

import numpy as np

from gps import __file__ as gps_filepath
from gps.agent.ros.agent_ros import AgentROS
from gps.algorithm.algorithm_traj_opt import AlgorithmTrajOpt
from gps.algorithm.cost.cost_fk import CostFK
from gps.algorithm.cost.cost_action import CostAction
from gps.algorithm.cost.cost_sum import CostSum
from gps.algorithm.cost.cost_ioc_nn import CostIOCNN
from gps.algorithm.cost.cost_utils import RAMP_CONSTANT, evall1l2term
from gps.algorithm.dynamics.dynamics_lr_prior import DynamicsLRPrior
from gps.algorithm.dynamics.dynamics_prior_gmm import DynamicsPriorGMM
from gps.algorithm.traj_opt.traj_opt_lqr_python import TrajOptLQRPython
from gps.algorithm.policy.lin_gauss_init import init_lqr, init_demo_conditions
from gps.gui.target_setup_gui import load_pose_from_npz
from gps.proto.gps_pb2 import JOINT_ANGLES, JOINT_VELOCITIES, \
        END_EFFECTOR_POINTS, END_EFFECTOR_POINT_VELOCITIES, ACTION, \
        TRIAL_ARM, AUXILIARY_ARM, JOINT_SPACE
from gps.utility.general_utils import get_ee_points
from gps.gui.config import generate_experiment_info


EE_POINTS = np.array([[0.02, -0.025, 0.05], [0.02, -0.025, -0.05],
                      [0.02, 0.05, 0.0]])

SENSOR_DIMS = {
    JOINT_ANGLES: 7,
    JOINT_VELOCITIES: 7,
    END_EFFECTOR_POINTS: 3 * EE_POINTS.shape[0],
    END_EFFECTOR_POINT_VELOCITIES: 3 * EE_POINTS.shape[0],
    ACTION: 7,
}

PR2_GAINS = np.array([3.09, 1.08, 0.393, 0.674, 0.111, 0.252, 0.098])

BASE_DIR = '/'.join(str.split(gps_filepath, '/')[:-2])
EXP_DIR = BASE_DIR + '/../experiments/pr2_ioc_example/'
DEMO_DIR = BASE_DIR + '/../experiments/pr2_example/'

x0s = []
ee_tgts = []
reset_conditions = []

common = {
    'experiment_name': 'my_experiment' + '_' + \
            datetime.strftime(datetime.now(), '%m-%d-%y_%H-%M'),
    'experiment_dir': EXP_DIR,
    'data_files_dir': EXP_DIR + 'data_files/',
    'target_filename': EXP_DIR + 'target.npz',
    'log_filename': EXP_DIR + 'log.txt',
    'conditions': 1,
    'demo_controller_file': DEMO_DIR + 'data_files/algorithm_itr_14.pkl',
    'demo_exp_dir': DEMO_DIR,
    'nn_demo': False
}

# TODO(chelsea/zoe) : Move this code to a utility function
# Set up each condition.
for i in xrange(5): #xrange(common['conditions']):

    ja_x0, ee_pos_x0, ee_rot_x0 = load_pose_from_npz(
        common['target_filename'], 'trial_arm', str(i), 'initial'
    )
    ja_aux, _, _ = load_pose_from_npz(
        common['target_filename'], 'auxiliary_arm', str(i), 'initial'
    )
    _, ee_pos_tgt, ee_rot_tgt = load_pose_from_npz(
        common['target_filename'], 'trial_arm', str(i), 'target'
    )

    x0 = np.zeros(32)
    x0[:7] = ja_x0
    x0[14:(14+3*EE_POINTS.shape[0])] = np.ndarray.flatten(
        get_ee_points(EE_POINTS, ee_pos_x0, ee_rot_x0).T
    )

    ee_tgt = np.ndarray.flatten(
        get_ee_points(EE_POINTS, ee_pos_tgt, ee_rot_tgt).T
    )

    aux_x0 = np.zeros(7)
    aux_x0[:] = ja_aux

    reset_condition = {
        TRIAL_ARM: {
            'mode': JOINT_SPACE,
            'data': x0[0:7],
        },
        AUXILIARY_ARM: {
            'mode': JOINT_SPACE,
            'data': aux_x0,
        },
    }

    x0s.append(x0)
    ee_tgts.append(ee_tgt)
    reset_conditions.append(reset_condition)


if not os.path.exists(common['data_files_dir']):
    os.makedirs(common['data_files_dir'])

agent = {
    'type': AgentROS,
    'dt': 0.05,
    'conditions': common['conditions'],
    'T': 100,
    'x0': [x0s[4]],
    'ee_points_tgt': [ee_tgts[4]],
    'reset_conditions': [reset_conditions[4]],
    'sensor_dims': SENSOR_DIMS,
    'state_include': [JOINT_ANGLES, JOINT_VELOCITIES, END_EFFECTOR_POINTS,
                      END_EFFECTOR_POINT_VELOCITIES],
    'end_effector_points': EE_POINTS,
    'obs_include': [JOINT_ANGLES, JOINT_VELOCITIES, END_EFFECTOR_POINTS,
                      END_EFFECTOR_POINT_VELOCITIES],
}

demo_agent = {
    'type': AgentROS,
    'dt': 0.05,
    'conditions': 5, #common['conditions'],
    'T': 100,
    'x0': x0s[:5],
    'ee_points_tgt': ee_tgts[:5],
    'reset_conditions': reset_conditions[:5],
    'sensor_dims': SENSOR_DIMS,
    'state_include': [JOINT_ANGLES, JOINT_VELOCITIES, END_EFFECTOR_POINTS,
                      END_EFFECTOR_POINT_VELOCITIES],
    'end_effector_points': EE_POINTS,
    'obs_include': [JOINT_ANGLES, JOINT_VELOCITIES, END_EFFECTOR_POINTS,
                      END_EFFECTOR_POINT_VELOCITIES],
    'filter_demos': True,
    'target_end_effector': np.zeros(3 * EE_POINTS.shape[0]),
}

algorithm = {
    'type': AlgorithmTrajOpt,
    'conditions': common['conditions'],
    'iterations': 25,
    #'learning_from_prior': True,
    'target_end_effector': np.zeros(3 * EE_POINTS.shape[0]),
    'ioc': 'ICML',  # 'MPF', 'ICML'
    'max_ent_traj': 1.0,
    'kl_step': 0.5,
    'min_step_mult': 0.05,
    'max_step_mult': 2.0,
    'demo_distr_empest': True, # For ICML version, importance sampling emperically.
    #'demo_cond': 15,
    'num_demos': 10,
    'synthetic_cost_samples': 100,
    'demo_var_mult': 1.0  # Increase variance on demos
}

"""
algorithm['init_traj_distr'] = {
    'type': init_lqr,
    'init_gains':  1.0 / PR2_GAINS,
    'init_acc': np.zeros(SENSOR_DIMS[ACTION]),
    'init_var': 1.0,
    'stiffness': 0.5,
    'stiffness_vel': 0.25,
    'final_weight': 50,
    'dt': agent['dt'],
    'T': agent['T'],
}
"""


algorithm['init_traj_distr'] = {
    'type': init_demo_conditions,
    'init_gains':  1.0 / PR2_GAINS,
    'init_acc': np.zeros(SENSOR_DIMS[ACTION]),
    'init_var': 0.5,
    'stiffness': 10.0,
    'stiffness_vel': 0.25,
    'final_weight': 1.0,
    'dt': agent['dt'],
    'T': agent['T'],
    'demo_file': common['data_files_dir']+'demos_LG.pkl',
    'ee_tgts': ee_tgts,
    'ee_idx': slice(14,23),
    'combine_conditions': False
}


torque_cost = {
    'type': CostAction,
    'wu': 5e-3 / PR2_GAINS,
}

fk_cost1 = {
    'type': CostFK,
    # Target end effector is subtracted out of EE_POINTS in ROS so goal
    # is 0.
    'target_end_effector': np.zeros(3 * EE_POINTS.shape[0]),
    'wp': np.ones(SENSOR_DIMS[END_EFFECTOR_POINTS]),
    'l1': 1.0,
    'alpha': 1e-5,
    'l2': 0.0001,
    'ramp_option': RAMP_CONSTANT,
    'evalnorm': evall1l2term
}

algorithm['gt_cost'] = {
    'type': CostSum,
    'costs': [torque_cost, fk_cost1],
    'weights': [1.0, 1.0],
}

algorithm['cost'] = {
    'type': CostIOCNN,
    'wu': 5e-1 / PR2_GAINS,
    'T': 100,
    'demo_batch_size': 5,
    'sample_batch_size': 5,
    'dO': 32,
    'iterations': 5000,
    'smooth_reg_weight': 0.0,
    'mono_reg_weight': 100.0,
    'learn_wu': False
}

algorithm['dynamics'] = {
    'type': DynamicsLRPrior,
    'regularization': 1e-6,
    'prior': {
        'type': DynamicsPriorGMM,
        'max_clusters': 20,
        'min_samples_per_cluster': 40,
        'max_samples': 20,
    },
}

algorithm['traj_opt'] = {
    'type': TrajOptLQRPython,
}

algorithm['policy_opt'] = {}

config = {
    'iterations': algorithm['iterations'],
    'common': common,
    'verbose_trials': 0,
    'agent': agent,
    'demo_agent': demo_agent,
    'gui_on': True,
    'algorithm': algorithm,
    'num_samples': 10,
}

common['info'] = generate_experiment_info(config)
