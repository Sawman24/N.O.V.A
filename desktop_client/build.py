import sys
import os
import subprocess


def build_desktop_app():
    print("[Build Script] Building N.O.V.A Desktop App...")
    
    script_path = os.path.join(os.path.dirname(__file__), "main.py")
    dist_path = os.path.join(os.path.dirname(__file__), "dist")
    build_path = os.path.join(os.path.dirname(__file__), "build")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=NovaDesktop",
        "--onefile",
        "--noconsole",
        f"--distpath={dist_path}",
        f"--workpath={build_path}",
        script_path,
    ]

    if sys.platform == "darwin":
        cmd.append("--windowed")
        print("[Build Script] Target OS: macOS (.app bundle)")
    elif sys.platform == "win32":
        print("[Build Script] Target OS: Windows (.exe binary)")

    try:
        subprocess.run(cmd, check=True)
        print(f"\n[Build Script] Successfully built NovaDesktop in: {dist_path}")
    except subprocess.CalledProcessError as e:
        print(f"\n[Build Script] Build failed: {e}")


if __name__ == "__main__":
    build_desktop_app()
