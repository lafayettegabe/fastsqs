from setuptools import setup, find_packages

setup(
    name="fastsqs",
    version="0.3.5",
    description="FastAPI-like, modern async SQS message processing for Python with advanced features",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Gabriel LaFayette",
    author_email="gabriel.lafayette@proton.me",
    url="https://github.com/lafayettegabe/fastsqs",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0"
    ],
    extras_require={
        "dynamodb": ["boto3>=1.26.0", "aioboto3>=12.0.0"],
        "idempotency": ["boto3>=1.26.0", "aioboto3>=12.0.0"],
        "telemetry": [
            "opentelemetry-sdk>=1.32.1",
            "opentelemetry-exporter-otlp>=1.32.1",
            "opentelemetry-instrumentation>=0.53b1",
            "elasticsearch>=8.11.1"
        ],
        "all": [
            "boto3>=1.26.0",
            "aioboto3>=12.0.0",
            "opentelemetry-sdk>=1.32.1",
            "opentelemetry-exporter-otlp>=1.32.1",
            "opentelemetry-instrumentation>=0.53b1",
            "elasticsearch>=8.11.1"
        ],
    },
    python_requires=">=3.8",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    keywords="sqs aws lambda serverless async fastapi pydantic message-processing",
    include_package_data=True,
)
