# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install Git and other dependencies
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables
ENV MODULE_NAME main
ENV VARIABLE_NAME app
ENV MODULES_DIR=/app/modules
ENV GIT_REPO_URL=""
ENV GIT_USERNAME=""
ENV GIT_TOKEN=""
ENV GIT_BRANCH="main"
ENV GIT_SYNC_ON_STARTUP="false"

# Run the application using Uvicorn
# Use 0.0.0.0 to make it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]