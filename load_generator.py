import argparse
import math
import multiprocessing as mp
import neptune
import logging
import os
import random
import string
import subprocess
import sys
import time


def _initialize_run(run_name, *args, **kwargs):
  return neptune.init_run(
      capture_stderr=False,
      capture_stdout=False,
      name=run_name,
      source_files=[], # we don't want to send source files
      git_ref=False, # we don't want to send git info
      enable_remote_signals = False,
      capture_hardware_metrics=False)                                                                                                                                                                                                                                                                                                                      


def log_not_indexed_metrics(run, step, n, seed=0):                                                                                                                                                                       
  r_vals = random.Random(seed)
  for i in range(n):                                                                                                                                                                                          
    run[f"metrics/not_indexed/metric_{i}"].append(step**1.1 + r_vals.random(), step=step)


def log_not_indexed_atoms(run, step, n, seed=0):
  r_vals = random.Random(seed)
  for i in range(n):                                                                                                                                                                                          
    run[f"atoms/not_indexed/{i}"] = step**1.1 + r_vals.random()


def _random_word(length, rgenerator):
   letters = string.ascii_lowercase
   return ''.join(rgenerator.choice(letters) for i in range(length))


def log_indexed_atoms(run, n, seed=0):
  r_names = random.Random(0) # we want to have shared names across runs
  r_vals = random.Random(seed) # values don't need to be shared
  for i in range(n):
    name = _random_word(10, r_names)
    run["atoms/{}".format(name)] = r_vals.random() if i % 2 == 0 else _random_word(10, r_vals)


def log_indexed_metrics(run, step, n, seed=0):
  r_names = random.Random(1) # we want to have shared names across runs. Value is 1 to be different from atoms
  r_vals = random.Random(seed) # values don't need to be shared
  offset = r_vals.random() * 100
  a_linear = r_vals.random() * 3
  names = set()
  for i in range(n):
    # to avoid name collisions
    name = _random_word(10, r_names)
    assert name not in names
    names.add(name)

    value = 0
    if i%4 == 0:
      # value of sin with period 10 steps with noise [-0.1, 0.1]
      value = math.sin((step - offset * 0.1) / 10) + r_vals.random() * 0.2 - 0.1
    elif i%4 == 1:
      # value of log steps with noise [-0.1, 0.1]
      value = math.log(step + 0.1) + r_vals.random() * 0.2 - 0.1
    elif i%4 == 2:
      # value of sigmoid with offset of 10 steps with noise [-0.1, 0.1]
      value = 1/(1 + math.exp(-step - offset)) + r_vals.random() * 0.2 - 0.1
    elif i%4 == 3:
      # value of linear
      value = a_linear * step + offset
    run["metrics/{}".format(name)].append(value, step=step)


# hacky way to understand if where we are in syncing run
def _get_sync_position(runs, offset=0, logger=None):
  last_puts = []
  last_acks = []

  for run in runs:
    path = '.neptune/async/run__{}'.format(run._id)
    os.listdir(path)
    path = os.path.join(path, os.listdir(path)[0])
    partitions = os.listdir(path)
    if 'partition-0' not in partitions:
      # we are not using partitions
      partitions = ['']
    for p in partitions:

      def _read_step(filename, retries=100, logger=None):
        for retry in range(0, retries):
          try:
            with open(filename, 'r') as f:
              return int(f.read().split('\n')[0])
          except ValueError:
              sleep_time = 0.05
              if retry == retries-1 and logger:
                logger.warn('Waiting for a files {} to be written. Sleeping for {:.2f} seconds'.format(os.path.join(path, p), sleep_time))
              time.sleep(sleep_time) # wait for a file to be written
        return -1

      ack_file = os.path.join(path, p, 'last_ack_version')
      put_file = os.path.join(path, p, 'last_put_version')
      if _read_step(ack_file, retries=1) != -1 and _read_step(put_file, retries=1) != -1:
        last_acks.append(_read_step(ack_file, logger=logger))
        last_puts.append(_read_step(put_file, logger=logger))
    
  sum_puts = sum(last_puts)
  sum_acks = sum(last_acks)
  return sum_acks - offset, sum_puts - offset

def _seconds_to_hms(seconds):
  return '{}:{:02d}:{:02d}'.format(int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60))


# get info about speed of syncing with NPT server
def _get_sync_progress(runs, partitions_per_run, offset=0, progress_history=None, logger=None):
  now = time.monotonic()
  progress_history = progress_history or {}
  progress_history['times'] = progress_history.get('times', []) + [now]
  acks, puts = _get_sync_position(runs, offset, logger=logger)
  assert(acks <= puts)
  progress_history['acks'] = progress_history.get('acks', []) + [acks]
  progress_history['puts'] = progress_history.get('puts', []) + [puts]

  # Only consider the last 120 seconds of data
  last_60s = [i for i, t in enumerate(progress_history['times']) if now - t <= 120]
  last_acks = [progress_history['acks'][i] for i in last_60s]
  last_puts = [progress_history['puts'][i] for i in last_60s]

  if len(last_60s) > 1:
    speed_acks = (last_acks[-1] - last_acks[0]) / (progress_history['times'][last_60s[-1]] - progress_history['times'][last_60s[0]])
    speed_puts = (last_puts[-1] - last_puts[0]) / (progress_history['times'][last_60s[-1]] - progress_history['times'][last_60s[0]])
    progress_history['speed'] = progress_history.get('speed', []) + [(speed_acks, speed_puts)]
  else:
    progress_history['speed'] = progress_history.get('speed', []) + [(0, 0)]

  if len(progress_history['speed']) > 1:
    speed_acks_avg = acks / (now - progress_history['times'][0])
    speed_puts_avg = puts / (now - progress_history['times'][0])
    progress_history['speed_avg'] = (speed_acks_avg, speed_puts_avg)
  else:
    progress_history['speed_avg'] = (0, 0)

  if progress_history['speed_avg'][0] == 0:
    eta = "?"
    eta_time = -1000000000
  else:
    eta_time = (progress_history['puts'][-1] - progress_history['acks'][-1]) / progress_history['speed_avg'][0]
    eta = _seconds_to_hms(eta_time)
    if eta_time < 25:
      eta_color = '\033[92m'  # green
    else:
      eta_color = '\033[91m'  # red
    eta = '{}{}{}'.format(eta_color, eta, '\033[0m')
  
  ops_left = progress_history['puts'][-1] - progress_history['acks'][-1]
  if ops_left < 30000:
    ops_left_msg = '\033[92m{}\033[0m'.format(ops_left)  # green
  else:
    ops_left_msg = '\033[91m{}\033[0m'.format(ops_left)  # red

  if progress_history['speed'][-1][0] <= 0 and ops_left > 0:
    speed_msg = '\033[91m0\033[0m'
  else:
    speed_msg = '{:7.1f}'.format(progress_history['speed'][-1][0])

  msg = 'Sync: ACK in last 120s {} (avg {:7.1f}) ops/s. {:7} ops left to sync, sync ETA {}'.format(
    speed_msg,
    progress_history['speed_avg'][0],
    ops_left_msg,
    eta
  )
  return msg, eta_time, progress_history


def _manual_sync_runs(runs, sync_partitions, disk_flashing_time=8, probe_time=10, logger=None, phase='', sync_offset=0, sync_progress_history=None):
  # waiting for all data being flashed to a disk
  time.sleep(disk_flashing_time)
  sync_started_time = time.monotonic()
  started_acks, started_puts = _get_sync_position(runs, sync_offset, logger=logger)
  last_log_time = 0
  while True:
    acks, puts = _get_sync_position(runs, sync_offset, logger=logger)
    if started_puts != puts:
      started_puts = puts
    elif acks == puts:
      break
    else:
      if logger and last_log_time + 10 < time.monotonic():
        last_log_time = time.monotonic()
        sync_progress_msg, _, sync_progress_history = _get_sync_progress(runs, sync_partitions, sync_offset, sync_progress_history, logger=logger)
        logger.info('Synchronizing {} phase: {}'.format(phase, sync_progress_msg)) 
    time.sleep(probe_time)
  
  stop_started_time = time.monotonic()

  sync_time = stop_started_time - sync_started_time
  logger.info('\033[92mSynchronization of {} phase has finished in {}\033[0m'.format(phase, _seconds_to_hms(sync_time)))
  return sync_time

def perform_load_test(steps, atoms, series, indexed_split, step_time, run_name='', sync_partitions=1,
                      randomize_start=False, sync_after_definitions=True, group_seed=0, group_id=0, color=''):

  
  log_format = '{}G-{:3}\x1b[0m - %(asctime)s - %(levelname)s - %(message)s'.format(color, group_id)
  logging.basicConfig(format=log_format)
  log = logging.getLogger('load_test')
  log.setLevel(logging.INFO)

  # turn on experimental mode to use partitions in syncing with NPT server
  if sync_partitions > 1:
    log.warn('Turning experimental mode on with {} partitions.'.format(sync_partitions))
    os.environ['NEPTUNE_MODE'] = 'experimental'
    os.environ['NEPTUNE_ASYNC_PARTITIONS_NUMBER'] = str(sync_partitions)
  else:
    os.environ.pop('NEPTUNE_MODE', None)
    os.environ.pop('NEPTUNE_ASYNC_PARTITIONS_NUMBER', None)
  
  # specific settings for benchmarks
  os.environ['NEPTUNE_ALLOW_SELF_SIGNED_CERTIFICATE'] = 'TRUE'
  os.environ['NEPTUNE_REQUEST_TIMEOUT'] = '90'

  g_random = random.Random(group_seed)
  if randomize_start:
    time_to_start= g_random.random() * step_time
    log.warn('Waiting for {:.2f} seconds to start'.format(time_to_start))
    time.sleep(time_to_start)
  
  # we have  1 run per subprocess
  runs = [_initialize_run(run_name)]

  start_time = time.monotonic()                                                                                                                                                                                              

  run_initialization_time = _manual_sync_runs(runs, sync_partitions, disk_flashing_time=6, probe_time=1, logger=log, phase='run initialization', sync_offset=0)
  sync_offset_init, _ = _get_sync_position(runs, 0, logger=log)
  last_sync_offset = sync_offset_init

  sync_after_definitions_time = -1
  sync_after_definitions_time_msg = '?'
  disk_bottleneck_info = False
  last_operation_info_time = time.monotonic()
  sync_progress_history = None


  for i in range(0, steps):                                                                                                                                                                                          
      disk_start_time = time.monotonic()
      # log step data
      for r in runs:
        log_not_indexed_atoms(r, i, int(atoms * (1-indexed_split)))
        log_not_indexed_metrics(r, i, int(series * (1-indexed_split)))
        log_indexed_atoms(r, int(atoms * indexed_split), group_id)
        log_indexed_metrics(r, i, int(series * indexed_split), group_id)
      disk_end_time = time.monotonic() 
      # wait to simulate avg. step time
      if disk_end_time-disk_start_time > step_time:
          if not disk_bottleneck_info:
            logging.warn('Writing to a disk is lagging. Consider increasing the step_time {} -> {:.2f}'.format(step_time, disk_end_time-disk_start_time))
            disk_bottleneck_info = True
      time.sleep(max(step_time - (disk_end_time - disk_start_time), 0))
      
      # calculate ETA
      disk_eta = (steps - i) * step_time

      # NPT sync diagnostics   
      sync_progress_msg, sync_eta, sync_progress_history = _get_sync_progress(runs, sync_partitions, last_sync_offset, sync_progress_history, logger=log)

      # print progress
      if i % ((steps/100)+1) == 0 or i == steps-1 or last_operation_info_time + 10 < time.monotonic():
        msg = msg = 'Steps {:7}/{:3} ({:5.1f}%)'.format(i, steps-1, (i+1)/steps * 100)
        last_operation_info_time = time.monotonic()
        total_eta = disk_eta + sync_eta
        log.info('{} {}. Total ETA {}'.format(msg, sync_progress_msg, _seconds_to_hms(total_eta) if total_eta > 0 else '?'))


      # sync with NPT server after definitions of atoms and metrics
      if i == 0 and sync_after_definitions:
        sync_after_definitions_time = _manual_sync_runs(
          runs, sync_partitions, disk_flashing_time=6, probe_time=1, logger=log, phase='definitions', sync_offset=last_sync_offset)
        sync_after_definitions_time_msg = _seconds_to_hms(sync_after_definitions_time)
        last_sync_offset += _get_sync_position(runs, last_sync_offset, logger=log)[0]
        
  
  sync_start_time = time.monotonic()
  sync_time = _manual_sync_runs(runs, sync_partitions, disk_flashing_time=6, probe_time=1, logger=log, phase='training', sync_offset=last_sync_offset, sync_progress_history=None)

  stop_started_time = time.monotonic()
  for r in runs:
     r.stop()
  stop_end_time = time.monotonic()
  stopping_time = stop_end_time - stop_started_time
  
  log.info('\033[95mSummary: total time: {} ({:.2f}), run init: {} ({:.2f}), definitions: {} ({:.2f}), training time: {} ({:.2f}), syncing time: {} ({:.2f}), stopping time {}  ({:.2f}).\033[0m'.format(\
    _seconds_to_hms(stop_end_time - start_time),\
    stop_end_time - start_time, \
    _seconds_to_hms(run_initialization_time),\
    run_initialization_time,\
    sync_after_definitions_time_msg,\
    sync_after_definitions_time,\
    _seconds_to_hms(sync_start_time - start_time),\
    sync_start_time - start_time,\
    _seconds_to_hms(sync_time),\
    sync_time,\
    _seconds_to_hms(stopping_time),
    stopping_time))


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--steps", type=int, default=60)
  parser.add_argument("--runs", type=int, default=1, help='number of runs to perform')
  parser.add_argument("--atoms", type=int, default=0)
  parser.add_argument("--series", type=int, default=0)
  parser.add_argument("--step-time", type=float, default=1.0)
  parser.add_argument("--indexed-split", type=float, default=0.1, help='split of indexed metrics and atoms vs not indexed')
  parser.add_argument("--run-name", type=str, default='')
  parser.add_argument("--sync-partitions", type=int, help='(experimental) number of threads per run used to sync with NPT servers', default=1)

  parser.add_argument('--randomize-start', action='store_true')
  parser.add_argument('--no-randomize-start', dest='randomize_start', action='store_false')
  parser.set_defaults(randomize_start=True)

  parser.add_argument('--sync-after-definitions', action='store_true')
  parser.add_argument('--no-sync-after-definitions', dest='sync_after_definitions', action='store_false')
  parser.set_defaults(sync_after_definitions=False)
  args = parser.parse_args()

  steps = args.steps
  n_runs = args.runs
  atoms = args.atoms
  series = args.series
  step_time = args.step_time
  sync_partitions = args.sync_partitions
  run_name = args.run_name
  indexed_split = args.indexed_split
  randomize_start = args.randomize_start
  sync_after_definitions = args.sync_after_definitions

  assert(series + atoms <= 100000)
  assert(int(subprocess.check_output("ulimit -n", shell=True)) > 2000)
  assert(n_runs > 0 and n_runs <= 200)
  assert(n_runs * sync_partitions <= 10000)
  assert(indexed_split * (atoms + series) <= 10000) # 10000 is a limit of indexed fields at NPT server

  if series + atoms > 10000 and sync_partitions <= 1:
     pass

  
  if sync_partitions > 1 and neptune.__version__ != '1.8.3rc2.post16+6597fac':
    
    logging.error('You need to have experimental version of NPT client installed. Run\n'\
              '  pip install git+https://github.com/neptune-ai/neptune-client.git@partitioned')
    exit(1)


  colors = [] 
  for fg in range(30,38):
      s1 = ''
      for bg in range(40,48):
          if fg != bg - 10:
            format = ';'.join([str(1), str(fg), str(bg)])
            color = '\x1b[%sm' % format
            colors.append(color)

  processes = [
     mp.Process(target=perform_load_test, args=(
          steps, atoms, series, indexed_split, step_time,
          '{}-group-{}'.format(run_name, i), sync_partitions, randomize_start,
          sync_after_definitions,
          int(i+time.monotonic()*20),
          i,
          colors[i % len(colors)])
        ) for i in range(n_runs)]
  
  for i in range(n_runs):
      processes[i].start()    

  for i in range(n_runs):
      processes[i].join()
  
