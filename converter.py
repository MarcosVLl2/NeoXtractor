import os, io
import struct, math, argparse
import numpy as np
import json
import transformations as tf
import pymeshio.pmx as pmx
import pymeshio.common as common
import pymeshio.pmx.writer
import pymeshio.pmx.reader
from bone_name import *

def readuint8(f):
    return int(struct.unpack('B', f.read(1))[0])

def readuint16(f):
    return int(struct.unpack('H', f.read(2))[0])

def readuint32(f):
    return struct.unpack('I', f.read(4))[0]

def readfloat(f):
    return struct.unpack('f', f.read(4))[0]

def get_parser():
    parser = argparse.ArgumentParser(description='NeoX Model Converter')
    parser.add_argument('path', type=str)
    parser.add_argument('--mode', type=str, choices=['obj', 'iqe', 'pmx', 'gltf', 'smd', 'ascii'], default='gltf')
    opt = parser.parse_args()
    return opt

def saveobj(model, filename, flip_uv=False):
    """
    Save model to OBJ format as a static mesh without skeleton.
    
    Parameters:
    - model: Dictionary with model data containing bones, vertices, faces, etc.
    - filename: The output OBJ filename.
    - flip_uv: Boolean to indicate whether to flip the UV coordinates on the Y-axis.
    """
    filename = filename.replace('.mesh', '.obj')

    try:
        with open(filename, 'w', encoding='utf-8') as f:  # Ensure encoding is set for text writing
            f.write(f"o {os.path.basename(filename)}\n")
            print("Started writing OBJ file...")

            # Write vertices
            print(f"Total vertices: {len(model['position'])}")
            for v in model['position']:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")

            # Write normals if available
            if 'normal' in model:
                print(f"Total normals: {len(model['normal'])}")
                for n in model['normal']:
                    f.write(f"vn {n[0]} {n[1]} {n[2]}\n")

            vertex_offset = 0
            face_offset = 0

            # Handle submeshes and write UVs and faces separately
            for i, (mesh_vertex_count, mesh_face_count, _, _) in enumerate(model['mesh']):
                print(f"Processing Submesh {i}: Vertices {mesh_vertex_count}, Faces {mesh_face_count}")
                f.write(f"g Submesh_{i}\n")

                # Write UVs for this submesh
                for uv in model['uv'][vertex_offset:vertex_offset + mesh_vertex_count]:
                    if flip_uv:
                        uv = (uv[0], 1 - uv[1])  # Flip UV on the Y axis
                    f.write(f"vt {uv[0]} {uv[1]}\n")

                # Write faces, adjusting for vertex offset
                for v1, v2, v3 in model['face'][face_offset:face_offset + mesh_face_count]:
                    f.write(f"f {v1 + 1}/{v1 + 1} {v2 + 1}/{v2 + 1} {v3 + 1}/{v3 + 1}\n")

                # Update the offsets for the next submesh
                vertex_offset += mesh_vertex_count
                face_offset += mesh_face_count

            print(f"Total faces: {len(model['face'])}")

            # Write bone information as comments
            if 'bone_name' in model and 'bone_parent' in model:
                f.write("\n# Bone Information\n")
                for i, bone_name in enumerate(model['bone_name']):
                    parent = model['bone_parent'][i]
                    f.write(f"# Bone: {bone_name}, Parent: {parent}\n")

        print(f"OBJ saved with {len(model['face'])} faces and {len(model['bone_name'])} bones.")

    except Exception as e:
        print(f"Failed to save OBJ: {e}")

def savesmd(model, filename, flip_uv=False):
    """
    Save model to Valve's SMD format as a reference (static) SMD.
    
    Parameters:
    - model: Dictionary with model data containing bones, vertices, faces, etc.
    - filename: The output SMD filename.
    - flip_uv: Boolean to indicate whether to flip the UV coordinates on the Y-axis.
    """
    
    filename = filename.replace('.mesh', '.smd')
    try:
        with open(filename, 'w') as smd_file:
            smd_file.write("version 1\n")

            # Bone Structure - Write nodes as in a static SMD
            smd_file.write("nodes\n")
            parent_child_dict = {}
            for i, parent in enumerate(model['bone_parent']):
                if parent not in parent_child_dict:
                    parent_child_dict[parent] = []
                parent_child_dict[parent].append(i)

            # Recursive function to build bone hierarchy
            def write_bone_hierarchy(index, parent_index):
                bone_name = model['bone_name'][index]
                smd_file.write(f"{index} \"{bone_name}\" {parent_index}\n")
                if index in parent_child_dict:
                    for child in parent_child_dict[index]:
                        write_bone_hierarchy(child, index)

            # Start with root bones
            root_index = model['bone_parent'].index(-1)
            write_bone_hierarchy(root_index, -1)
            smd_file.write("end\n")
            
            # Skeleton - Static, only the initial frame at time 0
            smd_file.write("skeleton\n")
            smd_file.write("time 0\n")
            for i, matrix in enumerate(model['bone_original_matrix']):
                x, y, z = tf.translation_from_matrix(matrix.T)
                smd_file.write(f"{i} {x:.6f} {y:.6f} {z:.6f}\n")
            smd_file.write("end\n")
            
            # Mesh Data - Vertices, Normals, UVs, and Faces
            smd_file.write("triangles\n")
            for face, mesh_data in enumerate(model['face']):
                material_name = f"material_{face}"
                for vertex_index in mesh_data:
                    pos = model['position'][vertex_index]
                    norm = model['normal'][vertex_index]
                    uv = model['uv'][vertex_index]
                    joint_indices = model['vertex_joint'][vertex_index]
                    weights = model['vertex_joint_weight'][vertex_index]
                    
                    # Flip UV if specified
                    if flip_uv:
                        uv = (uv[0], 1 - uv[1])
                    
                    # Write the material name once per triangle
                    smd_file.write(f"{material_name}\n")
                    
                    # Format: <bone ID> <x> <y> <z> <nx> <ny> <nz> <u> <v> <weight>
                    for joint_index, weight in zip(joint_indices, weights):
                        smd_file.write(f"{joint_index} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f} "
                                    f"{norm[0]:.6f} {norm[1]:.6f} {norm[2]:.6f} "
                                    f"{uv[0]:.6f} {uv[1]:.6f} {weight:.6f}\n")
            
            smd_file.write("end\n")
        print(f"SMD saved as static reference with {len(model['face'])} faces and {len(model['bone_name'])} bones.")
    except Exception as e:
        print(f"Failed to save SMD: {e}")
    
def savepmx(model, filename):
    pmx_model = pmx.Model()
    pmx_model.display_slots.append(pmx.DisplaySlot(u'表情', u'Exp', 1, None))
    pmx_model.english_name = u'Empty model'
    pmx_model.comment = u'NeoX Model Converterで生成'
    pmx_model.english_comment = u'Created by NeoX Model Converter.'

    parent_child_dict = {}
    old2new = {}
    index_pool = [-1]
    bone_pool = []
    for i in range(len(model['bone_parent'])):
        p = model['bone_parent'][i]
        if p not in parent_child_dict:
            parent_child_dict[p] = []
        parent_child_dict[p].append(i)

    def build_joint(index, parent_index):
        matrix = model['bone_original_matrix'][index]
        x, y, z = tf.translation_from_matrix(matrix.T)
        bone_pool.append(pmx.Bone(
                name=model['bone_name'][index],
                english_name=model['bone_name'][index],
                position=common.Vector3(-x, y, -z),
                parent_index=parent_index,
                layer=0,
                flag=0
            ))
        bone_pool[-1].setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
        bone_pool[-1].setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
        bone_pool[-1].setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)

    def deep_first_search(index, index_pool, parent_index):
        index_pool[0] += 1
        current_node_index = index_pool[0]
        old2new[index] = current_node_index
        build_joint(index, parent_index)
        if index in parent_child_dict:
            for child in parent_child_dict[index]:
                deep_first_search(child, index_pool, current_node_index)

    deep_first_search(model['bone_parent'].index(-1), index_pool, -1)

    pmx_model.bones = bone_pool

    for i in range(len(model['position'])):
        x, y, z = model['position'][i]
        nx, ny, nz = model['normal'][i]
        u, v = model['uv'][i]
        if 65535 in model['vertex_joint'][i]:
            vertex_joint_index = list(map(lambda x: old2new[x] if x != 65535 else 0,model['vertex_joint'][i]))
        else:
            vertex_joint_index = list(map(lambda x: old2new[x] if x != 255 else 0,model['vertex_joint'][i]))

        vertex = pmx.Vertex(
            common.Vector3(-x, y, -z),
            common.Vector3(-nx, ny, -nz),
            common.Vector2(u, v),
            pmx.Bdef4(*vertex_joint_index, *(model['vertex_joint_weight'][i])),
            0.0
        )
        pmx_model.vertices.append(vertex)

    for i in range(len(model['face'])):
        pmx_model.indices += list(model['face'][i])

    pmx_model.materials[0].vertex_count = len(model['face']) * 3

    ###########
    pmx_model.materials = []
    for i in range(len(model['mesh'])):
        _, mesh_face_count, _, _ = model['mesh'][i]
        pmx_model.materials.append(
            pmx.Material(u'Mat{}'.format(i)
                    , u'material{}'.format(i)
                    , common.RGB(1, 1, 1)
                    , 1.0
                    , 1
                    , common.RGB(1, 1, 1)
                    , common.RGB(0, 0, 0)
                    , 0
                    , common.RGBA(0, 0, 0, 1)
                    , 0
                    , -1
                    , -1
                    , pmx.MATERIALSPHERE_NONE
                    , 1
                    , 0
                    , u"comment"
                    , mesh_face_count * 3
            )
        )

    filename = filename.replace('.mesh', '')
    pymeshio.pmx.writer.write_to_file(pmx_model, filename + '.pmx')
    for bone in pmx_model.bones:
        if bone.english_name in paj_middle_bone_name:
            bone.position.x = 0.0

    if 'bip001_l_finger13'  in [bone.english_name for bone in pmx_model.bones]:
        paj_bone_name.update(paj_hand1_name)
    else:
        paj_bone_name.update(paj_hand0_name)

    for bone in pmx_model.bones:
        if bone.english_name in paj_bone_name:
            bone.name = paj_bone_name[bone.english_name][0]
            bone.english_name = paj_bone_name[bone.english_name][1]

    pymeshio.pmx.writer.write_to_file(pmx_model, filename + '_replace.pmx')

    def add_bone(pmxm, bone, index):
        assert index <= len(pmxm.bones)
        pmxm.bones.insert(index, bone)
        for bone in pmxm.bones:
            if bone.parent_index >= index:
                bone.parent_index += 1

        for vertex in pmxm.vertices:
            if vertex.deform.index0 >= index:
                vertex.deform.index0 += 1
            if vertex.deform.index1 >= index:
                vertex.deform.index1 += 1
            if vertex.deform.index2 >= index:
                vertex.deform.index2 += 1
            if vertex.deform.index3 >= index:
                vertex.deform.index3 += 1

        return index

    def find_bone_index_by_name(pmxm, bone_english_name):
        ret = None
        for i in range(len(pmxm.bones)):
            if pmxm.bones[i].english_name == bone_english_name:
                ret = i
                break
        return ret

    #######################
    try:
        parent_node_index = find_bone_index_by_name(pmx_model, 'ParentNode')

        center_bone = pmx.Bone(
                    name='センター',
                    english_name='Center',
                    position=common.Vector3(0, 8.0, 0),
                    parent_index=parent_node_index,
                    layer=0,
                    flag=0
                )
        center_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
        center_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
        center_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)

        waist_index = find_bone_index_by_name(pmx_model, 'Waist')
        center_index = add_bone(pmx_model, center_bone, waist_index)

        groove_bone = pmx.Bone(
                    name='グルーブ',
                    english_name='Groove',
                    position=common.Vector3(0, 8.2, 0),
                    parent_index=center_index,
                    layer=0,
                    flag=0
                )
        groove_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
        groove_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
        groove_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)
        waist_index = find_bone_index_by_name(pmx_model, 'Waist')
        groove_index = add_bone(pmx_model, groove_bone, waist_index)

        waist_index = find_bone_index_by_name(pmx_model, 'Waist')
        pmx_model.bones[waist_index].parent_index = groove_index

        waist_index = find_bone_index_by_name(pmx_model, 'Waist')
        upper_body_index = find_bone_index_by_name(pmx_model, 'UpperBody')
        pmx_model.bones[upper_body_index].parent_index = waist_index

        ##########################
        for LR in ['Left', 'Right']:
            ankle_index = find_bone_index_by_name(pmx_model, '{}Ankle'.format(LR))
            ankle_x, ankle_y, ankle_z = pmx_model.bones[ankle_index].position.to_tuple()
            toe_index = find_bone_index_by_name(pmx_model, '{}Toe'.format(LR))
            toe_vec = pmx_model.bones[toe_index].position
            toe_vec.y = ankle_y - 1.0
            toe_vec.z = -1.65
            leg_ik_parent_bone = pmx.Bone(
                    name='左足IK親' if LR == 'Left' else '右足IK親',
                    english_name='{}LegIkParent'.format(LR),
                    position=common.Vector3(ankle_x, 0, ankle_z),
                    parent_index=parent_node_index,
                    layer=0,
                    flag=0
                )
            leg_ik_parent_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
            leg_ik_parent_bone.setFlag(pmx.BONEFLAG_CAN_TRANSLATE, True)
            leg_ik_parent_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
            leg_ik_parent_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)
            leg_ik_parent_index = add_bone(pmx_model, leg_ik_parent_bone, len(pmx_model.bones))

            leg_ik_bone = pmx.Bone(
                    name='左足ＩＫ' if LR == 'Left' else '右足ＩＫ',
                    english_name='{}LegIk'.format(LR),
                    position=common.Vector3(ankle_x, ankle_y, ankle_z),
                    parent_index=leg_ik_parent_index,
                    layer=0,
                    flag=0
                )

            leg_ik_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
            leg_ik_bone.setFlag(pmx.BONEFLAG_CAN_TRANSLATE, True)
            leg_ik_bone.setFlag(pmx.BONEFLAG_IS_IK, True)
            leg_ik_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
            leg_ik_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)

            knee_index = find_bone_index_by_name(pmx_model, '{}Knee'.format(LR))
            leg_index = find_bone_index_by_name(pmx_model, '{}Leg'.format(LR))
            leg_ik_link = [
                pmx.IkLink(knee_index, 1, common.Vector3(-180.0/57.325, 0, 0), common.Vector3(-0.5/57.325, 0, 0)),
                pmx.IkLink(leg_index, 0)
            ]
            leg_ik_bone.ik = pmx.Ik(ankle_index, 40, 2, leg_ik_link)
            leg_ik_index = add_bone(pmx_model, leg_ik_bone, len(pmx_model.bones))

            toe_ik_bone = pmx.Bone(
                    name='左つま先ＩＫ' if LR == 'Left' else '右つま先ＩＫ',
                    english_name='{}LegIk'.format(LR),
                    position=common.Vector3(toe_vec.x, toe_vec.y, toe_vec.z),
                    parent_index=leg_ik_index,
                    layer=0,
                    flag=0
                )
            toe_ik_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
            toe_ik_bone.setFlag(pmx.BONEFLAG_CAN_TRANSLATE, True)
            toe_ik_bone.setFlag(pmx.BONEFLAG_IS_IK, True)
            toe_ik_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
            toe_ik_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)
            toe_ik_bone.ik = pmx.Ik(toe_index, 3, 4, [
                pmx.IkLink(ankle_index, 0)
            ])
            add_bone(pmx_model, toe_ik_bone, len(pmx_model.bones))

        '''
        # build local axis and get rotation
        left_arm_index = find_bone_index_by_name(pmx_model, 'LeftArm')
        left_elbow_index = find_bone_index_by_name(pmx_model, 'LeftElbow')
        left_wrist_index = find_bone_index_by_name(pmx_model, 'LeftWrist')
        larm_pos = np.array(list(pmx_model.bones[left_arm_index].position.to_tuple()))
        lelbow_pos = np.array(list(pmx_model.bones[left_elbow_index].position.to_tuple()))
        lwrist_pos = np.array(list(pmx_model.bones[left_wrist_index].position.to_tuple()))
        vec_ew = lwrist_pos - lelbow_pos
        vec_ea = larm_pos - lelbow_pos
        vec_ew = vec_ew / np.linalg.norm(vec_ew)
        vec_ea = vec_ea / np.linalg.norm(vec_ea)
        cos_ew_ea = np.dot(vec_ea, vec_ew)
        if -1 * math.cos(3/180 * 3.14) < cos_ew_ea and cos_ew_ea < 0:
            y_axis = np.cross(vec_ew, vec_ea)
            y_axis = y_axis / np.linalg.norm(y_axis)
            z_axis = np.cross(vec_ea, y_axis)
            z_axis = z_axis / np.linalg.norm(z_axis)
            x_axis = np.cross(z_axis, y_axis)
            x_axis = x_axis / np.linalg.norm(x_axis)
            # pmx_model.bones[left_elbow_index].setFlag(pmx.BONEFLAG_HAS_LOCAL_COORDINATE, True)
            pmx_model.bones[left_elbow_index].local_x_vector = common.Vector3(*x_axis.tolist())
            pmx_model.bones[left_elbow_index].local_z_vector = common.Vector3(*z_axis.tolist())
        '''
        head_index = find_bone_index_by_name(pmx_model, 'Head')
        eyes_bone = pmx.Bone(
                    name='両目',
                    english_name='Eyes',
                    position=common.Vector3(0, 25, 0),
                    parent_index=head_index,
                    layer=0,
                    flag=0
                )
        eyes_bone.setFlag(pmx.BONEFLAG_CAN_ROTATE, True)
        eyes_bone.setFlag(pmx.BONEFLAG_IS_VISIBLE, True)
        eyes_bone.setFlag(pmx.BONEFLAG_CAN_MANIPULATE, True)

        pmx_model.bones.append(eyes_bone)
        eyes_index = find_bone_index_by_name(pmx_model, 'Eyes')
        for LR in 'lr':
            eyeball_index = find_bone_index_by_name(pmx_model, 'bone_eyeball_{}'.format(LR))
            pmx_model.bones[eyeball_index].effect_index = eyes_index
            pmx_model.bones[eyeball_index].effect_factor = 2.2
            pmx_model.bones[eyeball_index].setFlag(pmx.BONEFLAG_IS_EXTERNAL_ROTATION, True)

        '''
        morph_ref_model = pymeshio.pmx.reader.read_from_file('morph_ref')
        pmx_model.morphs = morph_ref_model.morphs
        for morph in pmx_model.morphs:
            for offset in morph.offsets:
                bone_english_name = morph_ref_model.bones[offset.bone_index].english_name
                offset.bone_index = find_bone_index_by_name(pmx_model, bone_english_name)
        '''

        pymeshio.pmx.writer.write_to_file(pmx_model, filename + '_modified.pmx')
    except Exception:
        pass

def saveascii(model, filename, flip_uv=False):
    try:
        filename = filename.replace('.mesh', '.ascii')
        with open(filename, 'w') as file:
            # Write Bone Count
            if "bone_name" in model:
                file.write(f"{len(model['bone_name'])}\n")

            # Write Bone Information
            if "bone_name" in model and "bone_parent" in model:
                for name, parent in zip(model['bone_name'], model['bone_parent']):
                    file.write(f"{name}\n")
                    file.write(f"{parent}\n")
                    if "bone_original_matrix" in model:
                        matrix = model['bone_original_matrix'][model['bone_name'].index(name)]
                        position = " ".join(f"{val:.6f}" for val in matrix.flatten()[:3])
                        file.write(f"{position} 0 0 0 1\n")
                    else:
                        file.write("0.000000 0.000000 0.000000 0 0 0 1\n")

            # Write Vertex Positions
            if "position" in model:
                file.write(f"{len(model['position'])}\n")
                for x, y, z in model['position']:
                    file.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

            # Write Normals if they exist
            if "normal" in model:
                file.write(f"{len(model['normal'])}\n")
                for nx, ny, nz in model['normal']:
                    file.write(f"{nx:.6f} {ny:.6f} {nz:.6f}\n")

            # Write UVs, applying flip if needed
            if "uv" in model:
                file.write(f"{len(model['uv'])}\n")
                for u, v in model['uv']:
                    if flip_uv:
                        v = 1 - v
                    file.write(f"{u:.6f} {v:.6f}\n")

            # Write Face Indices
            if "face" in model:
                file.write(f"{len(model['face'])}\n")
                for v1, v2, v3 in model['face']:
                    file.write(f"{v1} {v2} {v3}\n")

    except Exception as e:
        print(f"Error writing ASCII file: {e}")

def saveiqe(model, filename):
    model['bone_translate'] = []
    model['bone_rotation'] = []
    bone_count = len(model['bone_parent'])
    for i in range(bone_count):
        matrix = tf.identity_matrix()
        parent_node = model['bone_parent'][i]
        if parent_node >= 0:
            matrix = model['bone_original_matrix'][parent_node]
        matrix = np.dot(model['bone_original_matrix'][i], np.linalg.inv(matrix))
        model['bone_translate'].append(tf.translation_from_matrix(matrix.T))
        model['bone_rotation'].append(tf.quaternion_from_matrix(matrix.T))
    filename = filename.replace('.mesh', '.iqe')
    with open(filename, 'w') as f:
        f.write('# Inter-Quake Export\n')
        f.write('\n')
        parent_child_dict = {}
        old2new = {}
        index_pool = [-1]
        for i in range(len(model['bone_parent'])):
            p = model['bone_parent'][i]
            if p not in parent_child_dict:
                parent_child_dict[p] = []
            parent_child_dict[p].append(i)

        def print_joint(index, parent_index):
            f.write('joint "{}" {}\n'.format(model['bone_name'][index], parent_index))
            x, y, z = model['bone_translate'][index]
            r, i, j, k = model['bone_rotation'][index]
            f.write('pq {} {} {} {} {} {} {}\n'.format(
                -x, y, z, i, -j, -k, r
            ))

        def deep_first_search(index, index_pool, parent_index):
            index_pool[0] += 1
            current_node_index = index_pool[0]
            old2new[index] = current_node_index
            print_joint(index, parent_index)
            if index in parent_child_dict:
                for child in parent_child_dict[index]:
                    deep_first_search(child, index_pool, current_node_index)

        deep_first_search(model['bone_parent'].index(-1), index_pool, -1)

        f.write('\n')

        mesh_vertex_counter = 0
        mesh_face_counter = 0

        for mesh_i in range(len(model['mesh'])):

            mesh_vertex_counter_end = mesh_vertex_counter + model['mesh'][mesh_i][0]
            mesh_face_counter_end = mesh_face_counter + model['mesh'][mesh_i][1]

            f.write('mesh mesh{}\n'.format(mesh_i))
            f.write('material "mesh{}Mat"\n'.format(mesh_i))
            f.write('\n')


            for i in range(mesh_vertex_counter, mesh_vertex_counter_end):
                x, y, z = model['position'][i]
                f.write('vp {} {} {}\n'.format(-x, y, z))
            f.write('\n')


            for i in range(mesh_vertex_counter, mesh_vertex_counter_end):
                x, y, z = model['normal'][i]
                f.write('vn {} {} {}\n'.format(-x, y, z))
            f.write('\n')

            for i in range(mesh_vertex_counter, mesh_vertex_counter_end):
                u, v = model['uv'][i]
                f.write('vt {} {}\n'.format(u, 1-v))
            f.write('\n')

            for i in range(mesh_vertex_counter, mesh_vertex_counter_end):
                f.write('vb')
                for j in range(4):
                    v = model['vertex_joint'][i][j]
                    if v == 255:
                        break
                    v = old2new[v]
                    w = model['vertex_joint_weight'][i][j]
                    f.write(' {} {}'.format(v, w))
                f.write('\n')
            f.write('\n')

            for i in range(mesh_face_counter, mesh_face_counter_end):
                v1, v2, v3 = model['face'][i]
                v1 -= mesh_vertex_counter
                v2 -= mesh_vertex_counter
                v3 -= mesh_vertex_counter
                f.write('fm {} {} {}\n'.format(v3, v1, v2))
            f.write('\n')

            mesh_vertex_counter = mesh_vertex_counter_end
            mesh_face_counter = mesh_face_counter_end

# Works for exporting just mesh
def save_to_json(model, filename):
    if not filename.endswith('.gltf'):
        filename = os.path.basename(filename).replace(".mesh", ".gltf")

    try:
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
            "scenes": [{"nodes": [0]}],
            "scene": 0
        }

        # Prepare binary buffers
        vertex_buffer = [coord for vertex in model['position'] for coord in vertex]
        normal_buffer = [coord for normal in model['normal'] for coord in normal]
        uv_buffer = [coord for uv in model['uv'] for coord in uv]
        index_buffer = [idx for face in model['face'] for idx in face]

        # Binary Buffer
        binary_buffer = (
            struct.pack(f"{len(vertex_buffer)}f", *vertex_buffer) +
            struct.pack(f"{len(normal_buffer)}f", *normal_buffer) +
            struct.pack(f"{len(uv_buffer)}f", *uv_buffer) +
            struct.pack(f"{len(index_buffer)}H", *index_buffer)
        )

        # Buffer and BufferView
        vertex_bytes = len(vertex_buffer) * 4
        normal_bytes = len(normal_buffer) * 4
        uv_bytes = len(uv_buffer) * 4
        index_bytes = len(index_buffer) * 2

        gltf_data["buffers"].append({
            "uri": os.path.basename(filename) + ".bin",
            "byteLength": len(binary_buffer)
        })

        gltf_data["bufferViews"].extend([
            {"buffer": 0, "byteOffset": 0, "byteLength": vertex_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes, "byteLength": normal_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes, "byteLength": uv_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes + uv_bytes, "byteLength": index_bytes, "target": 34963},
        ])

        # Calculate Bounds
        min_position = [min(coord) for coord in zip(*model['position'])]
        max_position = [max(coord) for coord in zip(*model['position'])]
        min_uv = [min(coord) for coord in zip(*model['uv'])]
        max_uv = [max(coord) for coord in zip(*model['uv'])]

        # Accessors
        gltf_data["accessors"].extend([
            {"bufferView": 0, "componentType": 5126, "count": len(model['position']), "type": "VEC3", "min": min_position, "max": max_position},
            {"bufferView": 1, "componentType": 5126, "count": len(model['normal']), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(model['uv']), "type": "VEC2", "min": min_uv, "max": max_uv},
            {"bufferView": 3, "componentType": 5123, "count": len(index_buffer), "type": "SCALAR"}
        ])

        # Meshes
        gltf_data["meshes"].append({
            "primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                "indices": 3
            }]
        })

        # Nodes
        gltf_data["nodes"].append({"mesh": 0})

        # Save Binary and JSON
        with open(filename + ".bin", "wb") as bin_file:
            bin_file.write(binary_buffer)
        with open(filename, "w") as json_file:
            json.dump(gltf_data, json_file, indent=4)

    except Exception as e:
        print(f"Failed to save GLTF2: {e}")

    print(f"GLTF JSON and binary saved as {filename} and {filename}.bin")

# Testing for getting skeleton
def save_to_gltf(model, filename):
    if not filename.endswith('.gltf'):
        filename = os.path.basename(filename).replace(".mesh", ".gltf")

    try:
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

        # Validate and extract mesh data
        positions = model.get('position', [])
        normals = model.get('normal', [])
        uvs = model.get('uv', [])
        indices = model.get('face', [])
        joint_indices = model.get('vertex_joint', [])
        weights = model.get('vertex_weight', [])
        bone_names = model.get('bone_name', [])
        bone_hierarchy = model.get('bone_parent', [])
        inverse_bind_matrices = model.get('bone_inverse_bind_matrices', [])

        if not positions or not indices or not bone_names or not inverse_bind_matrices:
            raise ValueError("Model must contain 'position', 'face', 'bone_name', and 'bone_inverse_bind_matrices'.")

        # Prepare binary buffers
        vertex_buffer = [coord for vertex in positions for coord in vertex]
        normal_buffer = [coord for normal in normals for coord in normal] if normals else []
        uv_buffer = [coord for uv in uvs for coord in uv] if uvs else []
        index_buffer = [idx for face in indices for idx in face]
        joint_buffer = [joint for joint_set in joint_indices for joint in joint_set]
        weight_buffer = [weight for weight_set in weights for weight in weight_set]
        flattened_ibms = [elem for matrix in inverse_bind_matrices for elem in matrix.flatten()]

        # Binary Buffer
        binary_buffer = (
            struct.pack(f"{len(vertex_buffer)}f", *vertex_buffer) +
            struct.pack(f"{len(normal_buffer)}f", *normal_buffer) +
            struct.pack(f"{len(uv_buffer)}f", *uv_buffer) +
            struct.pack(f"{len(index_buffer)}H", *index_buffer) +
            struct.pack(f"{len(joint_buffer)}B", *joint_buffer) +
            struct.pack(f"{len(weight_buffer)}f", *weight_buffer) +
            struct.pack(f"{len(flattened_ibms)}f", *flattened_ibms)
        )

        # Buffer and BufferView
        vertex_bytes = len(vertex_buffer) * 4
        normal_bytes = len(normal_buffer) * 4
        uv_bytes = len(uv_buffer) * 4
        index_bytes = len(index_buffer) * 2
        joint_bytes = len(joint_buffer)
        weight_bytes = len(weight_buffer) * 4
        ibm_bytes = len(flattened_ibms) * 4

        gltf_data["buffers"].append({
            "uri": filename.replace(".gltf", ".bin"),
            "byteLength": len(binary_buffer)
        })

        gltf_data["bufferViews"].extend([
            {"buffer": 0, "byteOffset": 0, "byteLength": vertex_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes, "byteLength": normal_bytes, "target": 34962} if normal_bytes else None,
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes, "byteLength": uv_bytes, "target": 34962} if uv_bytes else None,
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes + uv_bytes, "byteLength": index_bytes, "target": 34963},
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes + uv_bytes + index_bytes, "byteLength": joint_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes + uv_bytes + index_bytes + joint_bytes, "byteLength": weight_bytes, "target": 34962},
            {"buffer": 0, "byteOffset": vertex_bytes + normal_bytes + uv_bytes + index_bytes + joint_bytes + weight_bytes, "byteLength": ibm_bytes}
        ])

        # Calculate Bounds
        min_position = [min(coord) for coord in zip(*positions)]
        max_position = [max(coord) for coord in zip(*positions)]

        # Accessors
        gltf_data["accessors"].extend([
            {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3", "min": min_position, "max": max_position},
            {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"} if normals else None,
            {"bufferView": 2, "componentType": 5126, "count": len(uvs), "type": "VEC2"} if uvs else None,
            {"bufferView": 3, "componentType": 5123, "count": len(index_buffer), "type": "SCALAR"},
            {"bufferView": 4, "componentType": 5121, "count": len(joint_buffer) // 4, "type": "VEC4"},
            {"bufferView": 5, "componentType": 5126, "count": len(weight_buffer) // 4, "type": "VEC4"},
            {"bufferView": 6, "componentType": 5126, "count": len(inverse_bind_matrices), "type": "MAT4"}
        ])

        # Meshes
        gltf_data["meshes"].append({
            "primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2, "JOINTS_0": 4, "WEIGHTS_0": 5},
                "indices": 3
            }]
        })

        # Nodes
        for i, bone_name in enumerate(bone_names):
            gltf_data["nodes"].append({
                "name": bone_name,
                "translation": model['bone_translation'][i],
                "rotation": model['bone_rotation'][i],
                "scale": [1, 1, 1],
                "children": [j for j, parent in enumerate(bone_hierarchy) if parent == i] if bone_hierarchy else []
            })

        # Skin
        gltf_data["skins"].append({
            "joints": list(range(len(bone_names))),
            "inverseBindMatrices": 6
        })

        # Link skin to the mesh node
        gltf_data["nodes"][0]["skin"] = 0

        # Write binary and JSON files
        bin_file_name = filename.replace(".gltf", ".bin")
        with open(bin_file_name, "wb") as bin_file:
            bin_file.write(binary_buffer)

        with open(filename, "w") as json_file:
            json.dump(gltf_data, json_file, indent=4)

        print(f"GLTF with skeleton saved successfully as {filename} and {bin_file_name}")

    except Exception as e:
        print(f"Failed to save GLTF: {e}")

def parse_mesh_original(path):
    model = {}
    try:
        with io.BytesIO(path) as f:
            
            _magic_number = f.read(8)

            model['bone_exist'] = readuint32(f)
            model['mesh'] = []

            if model['bone_exist']:
                if model['bone_exist'] > 1:
                    count = readuint8(f)
                    f.read(2)
                    f.read(count * 4)
                bone_count = readuint16(f)
                parent_nodes = []
                for _ in range(bone_count):
                    parent_node = readuint16(f)
                    if parent_node == 65535:
                        parent_node = -1
                    parent_nodes.append(parent_node)
                model['bone_parent'] = parent_nodes

                bone_names = []
                for _ in range(bone_count):
                    bone_name = f.read(32)
                    bone_name = bone_name.decode().replace('\0', '').replace(' ', '_')
                    bone_names.append(bone_name)
                model['bone_name'] = bone_names

                bone_extra_info = readuint8(f)
                if bone_extra_info:
                    for _ in range(bone_count):
                        f.read(28)

                model['bone_original_matrix'] = []
                for i in range(bone_count):
                    matrix = [readfloat(f) for _ in range(16)]
                    matrix = np.array(matrix).reshape(4, 4)
                    model['bone_original_matrix'].append(matrix)

                if len(list(filter(lambda x: x == -1, parent_nodes))) > 1:
                    num = len(model['bone_parent'])
                    model['bone_parent'] = list(map(lambda x: num if x == -1 else x, model['bone_parent']))
                    model['bone_parent'].append(-1)
                    model['bone_name'].append('dummy_root')
                    model['bone_original_matrix'].append(np.identity(4))

                _flag = readuint8(f) # 00
                assert _flag == 0

            _offset = readuint32(f)
            while True:
                flag = readuint16(f)
                if flag == 1:
                    break
                f.seek(-2, 1)
                mesh_vertex_count = readuint32(f)
                mesh_face_count = readuint32(f)
                _flag = readuint8(f)
                color_len = readuint8(f)

                model['mesh'].append((mesh_vertex_count, mesh_face_count, _flag, color_len))

            vertex_count = readuint32(f)
            face_count = readuint32(f)

            model['position'] = []
            # vertex position
            for _ in range(vertex_count):
                x = readfloat(f)
                y = readfloat(f)
                z = readfloat(f)
                model['position'].append((x, y, z))

            model['normal'] = []
            # vertex normal
            for _ in range(vertex_count):
                x = readfloat(f)
                y = readfloat(f)
                z = readfloat(f)
                model['normal'].append((x, y, z))

            _flag = readuint16(f)
            if _flag:
                f.seek(vertex_count * 12, 1)

            model['face'] = []
            # face index table
            for _ in range(face_count):
                v1 = readuint16(f)
                v2 = readuint16(f)
                v3 = readuint16(f)
                model['face'].append((v1, v2, v3))

            model['uv'] = []
            # vertex uv
            for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
                if uv_layers > 0:
                    for _ in range(mesh_vertex_count):
                        u = readfloat(f)
                        v = readfloat(f)
                        model['uv'].append((u, v))
                    f.read(mesh_vertex_count * 8 * (uv_layers - 1))
                else:
                    for _ in range(mesh_vertex_count):
                        u = 0.0
                        v = 0.0
                        model['uv'].append((u, v))

            # vertex color
            for mesh_vertex_count, _, _, color_len in model['mesh']:
                f.read(mesh_vertex_count * 4 * color_len)

            if model['bone_exist']:
                model['vertex_joint'] = []
                for _ in range(vertex_count):
                    vertex_joints = [readuint16(f) for _ in range(4)]
                    model['vertex_joint'].append(vertex_joints)

                model['vertex_joint_weight'] = []
                for _ in range(vertex_count):
                    vertex_joint_weights = [readfloat(f) for _ in range(4)]
                    model['vertex_joint_weight'].append(vertex_joint_weights)

    except Exception as e:
        print(f"General parsing error: {e}")
        return None
    
    return model

def parse_mesh_helper(path):
    model = {}
    try:
        with io.BytesIO(path) as f:
            
            _magic_number = f.read(8)  # Read initial identifier
            
            model['bone_exist'] = readuint32(f)
            model['mesh'] = []

            # Bone Data Parsing
            if model['bone_exist']:
                try:
                    bone_count = readuint16(f)
                    parent_nodes = []
                    for _ in range(bone_count):
                        parent_node = readuint8(f)
                        parent_nodes.append(-1 if parent_node == 255 else parent_node)
                    model['bone_parent'] = parent_nodes

                    bone_names = []
                    for _ in range(bone_count):
                        bone_name = f.read(32).decode('latin-1', errors='replace').replace('\0', '').replace(' ', '_')
                        bone_names.append(bone_name)
                    model['bone_name'] = bone_names

                    model['bone_original_matrix'] = []
                    for _ in range(bone_count):
                        matrix = [readfloat(f) for _ in range(16)]
                        model['bone_original_matrix'].append(np.array(matrix).reshape(4, 4))

                    # Add dummy root if needed
                    if parent_nodes.count(-1) > 1:
                        num = len(model['bone_parent'])
                        model['bone_parent'] = [num if x == -1 else x for x in model['bone_parent']]
                        model['bone_parent'].append(-1)
                        model['bone_name'].append('dummy_root')
                        model['bone_original_matrix'].append(np.identity(4))

                    _flag = readuint8(f)  # Check flag
                    assert _flag == 0
                except Exception as e:
                    print(f"Bone parsing error: {e}")

            # Mesh Data Parsing
            _offset = readuint32(f)
            while True:
                try:
                    flag = readuint16(f)
                    if flag == 1:
                        break
                    f.seek(-2, 1)
                    mesh_vertex_count = readuint32(f)
                    mesh_face_count = readuint32(f)
                    uv_layers = readuint8(f)
                    color_len = readuint8(f)

                    model['mesh'].append((mesh_vertex_count, mesh_face_count, uv_layers, color_len))
                except Exception as e:
                    print(f"Mesh section parsing error: {e}")
                    break

            # Vertex Data
            vertex_count = readuint32(f)
            face_count = readuint32(f)

            try:
                model['position'] = [(readfloat(f), readfloat(f), readfloat(f)) for _ in range(vertex_count)]
                model['normal'] = [(readfloat(f), readfloat(f), readfloat(f)) for _ in range(vertex_count)]
            except Exception as e:
                print(f"Error parsing vertex positions or normals: {e}")

            # Faces Data
            try:
                model['face'] = [(readuint16(f), readuint16(f), readuint16(f)) for _ in range(face_count)]
            except Exception as e:
                print(f"Error parsing face data: {e}")

            # UV Data
            model['uv'] = []
            for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
                if uv_layers > 0:
                    for _ in range(mesh_vertex_count):
                        u, v = readfloat(f), readfloat(f)
                        model['uv'].append((u, v))
                    f.seek(mesh_vertex_count * 8 * (uv_layers - 1), 1)  # Skip remaining UV layers if any
                else:
                    model['uv'].extend([(0.0, 0.0)] * mesh_vertex_count)

            # Vertex Color Data (optional)
            for mesh_vertex_count, _, _, color_len in model['mesh']:
                f.seek(mesh_vertex_count * 4 * color_len, 1)

            # Bone Weights if Bones Exist
            if model['bone_exist']:
                try:
                    model['vertex_joint'] = [[readuint8(f) for _ in range(4)] for _ in range(vertex_count)]
                    model['vertex_joint_weight'] = [[readfloat(f) for _ in range(4)] for _ in range(vertex_count)]
                except Exception as e:
                    print(f"Error parsing bone weights: {e}")

    except Exception as e:
        print(f"General parsing error: {e}")
        return None

    # Final validation check
    if 'normal' not in model:
        print("Warning: 'normal' data missing.")
    if 'position' not in model or 'face' not in model:
        print("Error: Incomplete mesh data.")
        return None

    return model

def parse_mesh_adaptive(path):
    model = {}
    with io.BytesIO(path) as f:
        try:
            _magic_number = f.read(8)  # Read initial identifier
            
            model['mesh'] = []
            model['bone_exist'] = readuint32(f)

            # Bone Parsing based on identified patterns
            if model['bone_exist']:
                bone_count = readuint16(f)
                model['bone_parent'] = [readuint16(f) if f.readable() else -1 for _ in range(bone_count)]

                # Reading bone names in 32-byte sections
                model['bone_name'] = []
                for _ in range(bone_count):
                    bone_name = f.read(32).decode('utf-8', errors='replace').replace('\0', '').replace(' ', '_')
                    model['bone_name'].append(bone_name)

                # Bone matrices if present
                model['bone_original_matrix'] = [np.array([readfloat(f) for _ in range(16)]).reshape(4, 4) for _ in range(bone_count)]

            # Vertex Data Detection: Searching for clusters of floats
            model['position'] = []
            while True:
                # Read a small block of data to analyze
                pos = f.tell()
                data_block = f.read(4 * 3)  # Attempt to read a potential vertex (3 floats)
                if len(data_block) < 4 * 3:
                    break  # End of file

                # Check if this block resembles 3 valid floats (a vertex)
                try:
                    f.seek(pos)
                    vertex = (readfloat(f), readfloat(f), readfloat(f))
                    model['position'].append(vertex)
                except struct.error:
                    f.seek(pos + 4)  # Adjust by one byte if not valid floats

                # Terminate parsing if the vertex section ends or data no longer matches pattern
                end_pos = f.tell()
                if end_pos >= 0xb187:  # Replace with detected pattern in actual file
                    break

        except Exception as e:
            print(f"Error occurred during pattern-based parsing: {e}")
            model['error'] = str(e)

    return model