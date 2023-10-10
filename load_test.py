import argparse
import concurrent.futures
import math
import multiprocessing as mp
import random
import string
import time



def _initialize_run(run_name, *args, **kwargs):
  import neptune

  return neptune.init_run(
      capture_stderr=False,
      capture_stdout=False,
      name=run_name,
      source_files=[], # we don't want to send source files
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
      value = math.sin(step/10) + r_vals.random() * 0.2 - 0.1
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


def perform_load_test(n, steps, atoms, series, indexed_split, epoch_time, run_name='', threads=8, group_name='', color=''):

  import logging
  
  logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

  log_format = '{}Group={}\x1b[0m - %(levelname)s - %(message)s'.format(color, group_name)
  logging.basicConfig(format=log_format)
  log = logging.getLogger('load_test')
  log.setLevel(logging.INFO)
  

  runs = []
  with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
    future_runs = [executor.submit(_initialize_run, run_name) for _ in range(n)]
    for f in future_runs:
        runs.append(f.result())                       

  st = time.monotonic()                                                                                                                                                                                              

  # log indexed atoms
  for j in range(n):
    log_indexed_atoms(runs[j], int(atoms * indexed_split), j)


  for i in range(0, steps):                                                                                                                                                                                          
      before = time.monotonic()
      for j in range(n):                                                                                                                                                                                      
        log_not_indexed_atoms(runs[j], i, int(atoms * (1-indexed_split)))
        log_not_indexed_metrics(runs[j], i, int(series * (1-indexed_split)))
        log_indexed_metrics(runs[j], i, int(series * indexed_split), j)                                                                                                                                                                              
      after = time.monotonic() 
      log.info('Epoch {}/{} of {} runs was submitted to sync process ({}s)'.format(i+1, steps, n, after - before))                                                                                                                                                     
      if after - before > epoch_time:                                                                                                                                                                                         
          log.info('Epoch {}/{} did not manage to fit into epoch time {} > {}!'.format(i+1, steps, after - before, epoch_time))
      time.sleep(max(epoch_time - (after - before), 0))                                                                                                                                                                       
                                                                                                                                                                                                                    
  wt = time.monotonic()                                                                                                                                                                                              

  with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
      futures = [executor.submit(runs[i].sync) for i in range(n)]
      for f in futures:
          f.result()
                                                                                                                                                                                                                        
  syncT = time.monotonic()                                                                                                                                                                                           

  with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
      futures = [executor.submit(runs[i].stop) for i in range(n)]
      for f in futures:
          f.result()                                                                                                                                                                                                                   
                                                                                                                                                                          
  stopT = time.monotonic()                                                                                                                                                                                           
  log.info('Summary: training {}\tsyncing:{}\tstopping:{}'.format(wt-st, syncT-wt, stopT-syncT))

if __name__ == "__main__":
  argparse = argparse.ArgumentParser()
  argparse.add_argument("--steps", type=int, default=60)
  argparse.add_argument("--runs", type=int, default=1, help='number of runs to perform per process')
  argparse.add_argument("--atoms", type=int, default=0)
  argparse.add_argument("--series", type=int, default=0)
  argparse.add_argument("--epoch-time", type=int, default=1)
  argparse.add_argument("--indexed-split", type=float, default=0.1, help='split of indexed metrics and atoms vs not indexed')
  argparse.add_argument("--run-name", type=str, default='')
  argparse.add_argument("--threads", type=int, help='per process to initialize, sync and close runs', default=8)
  argparse.add_argument("--processes", type=int, help='number of processes. In total we will log runs * processes', default=1)
  args = argparse.parse_args()


  steps = args.steps
  n = args.runs
  atoms = args.atoms
  series = args.series
  epoch_time = args.epoch_time
  threads = args.threads
  run_name = args.run_name
  num_processes = args.processes
  indexed_split = args.indexed_split

  assert(num_processes > 0 and num_processes <= 160)
  assert(indexed_split * (atoms + series) <= 9000) # 9000 is a limit of neptune
  
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
        n, steps, atoms, series, indexed_split, epoch_time, '{}-group-{}'.format(run_name, i), threads, i, colors[i % len(colors)])
        ) for i in range(num_processes)]
  
  for i in range(num_processes):
      processes[i].start()    

  for i in range(num_processes):
      processes[i].join()
  