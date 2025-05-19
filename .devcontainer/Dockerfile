FROM mcr.microsoft.com/devcontainers/miniconda:1.1-3

# Configure conda
RUN conda config --set channel_priority strict

RUN conda install -y python=3.10
# RUN conda install -y -c conda-forge "ta-lib=0.5.1" # regularly check back with https://anaconda.org/conda-forge/ta-lib for updates on the latest version that conda can install

# TODO: Uncomment the following ONLY when we want to use lint and reformat markdown files with `markdownlint-cli2-auto-fix.mdc` or else we can just rely on the markdownlint extension: `davidanson.vscode-markdownlint`
# RUN apt-get update && apt-get install -y curl && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && apt-get install -y nodejs && runuser -u vscode -- npm config set prefix '~/.local' && apt-get clean && rm -rf /var/lib/apt/lists/*
# RUN npm install -g markdownlint-cli2

# Install and upgrade pip
RUN pip3 install --upgrade pip

# All Python dependencies are now managed through pyproject.toml
# and installed via the postCreateCommand in devcontainer.json
# which uses pip install -e '.[dev]'

# Add .local/bin to PATH for the vscode user to remove WARNINGs
RUN echo "export PATH=\$PATH:/home/vscode/.local/bin" >> /home/vscode/.bashrc
