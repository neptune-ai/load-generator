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
    run[f"metrics/not_indexed/metric_{i}"].extend([step**1.1 + r_vals.random()])                                                                                                                                                                  


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
  for i in range(n):
    name = _random_word(10, r_names)
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
    run["metrics/{}".format(name)].append(value)


# hacky way to understand if where we are in syncing run
def _get_sync_position(runs):
  last_puts = []
  last_acks = []

  for run in runs:

    path = '.neptune/async/run__{}'.format(run._id)
    os.listdir(path)
    path = os.path.join(path, os.listdir(path)[0])
    partitions = os.listdir(path)
    if 'partition-0' not in partitions:
      # we are not usign partitions
      partitions = ['']
    for p in partitions:
      for i in range(0,10000):
        try:
          with open(os.path.join(path, p, 'last_ack_version'), 'r') as f:
            last_ack = int(f.read().split('\n')[0])
          with open(os.path.join(path, p, 'last_put_version'), 'r') as f:      
            last_put = int(f.read().split('\n')[0])
          last_acks.append(last_ack)
          last_puts.append(last_put)
          break
        except ValueError:
          time.sleep(0.01)

  sum_puts = sum(last_puts)
  sum_acks = sum(last_acks)
  return sum_acks, sum_puts


def _seconds_to_hms(seconds):
  return '{}:{:02d}:{:02d}'.format(int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60))


def _manual_sync_runs(runs, disk_flashing_time=8, probe_time=1, logger=None, phase=''):
  # waiting for all data being flashed to a disk
  time.sleep(disk_flashing_time)
  sync_started_time = time.monotonic()
  started_acks, started_puts = _get_sync_position(runs)
  disk_bottleneck_info = False
  while True:
    acks, puts = _get_sync_position(runs)  
    if started_puts != puts:
      started_puts = puts
      if logger:
        if not disk_bottleneck_info:
          logger.warn('Disk is a bottleneck. Consider increasing the step_time or decrease number of runs.')
          disk_bottleneck_info = True
    elif acks == puts:
      break
    else:
      if acks > started_acks:
        current_time = time.monotonic()
        elapsed = current_time - sync_started_time
        estimated = elapsed / (acks - started_acks) * (puts - started_acks)
        seconds_eta = estimated - elapsed
        # seconds eta in format hh:mm:ss
        eta_msg = 'ETA {}'.format(_seconds_to_hms(seconds_eta))
      else:
        eta_msg = ''
      if logger:
        logger.info('Synchronizing {} phase: {}/{} ({:.2f}%). {}'.format(phase, acks, puts, acks/puts * 100, eta_msg)) 
    time.sleep(probe_time)
  
  stop_started_time = time.monotonic()

  sync_time = stop_started_time - sync_started_time
  logger.info('Synchronization of {} phase has finished in {}'.format(phase, _seconds_to_hms(sync_time)))
  return sync_time


def perform_load_test(n, steps, atoms, series, indexed_split, step_time, run_name='', sync_partitions=1,
                      randomize_start=False, sync_after_definitions=True, group_seed=0, group_name='', color=''):

  logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

  log_format = '{}Group={}\x1b[0m - %(levelname)s - %(message)s'.format(color, group_name)
  logging.basicConfig(format=log_format)
  log = logging.getLogger('load_test')
  log.setLevel(logging.INFO)

  if sync_partitions > 1:
    log.warn('Turning experimental mode on with {} partitions.'.format(sync_partitions))
    os.environ['NEPTUNE_MODE'] = 'experimental'
    os.environ['NEPTUNE_ASYNC_PARTITIONS_NUMBER'] = str(sync_partitions)
  else:
    os.environ.pop('NEPTUNE_MODE', None)
    os.environ.pop('NEPTUNE_ASYNC_PARTITIONS_NUMBER', None)
  
  g_random = random.Random(group_seed)
  if randomize_start:
    time_to_start= g_random.random() * step_time
    log.warn('Waiting for {:.2f} seconds to start'.format(time_to_start))
    time.sleep(time_to_start)
  runs = [_initialize_run(run_name) for _ in range(n)]

  start_time = time.monotonic()                                                                                                                                                                                              

  # log indexed atoms
  for j in range(n):
    log_indexed_atoms(runs[j], int(atoms * indexed_split), j)
  
  _, initial_puts = _get_sync_position(runs)

  sync_after_definitions_time = -1
  sync_after_definitions_time_msg = '?'
  disk_bottleneck_info = False

  for i in range(0, steps):                                                                                                                                                                                          
      before = time.monotonic()
      # log step data
      for j in range(n):                                                                                                                                                                                      
        log_not_indexed_atoms(runs[j], i, int(atoms * (1-indexed_split)))
        log_not_indexed_metrics(runs[j], i, int(series * (1-indexed_split)))
        log_indexed_metrics(runs[j], i, int(series * indexed_split), j)
      after = time.monotonic() 
      time.sleep(max(step_time - (after - before), 0))
      
      acks, puts = _get_sync_position(runs)
      acks -= initial_puts
      puts_per_step = (puts - initial_puts) / (i+1)
      total_puts = int(puts_per_step * steps)

      elapsed_time = after - start_time
      eta_time = elapsed_time / (i+1) * (steps - i - 1)
      if total_puts > 0:
        msg = 'Steps on disk {}/{} ({:.2f}%). Elapsed {} - ETA {}. '.format(
          i, steps-1, (i+1)/steps * 100, _seconds_to_hms(elapsed_time), _seconds_to_hms(eta_time))
        msg = msg + 'Operations synchronized with NPT server {}/{} ({:.2f}%)'.format(acks, total_puts, acks/total_puts * 100)
        log.info(msg)
        
        if after-before > step_time:
            if not disk_bottleneck_info:
              logging.warn('Writing to a disk is lagging. Consider increasing the step_time {} -> {:.2f}'.format(step_time, after-before))
              disk_bottleneck_info = True
            
      else:
        log.info('No puts yet')

      if i == 0 and sync_after_definitions:
        sync_after_definitions_time = _manual_sync_runs(
          runs, disk_flashing_time=6, probe_time=1, logger=log, phase='definitions')
        sync_after_definitions_time_msg = _seconds_to_hms(sync_after_definitions_time)
  
  sync_start_time = time.monotonic()
  sync_time = _manual_sync_runs(runs, disk_flashing_time=6, probe_time=1, logger=log, phase='training')

  stop_started_time = time.monotonic()
  for r in runs:
     r.stop()
  stop_end_time = time.monotonic()
  stopping_time = stop_end_time - stop_started_time
  
  log.info('Summary: total time: {} ({:.2f}), defintions: {} ({:.2f}), training time: {} ({:.2f}), syncing time: {} ({:.2f}), stopping time {}  ({:.2f}).'.format(\
    _seconds_to_hms(stop_end_time - start_time),\
    stop_end_time - start_time, \
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
  parser.add_argument("--runs", type=int, default=1, help='number of runs to perform per process')
  parser.add_argument("--atoms", type=int, default=0)
  parser.add_argument("--series", type=int, default=0)
  parser.add_argument("--step-time", type=float, default=1.0)
  parser.add_argument("--indexed-split", type=float, default=0.1, help='split of indexed metrics and atoms vs not indexed')
  parser.add_argument("--run-name", type=str, default='')
  parser.add_argument("--sync-partitions", type=int, help='(experimental) number of threads per run used to sync with NPT servers', default=1)
  parser.add_argument("--processes", type=int, help='number of processes. In total we will log runs * processes', default=1)

  parser.add_argument('--randomize-start', action='store_true')
  parser.add_argument('--no-randomize-start', dest='randomize_start', action='store_false')
  parser.set_defaults(randomize_start=True)

  parser.add_argument('--sync-after-definitions', action='store_true')
  parser.add_argument('--no-sync-after-definitions', dest='sync_after_definitions', action='store_false')
  parser.set_defaults(sync_after_definitions=False)
  args = parser.parse_args()

  steps = args.steps
  n = args.runs
  atoms = args.atoms
  series = args.series
  step_time = args.step_time
  sync_partitions = args.sync_partitions
  run_name = args.run_name
  num_processes = args.processes
  indexed_split = args.indexed_split
  randomize_start = args.randomize_start
  sync_after_definitions = args.sync_after_definitions

  assert(series + atoms <= 99900)
  assert(int(subprocess.check_output("ulimit -n", shell=True)) > 2000)
  assert(num_processes * n <= 1200)
  assert(num_processes * n * sync_partitions <= 10000)
  assert(num_processes > 0 and num_processes <= 160)
  assert(indexed_split * (atoms + series) <= 10000) # 10000 is a limit of indexed fields at NPT server

  if series + atoms > 10000 and sync_partitions <= 1:
     pass

  
  if sync_partitions > 1 and neptune.__version__ != '1.8.3rc1.post10+69d7735':
    
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
        n, steps, atoms, series, indexed_split, step_time,
          '{}-group-{}'.format(run_name, i), sync_partitions, randomize_start,
          sync_after_definitions,
          int(i+time.monotonic()*20),
          i,
          colors[i % len(colors)])
        ) for i in range(num_processes)]
  
  for i in range(num_processes):
      processes[i].start()    

  for i in range(num_processes):
      processes[i].join()
  
