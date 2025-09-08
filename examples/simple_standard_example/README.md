# Simple Standard Queue Example

This example demonstrates basic usage of FastSQS with Standard SQS queues.

## Features

- Basic message routing based on message type
- Standard queue processing (parallel processing)
- Simple event handling

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the example
python lambda_function.py
```

## What it demonstrates

- Creating a FastSQS app with default Standard queue type
- Basic routing with SQSRouter
- Processing multiple messages in parallel
- Simple message handling without FIFO-specific attributes

## Expected Output

The example will process three messages and show how Standard queues handle parallel processing.
