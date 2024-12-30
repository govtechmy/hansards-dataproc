# hansards_pipelines

This is a [Dagster](https://dagster.io/) project scaffolded with [`dagster project scaffold`](https://docs.dagster.io/getting-started/create-new-project).

## Getting started

First, install your Dagster code location as a Python package. By using the --editable flag, pip will install your Python package in ["editable mode"](https://pip.pypa.io/en/latest/topics/local-project-installs/#editable-installs) so that as you develop, local code changes will automatically apply.

```bash
pip install -e ".[dev]"
```

Then, start the Dagster UI web server:

```bash
dagster dev
```

Open http://localhost:3000 with your browser to see the project.

You can start writing assets in `hansards_pipelines/assets.py`. The assets are automatically loaded into the Dagster code location as you define them.

## Development


### Adding new Python dependencies

You can specify new Python dependencies in `setup.py`.

### Unit testing

Tests are in the `hansards_pipelines_tests` directory and you can run tests using `pytest`:

```bash
pytest hansards_pipelines_tests
```

### Schedules and sensors

If you want to enable Dagster [Schedules](https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules) or [Sensors](https://docs.dagster.io/concepts/partitions-schedules-sensors/sensors) for your jobs, the [Dagster Daemon](https://docs.dagster.io/deployment/dagster-daemon) process must be running. This is done automatically when you run `dagster dev`.

Once your Dagster Daemon is running, you can start turning on schedules and sensors for your jobs.

## Deploy on EKS

```
sudo yum install openssl-devel bzip2-devel libffi-devel zlib-devel sqlite-devel -y

cd /opt
sudo wget https://www.python.org/ftp/python/3.11.4/Python-3.11.4.tgz
sudo tar xzf Python-3.11.4.tgz

cd Python-3.11.4
sudo ./configure --enable-optimizations --enable-loadable-sqlite-extensions
```


### Setup dagster home
```
# Create Dagster home directory
sudo mkdir -p /opt/dagster/dagster_home
sudo chown -R ec2-user:ec2-user /opt/dagster

# Create logs directory
sudo mkdir -p /opt/dagster/dagster_home/logs
sudo chown -R ec2-user:ec2-user /opt/dagster/dagster_home/logs
```

### Setup service
```
sudo cp hansards_pipelines/service/dagster-daemon.service /etc/systemd/system
sudo cp hansards_pipelines/service/dagster-webserver.service /etc/systemd/system

```