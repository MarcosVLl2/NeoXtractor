import json
import struct
import base64

from core.mesh_loader.parsers import MeshData

NAME = "glTF 2.0 Format"
EXTENSION = ".gltf"

def convert(mesh: MeshData) -> bytes:
    """
    Convert mesh to glTF format.
    
    Parameters:
    - mesh: MeshData object containing bones, vertices, faces, etc.
    
    Returns:
    - bytes: glTF file content as bytes (JSON with embedded binary data)
    """
    gltf_data = {
        "asset": {
            "version": "2.0",
            "generator": "NeoX Model Converter"
        },
        "meshes": [],
        "accessors": [],
        "bufferViews": [],
        "buffers": [],
        "nodes": [],
        "skins": [],
        "scenes": [{"nodes": [0]}],
        "scene": 0
    }

    # Extract mesh data using MeshData properties
    positions = mesh.position
    normals = mesh.normal if mesh.has_normals else []
    uvs = mesh.uv if mesh.has_uvs else []
    indices = mesh.face

    if not positions or not indices:
        raise ValueError("Mesh must contain positions and face indices.")

    # Prepare binary buffers
    vertex_buffer = []
    for x, y, z in positions:
        vertex_buffer.extend([x, y, z])

    normal_buffer = []
    if normals:
        for nx, ny, nz in normals:
            normal_buffer.extend([nx, ny, nz])

    uv_buffer = []
    if uvs:
        for u, v in uvs:
            uv_buffer.extend([u, v])

    index_buffer = [idx for face in indices for idx in face]

    # Handle bone data if available - but disable skinning to avoid mesh distortion
    # Skip all bone skinning data to prevent mesh distortion
    # The bones will be created as nodes but not applied to the mesh
    joint_buffer = []
    weight_buffer = []
    inverse_bind_matrices = []

    # Create binary buffer
    binary_data = bytearray()

    # Add vertex data
    binary_data.extend(struct.pack(f"{len(vertex_buffer)}f", *vertex_buffer))
    vertex_bytes = len(vertex_buffer) * 4

    # Add normal data
    normal_offset = len(binary_data)
    if normal_buffer:
        binary_data.extend(struct.pack(f"{len(normal_buffer)}f", *normal_buffer))
    normal_bytes = len(normal_buffer) * 4

    # Add UV data
    uv_offset = len(binary_data)
    if uv_buffer:
        binary_data.extend(struct.pack(f"{len(uv_buffer)}f", *uv_buffer))
    uv_bytes = len(uv_buffer) * 4

    # Add index data
    index_offset = len(binary_data)
    binary_data.extend(struct.pack(f"{len(index_buffer)}H", *index_buffer))
    index_bytes = len(index_buffer) * 2

    # Add joint data
    joint_offset = len(binary_data)
    joint_bytes = 0
    if joint_buffer:
        binary_data.extend(struct.pack(f"{len(joint_buffer)}H", *joint_buffer))
        joint_bytes = len(joint_buffer) * 2

    # Add weight data
    weight_offset = len(binary_data)
    weight_bytes = 0
    if weight_buffer:
        binary_data.extend(struct.pack(f"{len(weight_buffer)}f", *weight_buffer))
        weight_bytes = len(weight_buffer) * 4

    # Add inverse bind matrices
    ibm_offset = len(binary_data)
    ibm_bytes = 0
    if inverse_bind_matrices:
        binary_data.extend(struct.pack(f"{len(inverse_bind_matrices)}f", *inverse_bind_matrices))
        ibm_bytes = len(inverse_bind_matrices) * 4

    # Create data URI for embedded binary data
    binary_b64 = base64.b64encode(binary_data).decode('utf-8')
    data_uri = f"data:application/octet-stream;base64,{binary_b64}"

    # Buffer definition
    gltf_data["buffers"].append({
        "uri": data_uri,
        "byteLength": len(binary_data)
    })

    # BufferViews
    buffer_view_index = 0

    # Position buffer view
    gltf_data["bufferViews"].append({
        "buffer": 0,
        "byteOffset": 0,
        "byteLength": vertex_bytes,
        "target": 34962  # ARRAY_BUFFER
    })
    position_buffer_view = buffer_view_index
    buffer_view_index += 1

    # Normal buffer view
    normal_buffer_view = None
    if normal_bytes > 0:
        gltf_data["bufferViews"].append({
            "buffer": 0,
            "byteOffset": normal_offset,
            "byteLength": normal_bytes,
            "target": 34962
        })
        normal_buffer_view = buffer_view_index
        buffer_view_index += 1

    # UV buffer view
    uv_buffer_view = None
    if uv_bytes > 0:
        gltf_data["bufferViews"].append({
            "buffer": 0,
            "byteOffset": uv_offset,
            "byteLength": uv_bytes,
            "target": 34962
        })
        uv_buffer_view = buffer_view_index
        buffer_view_index += 1

    # Index buffer view
    gltf_data["bufferViews"].append({
        "buffer": 0,
        "byteOffset": index_offset,
        "byteLength": index_bytes,
        "target": 34963  # ELEMENT_ARRAY_BUFFER
    })
    index_buffer_view = buffer_view_index
    buffer_view_index += 1

    # Joint buffer view
    joint_buffer_view = None
    if joint_bytes > 0:
        gltf_data["bufferViews"].append({
            "buffer": 0,
            "byteOffset": joint_offset,
            "byteLength": joint_bytes,
            "target": 34962
        })
        joint_buffer_view = buffer_view_index
        buffer_view_index += 1

    # Weight buffer view
    weight_buffer_view = None
    if weight_bytes > 0:
        gltf_data["bufferViews"].append({
            "buffer": 0,
            "byteOffset": weight_offset,
            "byteLength": weight_bytes,
            "target": 34962
        })
        weight_buffer_view = buffer_view_index
        buffer_view_index += 1

    # Inverse bind matrices buffer view
    ibm_buffer_view = None
    if ibm_bytes > 0:
        gltf_data["bufferViews"].append({
            "buffer": 0,
            "byteOffset": ibm_offset,
            "byteLength": ibm_bytes
        })
        ibm_buffer_view = buffer_view_index
        buffer_view_index += 1

    # Calculate position bounds
    min_position = [min(coord) for coord in zip(*positions)]
    max_position = [max(coord) for coord in zip(*positions)]

    # Accessors
    accessor_index = 0

    # Position accessor
    gltf_data["accessors"].append({
        "bufferView": position_buffer_view,
        "componentType": 5126,  # FLOAT
        "count": len(positions),
        "type": "VEC3",
        "min": min_position,
        "max": max_position
    })
    position_accessor = accessor_index
    accessor_index += 1

    # Normal accessor
    normal_accessor = None
    if normal_buffer_view is not None:
        gltf_data["accessors"].append({
            "bufferView": normal_buffer_view,
            "componentType": 5126,
            "count": len(normals),
            "type": "VEC3"
        })
        normal_accessor = accessor_index
        accessor_index += 1

    # UV accessor
    uv_accessor = None
    if uv_buffer_view is not None:
        gltf_data["accessors"].append({
            "bufferView": uv_buffer_view,
            "componentType": 5126,
            "count": len(uvs),
            "type": "VEC2"
        })
        uv_accessor = accessor_index
        accessor_index += 1

    # Index accessor
    gltf_data["accessors"].append({
        "bufferView": index_buffer_view,
        "componentType": 5123,  # UNSIGNED_SHORT
        "count": len(index_buffer),
        "type": "SCALAR"
    })
    index_accessor = accessor_index
    accessor_index += 1

    # Joint accessor
    joint_accessor = None
    if joint_buffer_view is not None:
        gltf_data["accessors"].append({
            "bufferView": joint_buffer_view,
            "componentType": 5123,  # UNSIGNED_SHORT
            "count": len(joint_buffer) // 4,
            "type": "VEC4"
        })
        joint_accessor = accessor_index
        accessor_index += 1

    # Weight accessor
    weight_accessor = None
    if weight_buffer_view is not None:
        gltf_data["accessors"].append({
            "bufferView": weight_buffer_view,
            "componentType": 5126,
            "count": len(weight_buffer) // 4,
            "type": "VEC4"
        })
        weight_accessor = accessor_index
        accessor_index += 1

    # Inverse bind matrices accessor
    ibm_accessor = None
    if ibm_buffer_view is not None:
        gltf_data["accessors"].append({
            "bufferView": ibm_buffer_view,
            "componentType": 5126,
            "count": len(inverse_bind_matrices) // 16,
            "type": "MAT4"
        })
        ibm_accessor = accessor_index
        accessor_index += 1

    # Create mesh primitive
    attributes = {"POSITION": position_accessor}
    if normal_accessor is not None:
        attributes["NORMAL"] = normal_accessor
    if uv_accessor is not None:
        attributes["TEXCOORD_0"] = uv_accessor
    # Skip bone attributes to prevent mesh distortion
    # TODO: see if it's fixable
    # if joint_accessor is not None:
    #     attributes["JOINTS_0"] = joint_accessor
    # if weight_accessor is not None:
    #     attributes["WEIGHTS_0"] = weight_accessor

    primitive = {
        "attributes": attributes,
        "indices": index_accessor
    }

    gltf_data["meshes"].append({
        "primitives": [primitive]
    })

    # Create nodes
    if mesh.has_bones:
        bone_names = mesh.bone_name
        bone_hierarchy = mesh.bone_parent
        
        # Create bone nodes with proper hierarchy
        for i, bone_name in enumerate(bone_names):
            node = {
                "name": bone_name,
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0]
            }

            # Add children (bones that have this bone as parent)
            children = [j for j, parent in enumerate(bone_hierarchy) if parent == i]
            if children:
                node["children"] = children

            gltf_data["nodes"].append(node)

        # Create mesh node without skin (to prevent distortion)
        gltf_data["nodes"].append({
            "name": "Mesh",
            "mesh": 0
        })

        # Find root bones (those with parent -1) and create scene structure
        root_bones = [i for i, parent in enumerate(bone_hierarchy) if parent == -1]
        mesh_node_index = len(bone_names)

        # Update scene to include root bones and mesh separately
        gltf_data["scenes"][0]["nodes"] = root_bones + [mesh_node_index]
    else:
        # Create simple mesh node
        gltf_data["nodes"].append({
            "name": "Mesh",
            "mesh": 0
        })

    # Convert to JSON and return as bytes
    json_string = json.dumps(gltf_data, separators=(',', ':'))
    return json_string.encode('utf-8')
