from setuptools import find_packages, setup

setup(
    name="hansards_pipelines",
    packages=find_packages(exclude=["hansards_pipelines_tests"]),
    install_requires=["dagster", "dagster-cloud"],
    extras_require={"dev": ["dagster-webserver", "pytest"]},
)
