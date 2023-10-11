# Load generator to Neptune Server


## Installation and setup

Please install the latest vesrion of neptune client (release candidate)
```
pip install neptune==1.8.3rc1
```

You need to remember about setting neptune token and project enviroments. *Use the token of the Neptune instance you want to use*.
```
export NEPTUNE_API_TOKEN="YOUR TOKEN"
export NEPTUNE_PROJECT="YOUR PROJECT" # "dzwiedziu/load-test"
```

It is also advice to increase a limit of open files (neptune-client has separate sync-files for each run).
```
ulimit -Sn 1000000
```


## Example configurations


20 runs, sending 20 steps every 10 seconds, in each step 100 series and 100 atoms

```
python3 load_test.py --processes=4 --runs 5 --steps 20 --series 100 --atoms 100 --step-time=10 --threads=1 --run-name='warmup' --indexed-split=0.5
```


100 runs, sending 20 steps every 25 seconds, in each step 5000 series and 100 atoms

```
python3 load_test.py --processes=10 --runs 10 --steps 20 --series 5000 --atoms 100 --step-time=25 --threads=1 --run-name='low 100x5000' --indexed-split=0.5
```

200 runs, sending 100 steps every 25 seconds, in each step 9000 series and 500 atoms

```
python3 load_test.py --processes=20 --runs 10 --steps 20 --series 9000 --atoms 500 --step-time=25 --threads=1 --run-name='medium 200x9500' --indexed-split=0.5
```


1200 runs, sending 144 (~1 hour) steps every 25 seconds, in each step 9500 series and 100 atoms

This may be too big to be executed on one machine / laptop.

```
python3 load_test.py --processes=120 --runs 10 --steps 144 --series 9500 --atoms 100 --step-time=25 --threads=1 --run-name='high 1200x9500' --indexed-split=0.5
```