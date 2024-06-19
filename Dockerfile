# Use Ubuntu as the base image
FROM ubuntu:20.04

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH /opt/conda/bin:$PATH

# Fix potential issues with downloading packages and clean up the package lists
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get update -o Acquire::CompressionTypes::Order::=gz \
    && apt-get -o Acquire::http::No-Cache=True -o Acquire::BrokenProxy=true update

# Install system dependencies
RUN apt-get install -y wget bash gcc libc6-dev libffi-dev libssl-dev make postgresql-client libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh \
    && /bin/bash ~/miniconda.sh -b -p /opt/conda \
    && rm ~/miniconda.sh

# Set PATH for conda
ENV PATH /opt/conda/bin:$PATH

# Create a Conda environment
COPY environment.yml /app/
RUN conda env create -f /app/environment.yml

# Activate the Conda environment
SHELL ["conda", "run", "-n", "stest_env", "/bin/bash", "-c"]

# Set the working directory in the container
WORKDIR /app

# Copy the application
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Start Gunicorn
CMD ["conda", "run", "-n", "stest_env", "gunicorn", "--bind", "0.0.0.0:8000", "sTest.wsgi:application"]
