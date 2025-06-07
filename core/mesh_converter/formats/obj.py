from core.mesh_loader.parsers import MeshData

NAME = "Wavefront OBJ Format"
EXTENSION = ".obj"

def convert(mesh: MeshData, flip_uv=False) -> bytes:
    """
    Convert mesh to OBJ format as a static mesh without skeleton.
    
    Parameters:
    - mesh: MeshData object to be converted to OBJ format.
    - flip_uv: Boolean to indicate whether to flip the UV coordinates on the Y-axis.
    
    Returns:
    - bytes: OBJ file content as bytes
    """
    obj_lines = []
    obj_lines.append("o mesh\n")

    # Write vertices
    for v in mesh.position:
        obj_lines.append(f"v {v[0]} {v[1]} {v[2]}\n")

    # Write normals if available
    if mesh.has_normals:
        for n in mesh.normal:
            obj_lines.append(f"vn {n[0]} {n[1]} {n[2]}\n")

    vertex_offset = 0
    face_offset = 0

    # Handle sub-meshes and write UVs and faces separately
    if mesh.mesh:
        for i, (mesh_vertex_count, mesh_face_count, _, _) in enumerate(mesh.mesh):
            obj_lines.append(f"g Sub-mesh_{i}\n")

            # Write UVs for this sub-mesh
            for uv in mesh.uv[vertex_offset:vertex_offset + mesh_vertex_count]:
                if flip_uv:
                    uv = (uv[0], 1 - uv[1])  # Flip UV on the Y axis
                obj_lines.append(f"vt {uv[0]} {uv[1]}\n")

            # Write faces, adjusting for vertex offset
            for v1, v2, v3 in mesh.face[face_offset:face_offset + mesh_face_count]:
                obj_lines.append(f"f {v1 + 1}/{v1 + 1} {v2 + 1}/{v2 + 1} {v3 + 1}/{v3 + 1}\n")

            # Update the offsets for the next sub-mesh
            vertex_offset += mesh_vertex_count
            face_offset += mesh_face_count
    else:
        # Handle case where there are no sub-meshes
        if mesh.has_uvs:
            for uv in mesh.uv:
                if flip_uv:
                    uv = (uv[0], 1 - uv[1])  # Flip UV on the Y axis
                obj_lines.append(f"vt {uv[0]} {uv[1]}\n")

        # Write all faces
        for v1, v2, v3 in mesh.face:
            if mesh.has_uvs:
                obj_lines.append(f"f {v1 + 1}/{v1 + 1} {v2 + 1}/{v2 + 1} {v3 + 1}/{v3 + 1}\n")
            else:
                obj_lines.append(f"f {v1 + 1} {v2 + 1} {v3 + 1}\n")

    # Write bone information as comments
    if mesh.has_bones:
        obj_lines.append("\n# Bone Information\n")
        for i, bone_name in enumerate(mesh.bone_name):
            parent = mesh.bone_parent[i]
            obj_lines.append(f"# Bone: {bone_name}, Parent: {parent}\n")

    return ''.join(obj_lines).encode('utf-8')
