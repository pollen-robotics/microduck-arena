FROM python:3.12-slim

# git, for the shallow clones of the two datasets (app.py). No git-lfs: the dashboard reads
# only small JSON files, and LFS files stay pointers.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user app.py stats.py page.html ./

CMD ["python", "app.py"]
