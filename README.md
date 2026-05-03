# SwiftDeploy

A declarative deployment CLI that generates all config files from a single `manifest.yaml`.

## Requirements

- Docker
- Docker Compose plugin
- Python 3 + PyYAML (`sudo apt install python3-yaml`)

## Setup

Clone the repo and build the image:

```bash
git clone https://github.com/Precious000/swiftdeploy.git
cd swiftdeploy
docker build -t swift-deploy-1-node:latest .
```

## Subcommands

### init
Generates nginx.conf and docker-compose.yml from manifest.yaml
```bash
./swiftdeploy init
```

### validate
Runs 5 pre-flight checks before deploying
```bash
./swiftdeploy validate
```

### deploy
Runs init, starts the stack, waits for health checks to pass
```bash
./swiftdeploy deploy
```

### promote
Switches between stable and canary mode with a rolling restart
```bash
./swiftdeploy promote canary
./swiftdeploy promote stable
```

### teardown
Stops and removes all containers, networks, and volumes
```bash
./swiftdeploy teardown
./swiftdeploy teardown --clean
```

## How it works

1. Edit `manifest.yaml` — the only file you ever touch
2. Run `./swiftdeploy deploy` — everything else is generated automatically
3. Nginx listens on port 8080 and proxies to the Python app on port 3000
4. All traffic routes through Nginx — the app port is never exposed directly
