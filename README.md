# SUIT ALPPS Tool

Automates ALPPS science proposal submissions for the SUIT instrument using Selenium.

## Example JSON Files

- `science-proposal-workflow.json`: Defines the automation workflow as a list of steps (actions like click, input, select, upload, repeat, etc.). Each step can reference variables, perform actions, and control browser flow.
- `synopticnb3nb5.json`: Provides data values for variables used in the workflow, such as proposal details, durations, file paths, and repeat counts. These values are substituted into the workflow at runtime.

Variables in the workflow can be referenced as `${VAR_NAME}` and will be replaced by values from the data JSON or environment variables.

## Quick Start
1. Install dependencies:
	```zsh
	pip install -r requirements.txt
	```
2. Run:
	```zsh
	python runner.py science-proposal-workflow.json synopticnb3nb5.json
	```

Requires Python 3.8+, Chrome, and dependencies in `requirements.txt`.
