from setuptools import setup, find_packages

setup(
    name="fastsqs",
    version="0.1.3",
    description="Async SQS routing and middleware library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Gabriel LaFayette",
    author_email="gabriel.lafayette@proton.me",
    url="https://github.com/lafayettegabe/fastsqs",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0"
    ],
    python_requires=">=3.8",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
)
