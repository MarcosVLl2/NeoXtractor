"""Script for building all shaders in the project."""

import os
import subprocess
import textwrap

project_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

for filename in os.listdir(os.path.join(project_dir, "shaders")):
    if filename.endswith(".vert") or filename.endswith(".frag"):
        shader_path = os.path.join(project_dir, "shaders", filename)
        output_path = os.path.join(project_dir, "data", "shaders", filename + ".qsb")
        result = subprocess.run(
                ["pyside6-qsb", "--qt6", shader_path, "-o", output_path],
                capture_output=True,
                check=False
            )
        if result.returncode == 0:
            print(f"> Built shader {filename} (to {filename + ".qsb"}) successfully.")
        else:
            print(f"> Error building shader {filename}")
            print(textwrap.indent(result.stderr.decode(), "-> "))
