# 1. Functional test to Neptune Server

- Export  the following Environmen variables:
  - ```export NEPTUNE_PROJECT=<Your Project>```
  - ```export NEPTUNE_API_TOKEN=<Your API Token>```
- Run the following script:
  - ```python3 functional_test.py```

# 2. Load generator to Neptune Server


## Installation and setup

Please install the latest vesrion of neptune client (release candidate)
```
pip install neptune==1.8.3rc2
```

You need to remember about setting neptune token and project enviroments. *Use the token of the Neptune instance you want to use*.
```
export NEPTUNE_API_TOKEN="YOUR TOKEN"
export NEPTUNE_PROJECT="YOUR PROJECT" # "dzwiedziu/load-test"
```

It is also adviced to increase a limit of open files (neptune-client has separate sync-files for each run).
```
ulimit -Sn 1000000
```


## Example configurations


20 runs, sending 20 steps every 10 seconds, in each step 100 series and 100 atoms

```
python3 load_generator.py --processes=4 --runs 5 --steps 20 --series 100 --atoms 100 --step-time=10 --run-name='warmup' --indexed-split=0.5  > /dev/null
```


100 runs, sending 20 steps every 25 seconds, in each step 5000 series and 100 atoms

```
python3 load_generator.py --processes=10 --runs 10 --steps 20 --series 5000 --atoms 100 --step-time=25 --run-name='low 100x5000' --indexed-split=0.5  > /dev/null
```

200 runs, sending 100 steps every 25 seconds, in each step 9000 series and 500 atoms

```
python3 load_generator.py --processes=20 --runs 10 --steps 20 --series 9000 --atoms 500 --step-time=25 --run-name='medium 200x9500' --indexed-split=0.5  > /dev/null
```


1200 runs, sending 144 (~1 hour) steps every 25 seconds, in each step 9500 series and 100 atoms

This may be too big to be executed on one machine / laptop.

```
python3 load_generator.py --processes=120 --runs 10 --steps 144 --series 9500 --atoms 100 --step-time=25 --run-name='high 1200x9500' --indexed-split=0.5 > /dev/null
```

## 100K attributes runs

For bigger runs you may want to use experimental version of Neptune Client, that parallelize the syncronization process of a run.
```
pip install git+https://github.com/neptune-ai/neptune-client.git@partitioned
```

Normally, you also need to set env variables but in this case, load generator will do it for you via setting `--sync-partitions=4` flag.
```
export NEPTUNE_MODE=experimental
export NEPTUNE_ASYNC_PARTITIONS_NUMBER=8
```

Check it out with 4 runs
```
 python3 load_generator.py --processes=2 --runs 2 --steps 20 --series 99000 --atoms 100 --step-time=25 --run-name='100k 2x2 runs' --indexed-split=0.1 --sync-partitions=12 > /dev/null
 ```

And now with 25 runs
```
 python3 load_generator.py --processes=5 --runs 5 --steps 20 --series 99000 --atoms 100 --step-time=25 --run-name='100k 5x5 runs' --indexed-split=0.1 --sync-partitions=8 > /dev/null
 ```
