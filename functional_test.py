import neptune
import random
import string


def add_chart_1M(run):
    namespace = "metrics/loss_1M"
    num_steps = 1000000
    decay = 0.9995
    init_metric = 0.98

    floor = 0.2 + (random.random() - 0.5) * 0.15
    anomaly_step = int(random.uniform(0.3, 0.6) * num_steps)
    fluctuation = init_metric - floor

    for i in range(num_steps):
        if (i + 1) % anomaly_step == 0:
            run[namespace].append(init_metric + random.random() * 0.5)
        else:
            run[namespace].append(init_metric)

        init_metric = init_metric - (init_metric - floor) * (1 - decay) + (random.random() - 0.5) * 0.005 * (
            fluctuation) * 3

        if init_metric > 1:
            init_metric = 0.99
        elif init_metric < 0.001:
            init_metric = 0.005


def add_chart_10K(run):
    namespace = "metrics/loss_10K"
    num_steps = 10000
    decay = 0.9995
    init_metric = 0.98

    floor = 0.2 + (random.random() - 0.5) * 0.15
    anomaly_step = int(random.uniform(0.3, 0.6) * num_steps)
    fluctuation = init_metric - floor

    for i in range(num_steps):
        if (i + 1) % anomaly_step == 0:
            run[namespace].append(init_metric + random.random() * 0.5)
        else:
            run[namespace].append(init_metric)

        init_metric = init_metric - (init_metric - floor) * (1 - decay) + (random.random() - 0.5) * 0.005 * (
            fluctuation) * 3

        if init_metric > 1:
            init_metric = 0.99
        elif init_metric < 0.001:
            init_metric = 0.005


def add_100K_fields(run):
    for i in range(100):
        for j in range(99):
            namespace = f"metrics/l_{i}/{''.join(random.choices(string.ascii_lowercase, k=5))}"
            run[namespace] = random.random()
    for i in range(91000):
        namespace = f"metrics/l_{i+100}/{random.randint(0, 10)}"
        run[namespace] = random.random()


def add_100_fields(run):
    for i in range(100):
        namespace = f"metrics/l_{i}"
        run[namespace] = random.random()


if __name__ == "__main__":

    print("Running 1M length series test...")
    runs = [neptune.init_run(enable_remote_signals=False) for i in range(10)]
    for run in runs:
        add_chart_1M(run)
    for run in runs:
        run.stop()
    print("1M length series test finished")

    print("Running 10K length series test...")
    runs = [neptune.init_run(enable_remote_signals=False) for i in range(200)]
    for run in runs:
        add_chart_10K(run)
    for run in runs:
        run.stop()
    print("10K length series test finished")

    print("Running 100K fields test...")
    run = neptune.init_run(enable_remote_signals=False)
    add_100K_fields(run)
    run.stop()
    print("100K fields test finished")

    print("Running Artifact / File Upload test...")
    run = neptune.init_run(enable_remote_signals=False)
    run["artifact"].track_files("./random.png")
    run["fie"].upload("./random.png")
    run.stop()
    print("Artifact / File Upload test finished")
