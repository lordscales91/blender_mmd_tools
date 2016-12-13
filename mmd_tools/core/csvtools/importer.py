# -*- coding: utf-8 -*-
import logging
import re
import os
import csv

import bpy

from mmd_tools.core.model import Model
from mmd_tools.core.pmx import Material
from mmd_tools.core.material import FnMaterial
from mmd_tools.utils import normalize_path

class InvalidFormatException(Exception):
    pass

class CSVImporter:
    
    MATERIAL_DATA_SIZE = 31
    
    def __init__(self, filepath, context=bpy.context, encoding='sjis'):
        self.filepath = filepath
        self.context = context
        self.__directory = os.path.dirname(filepath) 
        self.__file_obj = open(filepath, 'r', encoding=encoding)
        self.materials_map = {}

    def load(self, is_import=False):
        reader = csv.reader(self.__file_obj)
        for data in reader:
            if data[0].startswith(';'):
                continue
            if(is_import):
                self._import_data(data[0], self.parse_values(data[1:]))
            else:
                if(data[0] == 'Material'):
                    if len(data) != self.MATERIAL_DATA_SIZE:
                        raise InvalidFormatException()
                    self.load_material(data[1:])
                elif data[0] == 'Body':
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
        diffuse = [float(v) for v in values[2:6]]
        specular = [float(v) for v in values[6:9]]
        shininess = float(values[9])
        ambient = [float(v) for v in values[10:13]]
        is_double_sided = bool(int(values[13]))
        enabled_drop_shadow = bool(int(values[14]))
        enabled_self_shadow_map = bool(int(values[15]))
        enabled_self_shadow = bool(int(values[16]))
        values[17] # Unknown value. 頂点色(0/1)
        values[18] # Unknown value. 描画(0:Tri/1:Point/2:Line)
        enabled_toon_edge = bool(int(values[19]))
        edge_size = float(values[20])
        edge_color = [float(v) for v in values[21:25]]
        texture_path = values[25]
        sphere_texture_path = values[26]
        sphere_texture_mode = int(values[27])
        toon_texture_path = values[28]
        # Replace linebreaks with spaces for material comments
        comment = values[29].replace('\\r', '').replace('\\n', ' ')
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
        toon_patt = r'^toon(?P<index>(0[1-9]|10))\.bmp$'
        m = re.match(toon_patt, toon_texture_path)
        if m:
            mat.is_shared_toon_texture = True
            mat.toon_texture = int(m.group('index')) - 1
        elif toon_texture_path is not None and toon_texture_path != '':
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

    def update_data(self):
        """
        Updates the active model with the new data
        """
        root = Model.findRoot(self.context.active_object)
        rig = Model(root)
        basedir = root.get('import_folder', self.__directory)
        for mesh in rig.meshes():
            for mat in mesh.data.materials:
                # Process each material only once
                mmd_mat = mat.mmd_material
                pmx_mat = self.materials_map.pop(mat.mmd_material.name_j, None)
                if pmx_mat:
                    fnMat = FnMaterial(mat)
                    fnMat.update_values(from_pmx=pmx_mat)
                    mmd_mat.sphere_texture_type = str(pmx_mat.sphere_texture_mode)
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

        if len(self.materials_map) > 0:
            logging.warn("some materials were not found")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self.__file_obj is not None:
            logging.debug('close the file("%s")', self.filepath)
            self.__file_obj.close()
            self.__file_obj = None