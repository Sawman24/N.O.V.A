# Nova Desktop App (Mac & Windows)

The Nova Desktop App allows you to run Nova's chat interface locally on your personal Mac or Windows PC while connecting to a remote Nova server. It includes a built-in RPC daemon that enables Nova to securely execute local commands and manage local files on your machine when requested.

## Features

- **Cross-Platform**: Runs natively on macOS and Windows.
- **Native Webview**: Native OS UI window rendering the Nova frontend.
- **Local RPC Daemon**: Executes local shell commands and document/file operations on your PC when Nova calls remote execution tools.

## Setup & Running

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Desktop App

Point to your remote Nova server (defaults to `http://localhost:8000`):

```bash
python main.py http://your-remote-server-ip:8000
```

## Building Native App (.app / .exe)

To bundle Nova into a standalone application (`.app` on macOS, `.exe` on Windows):

```bash
python build.py
```

The output executable will be created inside `desktop_client/dist/`.
