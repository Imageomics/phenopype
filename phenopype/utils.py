#%% modules
import ast, cv2, copy, os, sys, warnings
import numpy as np
import glob
import pandas as pd
import pkgutil

from pathlib import Path

import phenopype.core.preprocessing as preprocessing
import phenopype.core.segmentation as segmentation
import phenopype.core.measurement as measurement
import phenopype.core.visualization as visualization
import phenopype.core.export as export

from phenopype.settings import AttrDict, default_filetypes, flag_verbose, \
    pype_config_template_list, confirm_options, _annotation_function_dicts
from phenopype.utils_lowlevel import _ImageViewer, _convert_tup_list_arr, \
    _load_image_data, _load_yaml, _show_yaml
    
from collections import defaultdict


#%% classes




class Container(object):
    """
    A phenopype container is a Python class where loaded images, dataframes, 
    detected contours, intermediate output, etc. are stored so that they are 
    available for inspection or storage at the end of the analysis. The 
    advantage of using containers is that they don’t litter the global environment 
    and namespace, while still containing all intermediate steps (e.g. binary 
    masks or contour DataFrames). Containers can be used manually to analyse images, 
    but typically they are created dynamically within the pype-routine. 
    
    Parameters
    ----------
    image : ndarray
        single or multi-channel iamge as an array (can be created using load_image 
        or load_pp_directory).
    df_image_data: DataFrame
        a dataframe that contains meta-data of the provided image to be passed on
        to all results-DataFrames
    save_suffix : str, optional
        suffix to append to filename of results files

    """

    def __init__(self, image, dirpath=None, save_suffix=None):

        ## images
        self.image = image
        self.image_copy = copy.deepcopy(self.image)
        self.image_bin = None
        self.image_gray = None
        self.canvas = None

        ## attributes
        self.dirpath = dirpath
        self.save_suffix = save_suffix
        
        ## annotations
        self.annotations = _annotation_function_dicts
                
    def select_canvas(self, canvas="mod", multi=True):
        """
        Isolate a colour channel from an image or select canvas for the pype method.
    
        Parameters
        ----------
    
        canvas : {"mod", "bin", "gray", "raw", "red", "green", "blue"} str, optional
            the type of canvas to be used for visual feedback. some types require a
            function to be run first, e.g. "bin" needs a segmentation algorithm to be
            run first. black/white images don't have colour channels. coerced to 3D
            array by default
        multi: bool, optional
            coerce returned array to multichannel (3-channel)
    
        Returns
        -------
        obj_input : container
            canvas can be called with "obj_input.canvas".
    
        """
        ## kwargs
        flag_multi = multi
    
        ## method
        if canvas == "mod":
            self.canvas = copy.deepcopy(self.image)
            print("- modifed image")
        elif canvas == "raw":
            self.canvas = copy.deepcopy(self.image_copy)
            print("- raw image")
        elif canvas == "bin":
            self.canvas = copy.deepcopy(self.image_bin)
            print("- binary image")
        elif canvas == "gray":
            self.canvas = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            print("- grayscale image")
        elif canvas == "green":
            self.canvas = self.image[:, :, 0]
            print("- green channel")
        elif canvas == "red":
            self.canvas = self.image[:, :, 1]
            print("- red channel")
        elif canvas == "blue":
            self.canvas = self.image[:, :, 2]
            print("- blue channel")
        else:
            print("- invalid selection - defaulting to raw image")
            self.canvas = copy.deepcopy(self.image_copy)
    
        ## check if colour
        if flag_multi:
            if len(self.canvas.shape) < 3:
                self.canvas = cv2.cvtColor(self.canvas, cv2.COLOR_GRAY2BGR)
            
    def run(self, fun, annotation_id=None, kwargs={}):
        
        if annotation_id in self.annotations["masks"]:
            kwargs.update({"previous_annotation":self.annotations["masks"][annotation_id]})

        ## preprocessing
        if fun == "blur":
            self.image = preprocessing.blur(self.image, **kwargs)

        if fun == "create_mask":
            annotation = preprocessing.create_mask(self.image, **kwargs)
            self.annotations["masks"][annotation_id] = annotation

        if fun == "detect_mask":
            annotation = preprocessing.detect_mask(self.image, **kwargs)
            self.annotations["masks"][annotation_id] = annotation
            
        if fun == "enter_data":
            annotation = preprocessing.enter_data(self.image, **kwargs)
            self.annotations["comments"][annotation_id] = annotation
            
            
        if fun == "detect_reference":
            if all(hasattr(self, attr) for attr in [
                    "reference_template_px_mm_ratio", 
                    "reference_template_image"
                    ]):
                annotation = preprocessing.detect_reference(
                    self.image, 
                    self.reference_template_image,
                    self.reference_template_px_mm_ratio,
                    **kwargs)
                self.annotations["masks"][annotation_id] = annotation
                if annotation.__class__.__name__ == "tuple":
                    self.annotations["masks"][annotation_id] = annotation[1]
                    self.annotations["references"][annotation_id] = annotation[0]
                else:
                    self.annotations["references"][annotation_id] = annotation
            else:
                print("- missing project level reference information, cannot detect")
            
        if fun == "select_channel":
            self.image = preprocessing.select_channel(self.image, **kwargs)
            
            
        ## segmentation
        if fun == "threshold":
            if len(self.annotations["masks"]) > 0:
                kwargs.update({"masks":self.annotations["masks"]})
            self.image = segmentation.threshold(self.image, **kwargs)
            self.image_bin = copy.deepcopy(self.image)
        if fun == "watershed":
            self.image = segmentation.watershed(self.image_copy, self.image_bin, **kwargs)
        if fun == "morphology":
            self.image = segmentation.morphology(self.image, **kwargs)
            
        if fun == "detect_contours":
            self.annotations["contours"][annotation_id] = segmentation.detect_contours(self.image, **kwargs)
            

                    
    def load(self, dirpath=None, save_suffix=None, contours=False, canvas=False, **kwargs):
        """
        Autoload function for container: loads results files with given save_suffix
        into the container. Can be used manually, but is typically used within the
        pype routine.
        
        Parameters
        ----------
        save_suffix : str, optional
            suffix to include when looking for files to load

        """
        files, loaded = [], []

        ## data flags
        flag_contours = contours

        ## check dirpath
        if (
            dirpath.__class__.__name__ == "NoneType"
            and not self.dirpath.__class__.__name__ == "NoneType"
        ):
            dirpath = self.dirpath
        if dirpath.__class__.__name__ == "NoneType":
            print('No save directory ("dirpath") specified - cannot load files.')
            return
        if not os.path.isdir(dirpath):
            print("Directory does not exist - cannot load files.")
            return

        ## check save_suffix
        if (
            save_suffix.__class__.__name__ == "NoneType"
            and not self.save_suffix.__class__.__name__ == "NoneType"
        ):
            save_suffix = "_" + self.save_suffix
        elif not save_suffix.__class__.__name__ == "NoneType":
            save_suffix = "_" + save_suffix
        else:
            save_suffix = ""

        # collect
        if len(os.listdir(dirpath)) > 0:
            for file in os.listdir(dirpath):
                if os.path.isfile(os.path.join(dirpath, file)):
                    if (
                        len(save_suffix) > 0
                        and save_suffix in file
                        and not "pype_config" in file
                    ):
                        files.append(file[0 : file.rindex("_")])
                    elif len(save_suffix) == 0:
                        files.append(file[0 : file.rindex(".")])

        else:
            print("No files found in given directory")
            return

        ## load attributes
        attr_local_path = os.path.join(dirpath, "attributes.yaml")
        if os.path.isfile(attr_local_path):

            attr_local = _load_yaml(attr_local_path)
                
            
            if "reference" in attr_local:
                
                ## manually measured px-mm-ratio
                if "manually_measured_px_mm_ratio" in attr_local["reference"]:
                    self.reference_manually_measured_px_mm_ratio = attr_local["reference"]["manually_measured_px_mm_ratio"]
                    loaded.append("manually measured local reference information loaded")
                    
                ## project level template px-mm-ratio
                if "project_level" in attr_local["reference"]:
                    
                    ## load local (image specific) and global (project level) attributes 
                    attr_proj_path =  os.path.abspath(os.path.join(attr_local_path ,r"../../../","attributes.yaml"))
                    attr_proj = _load_yaml(attr_proj_path)
                                        
                    ## find active project level references
                    n_active = 0
                    for key, value in attr_local["reference"]["project_level"].items():
                        if attr_local["reference"]["project_level"][key]["active"] == True:
                            active_ref = key
                            n_active += 1
                    if n_active > 1:
                        print("WARNING: multiple active reference detected - fix with running add_reference again.")                            
                    self.reference_active = active_ref
                    self.reference_template_px_mm_ratio = attr_proj["reference"][active_ref]["template_px_mm_ratio"]
                    loaded.append("project level reference information loaded for " + active_ref)
                
                    ## load previously detect px-mm-ratio
                    if "detected_px_mm_ratio" in attr_local["reference"]["project_level"]:
                        self.reference_detected_px_mm_ratio = attr_local["reference"]["project_level"]["detected_px_mm_ratio"]
                        loaded.append("detected local reference information loaded for " + active_ref)
                        
                    ## load tempate image from project level attributes
                    if "template_image" in attr_proj["reference"][active_ref]:
                        self.reference_template_image = cv2.imread(str(Path(attr_local_path).parents[2] / attr_proj["reference"][active_ref]["template_image"]))
                        loaded.append("reference template image loaded from root directory")

        ## contours
        if flag_contours:
            if not hasattr(self, "df_contours") and "contours" in files:
                path = os.path.join(dirpath, "contours" + save_suffix + ".csv")
                if os.path.isfile(path):
                    df = pd.read_csv(path, converters={"center": ast.literal_eval})
                    if "x" in df:
                        df["coords"] = list(zip(df.x, df.y))
                        coords = df.groupby("contour")["coords"].apply(list)
                        coords_arr = _convert_tup_list_arr(coords)
                        df.drop(columns=["coords", "x", "y"], inplace=True)
                        df = df.drop_duplicates().reset_index()
                        df["coords"] = pd.Series(coords_arr, index=df.index)
                        self.df_contours = df
                        loaded.append("contours" + save_suffix + ".csv")
                    else:
                        print("Could not load contours - df saved without coordinates.")                  
                
        ## feedback
        if len(loaded) > 0:
            print("=== AUTOLOAD ===\n- " + "\n- ".join(loaded))
        else:
            print("Nothing loaded.")
            
            

    def reset(self):
        """
        Resets modified images, canvas and df_image_data to original state. Can be used manually, but is typically used within the
        pype routine.

        """
        ## images
        self.image = copy.deepcopy(self.image_copy)
        self.image_bin = None
        self.image_gray = None
        self.canvas = None

        ## attributes
        self.reference_manual_mode = False

        # if hasattr(self, "df_masks"):
        #     del(self.df_masks)

        if hasattr(self, "df_contours"):
            del self.df_contours



#%% functions


def load_image(
    path,
    mode="default",
    load_container=False,
    dirpath=None,
    save_suffix=None,
    **kwargs
):
    """
    Create ndarray from image path or return or resize exising array.

    Parameters
    ----------
    path: str
        path to an image stored on the harddrive
    mode: {"default", "colour","gray"} str, optional
        image conversion on loading:
            - default: load image as is
            - colour: convert image to 3-channel (BGR)
            - gray: convert image to single channel (grayscale)
    load_container: bool, optional
        should the loaded image (and DataFrame) be returned as a phenopype 
        container
    dirpath: str, optional
        path to an existing directory where all output should be stored. default 
        is the current working directory ("cwd") of the python session.
    save_suffix : str, optional
        suffix to append to filename of results files, if container is created
    kwargs: 
        developer options

    Returns
    -------
    container: container
        A phenopype container is a Python class where loaded images, 
        dataframes, detected contours, intermediate output, etc. are stored 
        so that they are available for inspection or storage at the end of 
        the analysis. 
    image: ndarray
        original image (resized, if selected)

    """
    ## set flags
    flags = AttrDict({"mode":mode,"container":load_container})

    ## load image
    if path.__class__.__name__ == "str":
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1]
            if ext.replace(".", "") in default_filetypes:
                if flags.mode == "default":
                    image = cv2.imread(path)
                elif flags.mode == "colour":
                    image = cv2.imread(path, cv2.IMREAD_COLOR)
                elif flags.mode == "gray":
                    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)     
            else:
                print("Invalid file extension \"{}\" - could not load image:\n".format(ext) \
                        + os.path.basename(path))
                return
        else:
            print("Invalid image path - could not load image.")
            return
    elif path.__class__.__name__ == "ndarray":
        image = path
    else:
        print("Invalid input format - could not load image.")
        return

    ## check dirpath
    if flags.container == True:
        if dirpath == "cwd":
            dirpath = os.getcwd()
            if flag_verbose:
                print(
                    "Setting directory to save phenopype-container output to current working directory:\n" \
                    + os.path.abspath(dirpath)
                )
        elif dirpath.__class__.__name__ == "str":
            if not os.path.isdir(dirpath):
                user_input = input(
                    "Provided directory to save phenopype-container output {} does not exist - create?.".format(
                        os.path.abspath(dirpath)
                    )
                )
                if user_input in confirm_options:
                    os.makedirs(dirpath)
                else:
                    print("Directory not created - aborting")
                    return
            else:
                if flag_verbose:
                    print("Directory to save phenopype-container output set at - " + os.path.abspath(dirpath))
        elif dirpath.__class__.__name__ == "NoneType":
            if path.__class__.__name__ == "str":
                if os.path.isfile(path):
                    dirpath = os.path.dirname(os.path.abspath(path))
                    if flag_verbose:
                        print("Directory to save phenopype-container output set to parent folder of image:\n{}".format(dirpath))
            else: 
                print(
                    "No directory provided to save phenopype-container output" +
                    " - provide dirpath or use dirpath==\"cwd\" to set save" +
                    " paths to current working directory - aborting."
                      )
                return
            
            
    ## create container
    if flags.container:
        return Container(image, dirpath=dirpath, save_suffix=save_suffix)
    else:
        return image


def load_pp_directory(
    dirpath, 
    load_container=True, 
    save_suffix=None, 
    **kwargs
):
    """
    Parameters
    ----------
    dirpath: str or ndarray
        path to a phenopype project directory containing raw image, attributes 
        file, masks files, results df, etc.
    cont: bool, optional
        should the loaded image (and DataFrame) be returned as a phenopype 
        container
    save_suffix : str, optional
        suffix to append to filename of results files
    kwargs: 
        developer options
        
    Returns
    -------
    container
        A phenopype container is a Python class where loaded images, 
        dataframes, detected contours, intermediate output, etc. are stored 
        so that they are available for inspection or storage at the end of 
        the analysis. 

    """
    ## set flags
    flags = AttrDict({"container":load_container})    
    
    ## check if directory
    if not os.path.isdir(dirpath):
        print("Not a valid phenoype directory - cannot load files.")
        return
    
    ## check if attributes file and load otherwise
    if not os.path.isfile(os.path.join(dirpath, "attributes.yaml")):
        print("Attributes file missing - cannot load files.")
        return
    else:
        attributes = _load_yaml(os.path.join(dirpath, "attributes.yaml"))
    
    ## check if requires info is contained in attributes and load image
    if not "image_phenopype" in attributes or not "image_original" in attributes:
        print("Attributes doesn't contain required meta-data - cannot load files.")
        return 

    ## load image
    if attributes["image_phenopype"]["mode"] == "link":
        image_path =  attributes["image_original"]["filepath"]
    else:
        image_path =  os.path.join(dirpath,attributes["image_phenopype"]["filename"])
        
    ## return
    return load_image(image_path, load_container=flags.container, dirpath=dirpath)
    


def save_image(
    image,
    name,
    dirpath=os.getcwd(),
    resize=1,
    append="",
    extension="jpg",
    overwrite=False,
    **kwargs
):
    """Save an image (array) to jpg.
    
    Parameters
    ----------
    image: array
        image to save
    name: str
        name for saved image
    save_dir: str, optional
        directory to save image
    append: str, optional
        append image name with string to prevent overwriting
    extension: str, optional
        file extension to save image as
    overwrite: boo, optional
        overwrite images if name exists
    resize: float, optional
        resize factor for the image (1 = 100%, 0.5 = 50%, 0.1 = 10% of
        original size).
    kwargs: 
        developer options
    """

    ## kwargs
    flag_overwrite = overwrite

    # set dir and names
    # if "." in name:
    #     warnings.warn("need name and extension specified separately")
    #     return
    if append == "":
        append = ""
    else:
        append = "_" + append
    if "." not in extension:
        extension = "." + extension
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)

    ## resize
    if resize < 1:
        image = cv2.resize(
            image, (0, 0), fx=1 * resize, fy=1 * resize, interpolation=cv2.INTER_AREA
        )

    ## construct save path
    new_name = name + append + extension
    path = os.path.join(dirpath, new_name)

    ## save
    while True:
        if os.path.isfile(path) and flag_overwrite == False:
            print("Image not saved - file already exists (overwrite=False).")
            break
        elif os.path.isfile(path) and flag_overwrite == True:
            print("Image saved under " + path + " (overwritten).")
            pass
        elif not os.path.isfile(path):
            print("Image saved under " + path + ".")
            pass
        cv2.imwrite(path, image)
        break



def show_image(
    image,
    max_dim=1200,
    position_reset=True,
    position_offset=25,
    window_aspect="normal",
    check=True,
    **kwargs
):
    """
    Show one or multiple images by providing path string or array or list of 
    either.
    
    Parameters
    ----------
    image: array, list of arrays
        the image or list of images to be displayed. can be array-type, 
        or list or arrays
    max_dim: int, optional
        maximum dimension on either acis
    window_aspect: {"fixed", "free"} str, optional
        type of opencv window ("free" is resizeable)
    position_reset: bool, optional
        flag whether image positions should be reset when reopening list of 
        images
    position_offset: int, optional
        if image is list, the distance in pixels betweeen the positions of 
        each newly opened window (only works in conjunction with 
        "position_reset")
    check: bool, optional
        user input required when more than 10 images are opened at the same 
        time
    """
    ## kwargs
    flag_check = check
    test_params = kwargs.get("test_params", {})

    ## load image
    if image.__class__.__name__ == "ndarray":
        pass
    elif image.__class__.__name__ == "container":
        if not image.canvas.__class__.__name__ == "NoneType":
            image = copy.deepcopy(image.canvas)
        else:
            image = copy.deepcopy(image.image)
    elif image.__class__.__name__ == "list":
        pass
    else:
        print("wrong input format.")
        return

    ## open images list or single images
    while True:
        if isinstance(image, list):
            if len(image) > 10 and flag_check == True:
                warning_string = (
                    "WARNING: trying to open "
                    + str(len(image))
                    + " images - proceed (y/n)?"
                )
                check = input(warning_string)
                if check in ["y", "Y", "yes", "Yes"]:
                    print("Proceed - Opening images ...")
                    pass
                else:
                    print("Aborting")
                    break
            idx = 0
            for i in image:
                idx += 1
                if i.__class__.__name__ == "ndarray":
                    _ImageViewer(
                        i,
                        mode="",
                        window_aspect=window_aspect,
                        window_name="phenopype" + " - " + str(idx),
                        window_control="external",
                        max_dim=max_dim,
                        previous=test_params,
                    )
                    if position_reset == True:
                        cv2.moveWindow(
                            "phenopype" + " - " + str(idx),
                            idx + idx * position_offset,
                            idx + idx * position_offset,
                        )
                else:
                    print("skipped showing list item of type " + i.__class__.__name__)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            break
        else:
            _ImageViewer(
                image=image,
                mode="",
                window_aspect=window_aspect,
                window_name="phenopype",
                window_control="internal",
                # max_dim=max_dim,
                # previous=test_params,
            )
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            break
        
        
        
def show_pype_config_template(template):
    """
    
    Helper function to print phenopype configuration file in formatted yaml.

    Parameters
    ----------
    template : str
        name of pype configuration file to print (with or without ".yaml")

    Returns
    -------
    None

    """
    
    if not template.endswith(".yaml"):
        template_name = template + ".yaml"
    else:
        template_name = template
    if template_name in pype_config_template_list:
        config_steps = _load_yaml(pype_config_template_list[template_name])
        print("SHOWING BUILTIN PHENOPYPE TEMPLATE " + template_name + "\n\n")
        _show_yaml(config_steps)
        
