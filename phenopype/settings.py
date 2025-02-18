#%% load modules

import cv2
import numpy as np

from pprint import PrettyPrinter


#%% helper-class

# from importlib.resources import path
# from pathlib import Path, PurePath

# ## create template browser
# class TemplateList:
#     def __init__(self, root_path):
#         for folder_path in list(Path(root_path).glob('[!__]*')):
#             setattr(self, PurePath(folder_path).name, TemplateFolder(folder_path))
#     def __repr__(self):
#         no_repr_items = []
#         dict_cleaned = {x: self.__dict__[x] for x in self.__dict__ if x not in no_repr_items}
#         attrs = "\n".join("pype_templates.{} ({} files)".format(k, v.n_templates) for k, v in dict_cleaned.items())
#         return "Default Pype-templates:\n\n{}".format(attrs)

# class TemplateFolder:
#     def __init__(self, folder_path):
#         self.name = PurePath(folder_path).name
#         self.n_templates = len(list(Path(folder_path).glob('[!__]*')))
#         for file_path in list(Path(folder_path).glob('[!__]*')):
#             setattr(self, PurePath(file_path).stem, Template(file_path))
#     def __repr__(self):
#         no_repr_items = ["name","n_templates"]
#         dict_cleaned = {x: self.__dict__[x] for x in self.__dict__ if x not in no_repr_items}
#         attrs = "\n".join("pype_templates.{}.{}".format(self.name, k) for k, v in dict_cleaned.items())
#         return "Pype-templates in folder {}:\n\n{}".format(self.name, attrs)

# class Template:
#     def __init__(self, file_path):
#         self.name = PurePath(file_path).stem
#         self.path = str(PurePath(file_path))
#         self.processing_steps = utils_lowlevel._load_yaml(file_path)
#     def __repr__(self):
#         return "Pype-template \"{}\":\n\n{}".format(self.name,
#                                                     utils_lowlevel._show_yaml(
#                                                         self.processing_steps, ret=True))

# ## import
# with path(__package__, 'templates') as template_dir:
#     pype_templates = TemplateList(template_dir)

#%% defaults

auto_line_width_factor = 0.0025
auto_point_size_factor = 0.0025
auto_text_width_factor = 0.0005
auto_text_size_factor = 0.00025

confirm_options = ["True", "true", "y", "yes", True]

_default_label_colour = "lime"
_default_line_colour = "lime"
_default_point_colour = "red"
_default_overlay_left = "green"
_default_overlay_right = "red"


default_filetypes = ["jpg", "JPG", "jpeg", "JPEG", "tif", "png", "bmp"]
default_meta_data_fields = [
    "DateTimeOriginal",
    "Model",
    "LensModel",
    "ExposureTime",
    "ISOSpeedRatings",
    "FNumber",
]

default_save_suffix = "v1"
default_window_size = 1000

pandas_max_rows = 10
pretty = PrettyPrinter(width=30)

strftime_format = "%Y-%m-%d %H:%M:%S"


#%% flags

flag_verbose = True

#%% flags opencv

opencv_contour_flags = {
    "retrieval": {
        "ext": cv2.RETR_EXTERNAL,  ## only external
        "list": cv2.RETR_LIST,  ## all contours
        "tree": cv2.RETR_TREE,  ## fully hierarchy
        "ccomp": cv2.RETR_CCOMP,  ## outer perimeter and holes
        "flood": cv2.RETR_FLOODFILL,  ## not sure what this does
    },
    "approximation": {
        "none": cv2.CHAIN_APPROX_NONE,  ## all points (no approx)
        "simple": cv2.CHAIN_APPROX_SIMPLE,  ## minimal corners
        "L1": cv2.CHAIN_APPROX_TC89_L1,
        "KCOS": cv2.CHAIN_APPROX_TC89_KCOS,
    },
}

opencv_distance_flags = {
    "user": cv2.DIST_USER,
    "l1": cv2.DIST_L1,
    "l2": cv2.DIST_L2,
    "C": cv2.DIST_C,
    "l12": cv2.DIST_L12,
    "fair": cv2.DIST_FAIR,
    "welsch": cv2.DIST_WELSCH,
    "huber": cv2.DIST_HUBER,
}

opencv_interpolation_flags = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "area": cv2.INTER_AREA,
    "lanczos": cv2.INTER_LANCZOS4,
    "lin_exact": cv2.INTER_LINEAR_EXACT,
    "inter": cv2.INTER_MAX,
    "warp_fill": cv2.WARP_FILL_OUTLIERS,
    "warp_inverse": cv2.WARP_INVERSE_MAP,
}

opencv_morphology_flags = {
    "shape_list": {
        "cross": cv2.MORPH_CROSS,
        "rect": cv2.MORPH_RECT,
        "ellipse": cv2.MORPH_ELLIPSE,
    },
    "operation_list": {
        "erode": cv2.MORPH_ERODE,
        "dilate": cv2.MORPH_DILATE,
        "open": cv2.MORPH_OPEN,
        "close": cv2.MORPH_CLOSE,
        "gradient": cv2.MORPH_GRADIENT,
        "tophat": cv2.MORPH_TOPHAT,
        "blackhat": cv2.MORPH_BLACKHAT,
        "hitmiss": cv2.MORPH_HITMISS,
    },
}

opencv_skeletonize_flags = {
    "zhangsuen": cv2.ximgproc.THINNING_ZHANGSUEN,
    "guohall": cv2.ximgproc.THINNING_GUOHALL,
}

opencv_window_flags = {
    "normal": cv2.WINDOW_NORMAL,
    "auto": cv2.WINDOW_AUTOSIZE,
    "openGL": cv2.WINDOW_OPENGL,
    "full": cv2.WINDOW_FULLSCREEN,
    "free": cv2.WINDOW_FREERATIO,
    "keep": cv2.WINDOW_KEEPRATIO,
    "GUIexp": cv2.WINDOW_GUI_EXPANDED,
    "GUInorm": cv2.WINDOW_GUI_NORMAL,
}

#%% annotation definitions

## gui data
_coord_type = "points"
_coord_list_type = "polygons"
_sequence_type = "drawings"

## annotation data
_comment_type = "comment"
_contour_type = "contour"
_drawing_type = "drawing"
_landmark_type = "landmark"
_line_type = "line"
_mask_type = "mask"
_reference_type = "reference"
_shape_feature_type = "shape_features"
_texture_feature_type = "texture_features"

_annotation_functions = {
    ## comments
    "write_comment": _comment_type,
    "detect_QRcode": _comment_type,
    
    ## contours
    "detect_contour": _contour_type,
    
    ## drawings
    "edit_contour": _drawing_type,
    
    ## landmarks
    "set_landmark": _landmark_type,
    "detect_landmark": _landmark_type,

    ## lines
    "set_polyline": _line_type,
    "detect_skeleton": _line_type,
    
    ## masks
    "contour_to_mask": _mask_type,
    "create_mask": _mask_type,
    "detect_mask": _mask_type,
    
    ## reference
    "create_reference": _reference_type,
    "detect_reference": _reference_type,
    
    ## shape_features
    "compute_shape_features": _shape_feature_type,
    
    ## texture_features
    "compute_texture_features": _texture_feature_type,
}

_annotation_types = list(set(_annotation_functions.values()))

#%% GUI definitions

## find better solution
# from phenopype import utils_lowlevel
# g = utils_lowlevel._GUI(np.zeros((1, 1, 1), dtype="uint8"), window_control="external")
# cv2.waitKey(1)
# cv2.destroyAllWindows()
# _GUI_settings_args = list(g.settings.__dict__)
# _GUI_data_args = list(g.data.keys())

_GUI_settings_args = [
    'feedback',
    'show_label',
    'label_colour',
    'label_size',
    'label_width',
    'show_nodes',
    'node_colour',
    'node_size',
    'line_colour',
    'line_width',
    'point_colour',
    'point_size',
    'overlay_blend',
    'overlay_line_width',
    'overlay_colour_left',
    'overlay_colour_right',
    'pype_mode',
    'zoom_memory',
    'zoom_mode',
    'zoom_magnification',
    'zoom_n_steps',
    'wait_time',
    'window_aspect',
    'window_control',
    'window_max_dim',
    'window_name',
 ]

_GUI_data_args = [
    'comment', 
    'contour', 
    'points', 
    'polygons', 
    'drawings'
    ]


#%% legacy fun-names

_legacy_names = {
    "preprocessing": {
        "enter_data": "write_comment",
        "comment": "write_comment",
        "detect_shape": "detect_mask",
        },
    "segmentation": {
        "detect_contours": "detect_contour",
        "edit_contours": "edit_contour",
    },
    "measurement": {
        "set_landmark": "set_landmark",
        "set_landmarks": "set_landmark",
        "landmark": "set_landmark",
        "landmarks": "set_landmark",
        "shape_features": "compute_shape_features",
        "texture_features": "compute_texture_features"
    },
    "visualization": {
        "draw_landmarks": "draw_landmark",
        "draw_contours": "draw_contour",
    },
    "export": {},
}
