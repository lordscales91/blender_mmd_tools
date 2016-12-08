# -*- coding: utf-8 -*-
import logging
import re
import os

import bpy

from mmd_tools.core.model import Model
from mmd_tools.core.pmx import Material
from mmd_tools.core.material import FnMaterial
from mmd_tools.utils import normalize_path

class InvalidFormatException(Exception):
    pass

class CSVImporter:
    def __init__(self, filepath, context=bpy.context, encoding='sjis'):
        self.filepath = filepath
        self.context = context
        self.__directory = os.path.dirname(filepath) 
        self.__file_obj = open(filepath, 'r', encoding=encoding)
        self.materials_map = {}

    def load(self, is_import=False):
        header = None
        for line in self.__file_obj:
            if line.startswith(';'):
                header = line[1:].strip().split(',')
            else:
                data = line.strip().split(',')
                if header is None or len(header) != len(data):
                    raise InvalidFormatException()
                if(is_import):
                    self._import_data(header, self.parse_values(data[1:]))
                else:
                    if(header[0] == 'Material'):
                        self.load_material(self.parse_values(data[1:]))
                    elif header[0] == 'Body':
                        pass # TODO: Implement loading of Rigid Bodies

        if not is_import:
            self.update_data()

    def _import_data(self, header, values):
        """
        Instead of loading the settings into an existing model,
        appends new data to the model(Materials, Physics ...)
        """
                    
    def load_material(self, values):
        """
        Loads new material settings to an existing model
        """
        # First let's store the values into meaningful variables
        name = values[0]
        name_e = values[1]
        diffuse = [values[2], values[3], values[4], values[5]]
        specular = [values[6], values[7], values[8]]
        shininess = values[9]
        ambient = [values[10], values[11], values[12]]
        is_double_sided = bool(values[13])
        enabled_drop_shadow = bool(values[14])
        enabled_self_shadow_map = bool(values[15])
        enabled_self_shadow = bool(values[16])
        values[17] # Unknown value. 頂点色(0/1)
        values[18] # Unknown value. 描画(0:Tri/1:Point/2:Line)
        enabled_toon_edge = values [19]
        edge_size = values[20]
        edge_color = [values[21], values[22], values[23], values[24]]
        texture_path = values[25]
        sphere_texture_path = values[26]
        sphere_texture_mode = values[27]
        toon_texture_path = values[28]
        comment = values[29]
        mat = Material()
        # Let's start to assign the easy ones
        mat.name = name
        mat.name_e = name_e
        mat.diffuse = diffuse
        mat.specular = specular
        mat.shininess = shininess
        mat.ambient = ambient
        mat.is_double_sided = is_double_sided
        mat.enabled_drop_shadow = enabled_drop_shadow
        mat.enabled_self_shadow_map = enabled_self_shadow_map
        mat.enabled_self_shadow = enabled_self_shadow
        mat.enabled_toon_edge = enabled_toon_edge
        mat.edge_size = edge_size
        mat.edge_color = edge_color
        mat.comment = comment
        # Resolve the textures
        toon_patt = r'toon(?P<index>[01][0-9])\.bmp'
        m = re.match(toon_patt, toon_texture_path)
        if m:
            mat.is_shared_toon_texture = True
            mat.toon_texture = int(m.group('index')) - 1
        elif  toon_texture_path is not None and toon_texture_path != '':
            # Use extra attributes to store the paths
            mat.is_shared_toon_texture = False
            mat.toon_texture_path = toon_texture_path
        else:
            mat.is_shared_toon_texture = False
            mat.toon_texture = -1

        if texture_path is not None and texture_path != '':
            mat.texture_path = texture_path
        mat.sphere_texture_mode = sphere_texture_mode
        if sphere_texture_path is not None and sphere_texture_path != '':
            mat.sphere_texture_path = sphere_texture_path
        
        
        if name in self.materials_map:
            logging.warn("Duplicate material: %s" % (name,))
        else:
            self.materials_map[name] = mat

    def parse_values(self, data):
        """
        Converts the data strings into the proper types
        """
        string_patt = r'^\"(?P<value>.*)\"$'
        decimal_patt = r'^[0-9]+\.[0-9]+$'
        integer_patt = r'^[0-9]+$'
        values = []
        for val in data:
            if re.match(string_patt, val):
                raw = re.match(string_patt, val).group('value')
                values.append(raw.replace('\\r', '').replace('\\n', '\n'))
            elif re.match(decimal_patt, val):
                values.append(float(val))
            elif re.match(integer_patt, val):
                values.append(int(val))
            else:
                logging.warn("Unrecognized value: %s" % (val,))

        return values

    def update_data(self):
        """
        Updates the active model with the new data
        """
        root = Model.findRoot(self.context.active_object)
        rig = Model(root)
        basedir = root.get('import_folder', self.__directory)
        for mesh in rig.meshes():
            for mat in mesh.data.materials:
                mmd_mat = mat.mmd_material
                # Process each material only once
                pmx_mat = self.materials_map.pop(mmd_mat.name_j, None)
                if pmx_mat:
                    mat.diffuse_color = pmx_mat.diffuse[0:3]
                    mat.alpha = pmx_mat.diffuse[3]
                    mat.specular_color = pmx_mat.specular
                    if mat.alpha < 1.0 or mat.specular_alpha < 1.0 or hasattr(pmx_mat, 'texture_path'):
                        mat.use_transparency = True
                        mat.transparency_method = 'Z_TRANSPARENCY'
        
                    mmd_mat.name_j = pmx_mat.name
                    mmd_mat.name_e = pmx_mat.name_e
                    mmd_mat.ambient_color = pmx_mat.ambient
                    mmd_mat.diffuse_color = pmx_mat.diffuse[0:3]
                    mmd_mat.alpha = pmx_mat.diffuse[3]
                    mmd_mat.specular_color = pmx_mat.specular
                    mmd_mat.shininess = pmx_mat.shininess
                    mmd_mat.is_double_sided = pmx_mat.is_double_sided
                    mmd_mat.enabled_drop_shadow = pmx_mat.enabled_drop_shadow
                    mmd_mat.enabled_self_shadow_map = pmx_mat.enabled_self_shadow_map
                    mmd_mat.enabled_self_shadow = pmx_mat.enabled_self_shadow
                    mmd_mat.enabled_toon_edge = pmx_mat.enabled_toon_edge
                    mmd_mat.edge_color = pmx_mat.edge_color
                    mmd_mat.edge_weight = pmx_mat.edge_size                    
                    if pmx_mat.is_shared_toon_texture:
                        mmd_mat.is_shared_toon_texture = True
                        mmd_mat.shared_toon_texture = pmx_mat.toon_texture
                    else:
                        mmd_mat.is_shared_toon_texture = False
                        if hasattr(pmx_mat, 'toon_texture_path'):
                            normalized = normalize_path(pmx_mat.toon_texture_path, basedir)
                            mmd_mat.toon_texture = bpy.path.resolve_ncase(normalized)
                        else:
                            mmd_mat.toon_texture = ''
                    mmd_mat.comment = pmx_mat.comment
                    fnMat = FnMaterial(mat)
                    if hasattr(pmx_mat, 'texture_path'):
                        normalized = normalize_path(pmx_mat.texture_path, basedir)
                        img_path = bpy.path.resolve_ncase(normalized)
                        fnMat.create_texture(img_path)
                    else:
                        # Remove if not used
                        fnMat.remove_texture()
                    if hasattr(pmx_mat, 'sphere_texture_path'):
                        normalized = normalize_path(pmx_mat.sphere_texture_path, basedir)
                        img_path = bpy.path.resolve_ncase(normalized)
                        fnMat.create_sphere_texture(img_path)
                    else:
                        fnMat.remove_sphere_texture()
                    mmd_mat.sphere_texture_type = str(pmx_mat.sphere_texture_mode)
        

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self.__file_obj is not None:
            logging.debug('close the file("%s")', self.filepath)
            self.__file_obj.close()
            self.__file_obj = None