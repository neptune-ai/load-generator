# 1. Functional test to Neptune Server

- Export  the following Environmen variables:
  - ```export NEPTUNE_PROJECT=<Your Project>```
  - ```export NEPTUNE_API_TOKEN=<Your API Token>```
- Run the following script:
  - ```python3 functional_test.py```

# 2. Load generator to Neptune Server


## Installation and setup

Please install the latest, with parallelized sync support version of neptune client:
```
  pip install git+https://github.com/neptune-ai/neptune-client.git@partitioned
 ```

Alternatively, here is release candidate but it doesn't support the parallelized sync.
```
pip install neptune==1.8.3rc2
```


You need to remember about setting neptune token and project enviroments. *Use the token of the Neptune instance you want to use*.
```
export NEPTUNE_API_TOKEN="YOUR TOKEN"
export NEPTUNE_PROJECT="YOUR PROJECT" # "dzwiedziu/load-test"
```
There are additional ones, that load generators sets and are adviced for benchmark set-up.
```
export NEPTUNE_ALLOW_SELF_SIGNED_CERTIFICATE=TRUE
export NEPTUNE_REQUEST_TIMEOUT=90
```



It is also adviced to increase a limit of open files (neptune-client has separate sync-files for each run).
```
ulimit -Sn 1000000
```


## Example configurations


20 runs, sending 20 steps every 10 seconds, in each step 100 series and 100 atoms

```
python3 load_generator.py --runs 20 --steps 20 --series 100 --atoms 100 --step-time=10 --run-name='warmup' --indexed-split=0.5 
```


100 runs, sending 20 steps every 25 seconds, in each step 5000 series and 100 atoms

```
python3 load_generator.py --runs 20 --steps 20 --series 5000 --atoms 100 --step-time=25 --run-name='low 100x5000' --indexed-split=0.5 
```

200 runs, sending 100 steps every 25 seconds, in each step 9000 series and 500 atoms

```
python3 load_generator.py --runs 100 --steps 20 --series 9000 --atoms 500 --step-time=25 --run-name='medium 200x9500' --indexed-split=0.5
```


## 100K attributes runs

For bigger runs you may want to use experimental version of Neptune Client, that parallelize the syncronization process of a run.
```
pip install git+https://github.com/neptune-ai/neptune-client.git@partitioned
```

Normally, you also need to set env variables but in this case, load generator will do it for you via setting `--sync-partitions=32` flag.
```
export NEPTUNE_MODE=experimental
export NEPTUNE_ASYNC_PARTITIONS_NUMBER=32
```

Check it out with 4 runs
```
 python3 load_generator.py --runs 4 --steps 20 --series 1000000 --step-time=25 --run-name='100k 2x2 runs' --indexed-split=0.1 --sync-partitions=12 > /dev/null
 ```

And now with 25 runs
```
 python3 load_generator.py --runs 25 --steps 20 --series 100000 --step-time=25 --run-name='100k 5x5 runs' --indexed-split=0.1 --sync-partitions=8 > /dev/null
 ```
