import sys
import os

import _use_application_modules # pylint: disable=unused-import

from core.mesh_loader import MeshLoader

def main():
    """Main function to test mesh loader."""
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_mesh_file>")
        return 1

    mesh_path = os.path.expanduser(sys.argv[1])

    if not os.path.exists(mesh_path):
        print(f"Error: File does not exist: {mesh_path}")
        return 1

    print(f"Loading mesh file: {mesh_path}")

    loader = MeshLoader()
    mesh_data = loader.load_from_file(mesh_path)
    if mesh_data is None:
        print("Failed to load mesh data")
        return 1
    print("Mesh loaded successfully")
    print(f"Faces: {mesh_data.face_count}")
    print(f"Vertices: {mesh_data.vertex_count}")

if __name__ == "__main__":
    main()
