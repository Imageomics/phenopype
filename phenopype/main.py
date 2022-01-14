#%% modules
import copy
import os
import pandas as pd
import platform
import string

from dataclasses import make_dataclass

import pprint
import subprocess
import time

import cv2
import ruamel.yaml
from datetime import datetime

import shutil
from ruamel.yaml.comments import CommentedMap as ordereddict

from phenopype import __version__
from phenopype import _config
from phenopype import settings
from phenopype import utils
from phenopype import utils_lowlevel

from phenopype.core import (
    preprocessing,
    segmentation,
    measurement,
    export,
    visualization,
)


#%% settings

pd.options.display.max_rows = (
    settings.pandas_max_rows
)  # how many rows of pd-dataframe to show
pretty = pprint.PrettyPrinter(width=30)  # pretty print short strings
ruamel.yaml.Representer.add_representer(
    ordereddict, ruamel.yaml.Representer.represent_dict
)  # suppress !!omap node info

#%% classes


class Project:
    """
    Initialize a phenopype project with a root directory path. Phenopype 
    will create the project folder at the provided location. 

    Parameters
    ----------
    rootdir: str
        path to root directory of the project where folder gets created
    overwrite: bool, optional
        overwrite option, if a given root directory already exist 
        (WARNING: also removes all folders inside)

    Returns
    -------
    project: project
        phenopype project
    """

    def __init__(self, root_dir, load=True, overwrite=False):

        ## set flags
        flags = make_dataclass(
            cls_name="flags",
            fields=[("load", bool, load), ("overwrite", bool, overwrite)],
        )

        ## path conversion
        root_dir = root_dir.replace(os.sep, "/")
        root_dir = os.path.abspath(root_dir)

        print("--------------------------------------------")
        while True:
            if os.path.isdir(root_dir):
                if all(
                    [
                        "attributes.yaml" in os.listdir(root_dir),
                        "data" in os.listdir(root_dir),
                    ]
                ):
                    if flags.load and not flags.overwrite:
                        print(
                            "Found existing project root directory - loading from:\n"
                            + root_dir
                        )
                        break
                    elif not flags.load and flags.overwrite:
                        pass
                    elif flags.load and flags.overwrite:
                        print(
                            "Found existing phenopype project directory at:\n{}\n".format(
                                root_dir
                            )
                        )
                        query1 = input("overwrite (y/n)?")
                        if query1 in settings.confirm_options:
                            pass
                        else:
                            print(
                                'Aborted - project "{}" not overwritten'.format(
                                    os.path.basename(root_dir)
                                )
                            )
                            return
                    shutil.rmtree(root_dir, onerror=utils_lowlevel._del_rw)
                    os.makedirs(root_dir)
                    os.makedirs(os.path.join(root_dir, "data"))
                    print('\n"' + root_dir + '" created (overwritten)')
                    break
                else:
                    print(
                        "Directory is neither empty nor a valid phenopype directory - aborting."
                    )
                    return
            else:
                print(
                    "Creating a new phenopype project directory at:\n" + root_dir + "\n"
                )
                query2 = input("Proceed? (y/n)\n")
                if query2 in settings.confirm_options:
                    os.makedirs(root_dir)
                    os.makedirs(os.path.join(root_dir, "data"))
                    break
                else:
                    print('\n"' + root_dir + '" not created!')
                    return

        ## read directories
        dir_names, dir_paths = os.listdir(os.path.join(root_dir, "data")), []
        for file_path in os.listdir(os.path.join(root_dir, "data")):
            dir_paths.append(os.path.join(root_dir, "data", file_path))

        ## global project attributes
        if not os.path.isfile(os.path.join(root_dir, "attributes.yaml")):
            project_attributes = {
                "project_info": {
                    "date_created": datetime.today().strftime(settings.strftime_format),
                    "date_changed": datetime.today().strftime(settings.strftime_format),
                    "phenopype_version": __version__,
                },
                "project_data": None,
            }
            utils_lowlevel._save_yaml(
                project_attributes, os.path.join(root_dir, "attributes.yaml")
            )
            print(
                '\nProject "{}" successfully created.'.format(
                    os.path.basename(root_dir)
                )
            )
        else:
            if len(dir_names) > 0:
                print(
                    '\nProject "{}" successfully loaded with {} images'.format(
                        os.path.basename(root_dir), len(dir_paths)
                    )
                )
            else:
                print(
                    '\nProject "{}" successfully loaded, but it didn\'t contain any images!'.format(
                        os.path.basename(root_dir)
                    )
                )

        print("--------------------------------------------")

        ## attach to instance
        self.root_dir = root_dir
        self.dir_names = dir_names
        self.dir_paths = dir_paths

    def add_files(
        self,
        image_dir,
        filetypes=settings.default_filetypes,
        include=[],
        include_all=True,
        exclude=[],
        mode="copy",
        ext="tif",
        recursive=False,
        overwrite=False,
        resize_factor=1,
        unique="path",
        **kwargs
    ):
        """
        Add files to your project from a directory, can look recursively. 
        Specify in- or exclude arguments, filetypes, duplicate-action and copy 
        or link raw files to save memory on the harddrive. For each found image,
        a folder will be created in the "data" folder within the projects root
        directory. If found images are in subfolders and "recursive==True", 
        the respective phenopype directories will be created with 
        flattened path as prefix. 
        
        E.g., with "raw_files" as folder with the original image files 
        and "phenopype_proj" as rootfolder:
        
        - raw_files/file.jpg ==> phenopype_proj/data/file.jpg
        - raw_files/subdir1/file.jpg ==> phenopype_proj/data/1__subdir1__file.jpg
        - raw_files/subdir1/subdir2/file.jpg ==> phenopype_proj/data/2__subdir1__subdir2__file.jpg
    
        Parameters
        ----------
        image_dir: str 
            path to directory with images
        filetypes: list or str, optional
            single or multiple string patterns to target files with certain endings.
            "settings.default_filetypes" are configured in settings.py: 
            ['jpg', 'JPG', 'jpeg', 'JPEG', 'tif', 'png', 'bmp']
        include: list or str, optional
            single or multiple string patterns to target certain files to include
        include_all (optional): bool,
            either all (True) or any (False) of the provided keywords have to match
        exclude: list or str, optional
            single or multiple string patterns to target certain files to exclude - 
            can overrule "include"
        recursive: (optional): bool,
            "False" searches only current directory for valid files; "True" walks 
            through all subdirectories
        unique: {"file_path", "filename"}, str, optional:
            how to deal with image duplicates - "file_path" is useful if identically 
            named files exist in different subfolders (folder structure will be 
            collapsed and goes into the filename), whereas filename will ignore 
            all similar named files after their first occurrence.
        mode: {"copy", "mod", "link"} str, optional
            how should the raw files be passed on to the phenopype directory tree: 
            "copy" will make a copy of the original file, "mod" will store a 
            .tif version of the orginal image that can be resized, and "link" 
            will only store the link to the original file location to attributes, 
            but not copy the actual file (useful for big files, but the orginal 
            location needs always to be available)
        overwrite: {"file", "dir", False} str/bool (optional)
            "file" will overwrite the image file and modify the attributes accordingly, 
            "dir" will  overwrite the entire image directory (including all meta-data
            and results!), False will not overwrite anything
        ext: {".tif", ".bmp", ".jpg", ".png"}, str, optional
            file extension for "mod" mode
        resize_factor: float, optional
            
        kwargs: 
            developer options
        """

        # kwargs
        flags = make_dataclass(
            cls_name="flags",
            fields=[
                ("mode", str, mode),
                ("recursive", bool, recursive),
                ("overwrite", bool, overwrite),
                ("resize", bool, False),
            ],
        )

        if resize_factor < 1:
            flags.resize = True
            if not flags.mode == "mod":
                flags.mode = "mod"
                print('Resize factor <1 or >1 - switched to "mod" mode')

        ## path conversion
        image_dir = image_dir.replace(os.sep, "/")
        image_dir = os.path.abspath(image_dir)

        ## collect filepaths
        filepaths, duplicates = utils_lowlevel._file_walker(
            directory=image_dir,
            recursive=recursive,
            unique=unique,
            filetypes=filetypes,
            exclude=exclude,
            include=include,
            include_all=include_all,
        )

        ## feedback
        print("--------------------------------------------")
        print("phenopype will search for image files at\n")
        print(image_dir)
        print("\nusing the following settings:\n")
        print(
            "filetypes: "
            + str(filetypes)
            + ", include: "
            + str(include)
            + ", exclude: "
            + str(exclude)
            + ", mode: "
            + str(flags.mode)
            + ", recursive: "
            + str(flags.recursive)
            + ", resize: "
            + str(flags.resize)
            + ", unique: "
            + str(unique)
            + "\n"
        )

        ## loop through files
        for file_path in filepaths:

            ## generate folder paths by flattening nested directories; one
            ## folder per file
            relpath = os.path.relpath(file_path, image_dir)
            depth = relpath.count("\\")
            relpath_flat = os.path.dirname(relpath).replace("\\", "__")
            if depth > 0:
                subfolder_prefix = str(depth) + "__" + relpath_flat + "__"
            else:
                subfolder_prefix = str(depth) + "__"

            dir_name = (
                subfolder_prefix + os.path.splitext(os.path.basename(file_path))[0]
            )
            dir_path = os.path.join(self.root_dir, "data", dir_name)

            ## make image-specific directories
            if os.path.isdir(dir_path):
                if flags.overwrite == False:
                    print(
                        "Found image "
                        + relpath
                        + " - "
                        + dir_name
                        + " already exists (overwrite=False)"
                    )
                    continue
                elif flags.overwrite in ["file", "files", "image", "True"]:
                    pass
                elif flags.overwrite == "dir":
                    shutil.rmtree(
                        dir_path, ignore_errors=True, onerror=utils_lowlevel._del_rw
                    )
                    print(
                        "Found image "
                        + relpath
                        + " - "
                        + "phenopype-project folder "
                        + dir_name
                        + ' created (overwrite == "dir")'
                    )
                    os.mkdir(dir_path)
            else:
                print(
                    "Found image "
                    + relpath
                    + " - "
                    + "phenopype-project folder "
                    + dir_name
                    + " created"
                )
                os.mkdir(dir_path)

            ## load image, image-data, and image-meta-data
            image = utils.load_image(file_path)
            image_name = os.path.basename(file_path)
            image_name_root = os.path.splitext(image_name)[0]
            image_ext = os.path.splitext(image_name)[1]
            
            print(file_path)
            
            image_data_original = utils_lowlevel._load_image_data(file_path)
            image_data_phenopype = {
                "date_added": datetime.today().strftime(settings.strftime_format),
                "mode": flags.mode,
            }

            ## copy or link raw files
            if flags.mode == "copy":
                image_phenopype_path = os.path.join(
                    self.root_dir, "data", dir_name, image_name_root + "_copy" + image_ext,
                )
                shutil.copyfile(file_path, image_phenopype_path)
                image_data_phenopype.update(
                    utils_lowlevel._load_image_data(
                        image_phenopype_path, path_and_type=False
                    )
                )

            elif flags.mode == "mod":
                if resize_factor < 1:
                    image = utils_lowlevel._resize_image(image, resize_factor)
                if not "." in ext:
                    ext = "." + ext
                image_phenopype_path = os.path.join(
                    self.root_dir, "data", dir_name, image_name_root + "_mod" + ext,
                )
                if os.path.isfile(image_phenopype_path) and flags.overwrite == "file":
                    print(
                        "Found image "
                        + image_phenopype_path
                        + " in "
                        + dir_name
                        + ' - overwriting (overwrite == "files")'
                    )
                cv2.imwrite(image_phenopype_path, image)
                image_data_phenopype.update(
                    {"resize": flags.resize, "resize_factor": resize_factor,}
                )
                image_data_phenopype.update(
                    utils_lowlevel._load_image_data(
                        image_phenopype_path, path_and_type=False
                    )
                )

            elif flags.mode == "link":
                image_phenopype_path = file_path

            ## write attributes file
            attributes = {
                "image_original": image_data_original,
                "image_phenopype": image_data_phenopype,
            }
            if (
                os.path.isfile(os.path.join(dir_path, "attributes.yaml"))
                and flags.overwrite == "file"
            ):
                print("overwriting attributes")
            utils_lowlevel._save_yaml(
                attributes, os.path.join(dir_path, "attributes.yaml")
            )

        ## list dirs in data and add to project-attributes file in project root
        project_attributes = utils_lowlevel._load_yaml(
            os.path.join(self.root_dir, "attributes.yaml")
        )
        project_attributes["project_data"] = os.listdir(
            os.path.join(self.root_dir, "data")
        )
        utils_lowlevel._save_yaml(
            project_attributes, os.path.join(self.root_dir, "attributes.yaml")
        )

        ## add dirlist to project object (always overwrite)
        dir_names = os.listdir(os.path.join(self.root_dir, "data"))
        dir_paths = []
        for dir_name in dir_names:
            dir_paths.append(os.path.join(self.root_dir, "data", dir_name))
        self.dir_names = dir_names
        self.dir_paths = dir_paths

        print("\nFound {} files".format(len(filepaths)))
        print("--------------------------------------------")

    def add_config(
        self,
        tag,
        template_path,
        interactive=False,
        image_number=1,
        overwrite=False,
        **kwargs
    ):
        """
        Add pype configuration presets to all image folders in the project, either by using
        the templates included in the presets folder, or by adding your own templates
        by providing a path to a yaml file. Can be tested and modified using the 
        interactive flag before distributing the config files.

        Parameters
        ----------

        tag: str
            tag of config-file. this gets appended to all files and serves as and
            identifier of a specific analysis pipeline
        template_path: str, optional
            path to a template or config-file in yaml-format
        interactive: bool, optional
            start a pype and modify template before saving it to phenopype directories
        interactive_image: str, optional
            to modify pype config in interactive mode, select image from list of images
            (directory names) already included in the project. special flag "first" is 
            default and takes first image in "data" folder. 
        overwrite: bool, optional
            overwrite option, if a given pype config-file already exist
        kwargs: 
            developer options
        """

        ## kwargs and setup
        flag_interactive = interactive
        flag_overwrite = overwrite

        utils_lowlevel._check_pype_tag(tag)

        ## interactive template modification
        if flag_interactive:
            if len(self.dir_paths) > 0:
                dir_path = self.dir_paths[image_number - 1]
            else:
                print(
                    "Project contains no images - could not add config files in interactive mode."
                )
                return

            if os.path.isdir(dir_path):
                container = utils_lowlevel._load_project_image_directory(dir_path)
                container.dir_path = os.path.join(self.root_dir, "_template-mod")
            else:
                print("Could not enter interactive mode - invalid directory.")
                return

            if not os.path.isdir(container.dir_path):
                os.mkdir(container.dir_path)

            config_path = utils.load_template(
                template_path=template_path,
                dir_path=container.dir_path,
                tag="template-mod",
                overwrite=True,
                ret_path=True,
            )

            ## run pype
            p = Pype(container, tag="template-mod", config_path=config_path,)
            template_path = p.config_path

        ## save config to each directory
        for dir_path in self.dir_paths:
            utils.load_template(
                template_path=template_path,
                dir_path=dir_path,
                tag=tag,
                overwrite=flag_overwrite,
            )

        if flag_interactive:
            q = input("Save modified template? ")
            if q in settings.confirm_options:
                template_dir = os.path.join(self.root_dir, "templates")
                if not os.path.isdir(template_dir):
                    os.mkdir(template_dir)
                q = input("Enter template file name: ")
                if q.endswith(".yaml"):
                    ext = ""
                else:
                    ext = ".yaml"
                template_file_name = q + ext

                template_save_path = os.path.join(template_dir, template_file_name)
                if utils_lowlevel._save_prompt("template", template_save_path, False):
                    utils_lowlevel._save_yaml(p.config, template_save_path)

    def add_reference(
        self,
        reference_image_path,
        reference_tag,
        activate=True,
        template=False,
        overwrite=False,
        **kwargs
    ):
        """
        Add pype configuration presets to all project directories. 

        Parameters
        ----------

        reference_image: str
            name of template image, either project directory or file link. template 
            image gets stored in root directory, and information appended to all 
            attributes files in the project directories
        activate: bool, optional
            writes the setting for the currently active reference to the attributes 
            files of all directories within the project. can be used in conjunction
            with overwrite=False so that the actual reference remains unchanced. this
            setting useful when managing multiple references per project
        overwrite: bool, optional
            overwrite option, if a given pype config-file already exist
        template: bool, optional
            should a template for reference detection be created. with an existing 
            template, phenopype can try to find a reference card in a given image,
            measure its dimensions, and adjust pixel-to-mm-ratio and colour space
        """
        # =============================================================================
        # setup

        ## set flags
        flags = make_dataclass(
            cls_name="flags",
            fields=[("overwrite", bool, overwrite), ("activate", bool, activate),],
        )

        print_save_msg = "== no msg =="

        reference_source_path = copy.deepcopy(reference_image_path)

        ## load reference image
        if reference_source_path.__class__.__name__ == "str":
            reference_image = utils.load_image(reference_source_path)

        # =============================================================================
        # execute

        reference_folder_path = os.path.join(self.root_dir, "reference")
        if not os.path.isdir(reference_folder_path):
            os.mkdir(reference_folder_path)

        while True:

            ## generate reference name and check if exists
            reference_image_name = reference_tag + "_full_image.tif"
            reference_image_path = os.path.join(
                self.root_dir, "reference", reference_image_name
            )

            if os.path.isfile(reference_image_path) and flags.overwrite == False:
                print_save_msg = (
                    "Reference image not saved, file already exists "
                    + '- use "overwrite==True" or chose different name.'
                )
                break
            elif os.path.isfile(reference_image_path) and flags.overwrite == True:
                print_save_msg = (
                    "Reference image saved under "
                    + reference_image_path
                    + " (overwritten)."
                )
                pass
            elif not os.path.isfile(reference_image_path):
                print_save_msg = "Reference image saved under " + reference_image_path
                pass

            ## generate template name and check if exists
            template_name = reference_tag + "_search_template.tif"
            template_path = os.path.join(self.root_dir, "reference", template_name)

            if os.path.isfile(template_path) and flags.overwrite == False:
                print_save_msg = 'Reference template not saved, file already exists\
                 - use "overwrite==True" or chose different name.'
                break
            elif os.path.isfile(template_path) and flags.overwrite == True:
                print_save_msg = (
                    print_save_msg
                    + "\nReference image saved under "
                    + template_path
                    + " (overwritten)."
                )
                pass
            elif not os.path.isfile(template_path):
                print_save_msg = (
                    print_save_msg + "\nReference image saved under " + template_path
                )
                pass

            # =============================================================================
            # annotation management (for tests)

            annotations = kwargs.get("annotations")

            if not annotations:

                ## measure reference
                annotations = preprocessing.create_reference(reference_image)
                annotations = preprocessing.create_mask(
                    reference_image, annotations=annotations
                )

            ## create template from mask coordinates
            coords = annotations[settings._mask_type]["a"]["data"][settings._mask_type][
                0
            ]
            template = reference_image[
                coords[0][1] : coords[2][1], coords[0][0] : coords[1][0]
            ]

            ## create reference attributes
            reference_info = {
                "reference_source_path": reference_source_path,
                "reference_file_name": reference_image_name,
                "template_file_name": template_name,
                "template_px_ratio": annotations[settings._reference_type]["a"]["data"][
                    settings._reference_type
                ][0],
                "unit": annotations[settings._reference_type]["a"]["data"][
                    settings._reference_type
                ][1],
                "date_added": datetime.today().strftime(settings.strftime_format),
            }

            ## load project attributes and temporarily drop project data list to
            ## be reattched later, so it is always at then end of the file
            reference_dict = {}
            project_attributes = utils_lowlevel._load_yaml(
                os.path.join(self.root_dir, "attributes.yaml")
            )
            if "project_data" in project_attributes:
                project_data = project_attributes["project_data"]
                project_attributes.pop("project_data", None)
            if "reference" in project_attributes:
                reference_dict = project_attributes["reference"]
            reference_dict[reference_tag] = reference_info

            project_attributes["reference"] = reference_dict
            project_attributes["project_data"] = project_data

            ## save all after successful completion of all method-steps
            cv2.imwrite(reference_image_path, reference_image)
            cv2.imwrite(template_path, template)

            utils_lowlevel._save_yaml(
                project_attributes, os.path.join(self.root_dir, "attributes.yaml")
            )
            print_save_msg = (
                print_save_msg + "\nSaved reference info to project attributes."
            )
            break

        print(print_save_msg)

        # =============================================================================
        # METHOD END
        # =============================================================================

        ## set active reference information in file specific attributes
        for dir_name, dir_path in zip(self.dir_names, self.dir_paths):
            attr = utils_lowlevel._load_yaml(os.path.join(dir_path, "attributes.yaml"))

            ## create nested dict
            if not "reference_global" in attr:
                attr["reference_global"] = {}
            if not reference_tag in attr["reference_global"]:
                attr["reference_global"][reference_tag] = {}

            ## loop through entries and set active reference
            if flags.activate == True:
                for key, value in attr["reference_global"].items():
                    if key == reference_tag:
                        attr["reference_global"][key]["active"] = True
                    else:
                        attr["reference_global"][key]["active"] = False
                utils_lowlevel._save_yaml(
                    attr, os.path.join(dir_path, "attributes.yaml")
                )
                print(
                    'setting active global project reference to "'
                    + reference_tag
                    + '" for '
                    + dir_name
                    + " (active=True)"
                )
            else:
                print(
                    "could not set global project reference for "
                    + dir_name
                    + " (overwrite=False/activate=False)"
                )

    def collect_results(self, tag, files, folder, overwrite=False, **kwargs):

        """
        Collect canvas from each folder in the project tree. Search by 
        name/safe_suffix (e.g. "v1").

        Parameters
        ----------
        name : str
            name of the pype or save_suffix
        folder : str, optional
            folder in the root directory where the results are stored
        overwrite : bool, optional
            should the results be overwritten

        """

        ## set flags
        flags = make_dataclass(
            cls_name="flags", fields=[("overwrite", bool, overwrite)]
        )

        results_path = os.path.join(self.root_dir, "results", folder)

        if not os.path.isdir(results_path):
            os.makedirs(results_path)
            print("Created " + results_path)

        ## search string
        if not files.__class__.__name__ == "NoneType":
            if not files.__class__.__name__ == "list":
                files = [files]
            search_strings = []
            for file in files:
                if not tag == "":
                    search_strings.append(file + "_" + tag)
                else:
                    search_strings.append(file)
        else:
            search_strings = tag

        ## append name
        print("Search string: " + str(search_strings))

        ## exclude strings
        exclude = kwargs.get("exclude", [])
        if not exclude.__class__.__name__ == "NoneType":
            if exclude.__class__.__name__ == "str":
                exclude = [exclude]

        ## search
        found, duplicates = utils_lowlevel._file_walker(
            os.path.join(self.root_dir, "data"),
            recursive=True,
            include=search_strings,
            exclude=["pype_config"] + exclude,
        )

        ## collect
        for file_path in found:
            print(
                "Collected "
                + os.path.basename(file_path)
                + " from "
                + os.path.basename(os.path.dirname(file_path))
            )
            filename = (
                os.path.basename(os.path.dirname(file_path))
                + "_"
                + os.path.basename(file_path)
            )
            path = os.path.join(results_path, filename)

            ## overwrite check
            while True:
                if os.path.isfile(path) and flags.overwrite == False:
                    print(
                        filename + " not saved - file already exists (overwrite=False)."
                    )
                    break
                elif os.path.isfile(path) and flags.overwrite == True:
                    print(filename + " saved under " + path + " (overwritten).")
                    pass
                elif not os.path.isfile(path):
                    print(filename + " saved under " + path + ".")
                    pass
                shutil.copyfile(file_path, path)
                break

    def edit_config(self, tag, target, replacement, **kwargs):
        """
        Add or edit functions in all configuration files of a project. Finds and
        replaces single or multiline string-patterns. Ideally this is done via 
        python docstrings that represent the parts of the yaml file to be replaced.
                
        Parameters
        ----------

        tag: str
            tag (suffix) of config-file (e.g. "v1" in "pype_config_v1.yaml")
        target: str
            string pattern to be replaced. should be in triple-quotes to be exact
        replacement: str
            string pattern for replacement. should be in triple-quotes to be exact
        """

        ## setup
        flag_checked = False

        ## go through project directories
        for directory in self.dir_paths:
            dir_name = os.path.basename(directory)

            ## get config path
            config_path = os.path.join(
                self.root_dir, "data", dir_name, "pype_config_" + tag + ".yaml"
            )

            ## open config-file
            if os.path.isfile(config_path):
                with open(config_path, "r") as config_text:
                    config_string = config_text.read()
            else:
                print("Did not find config file to edit - check provided tag/suffix.")
                return
            ## string replacement
            new_config_string = config_string.replace(target, replacement)

            ## show user replacement-result and ask for confirmation
            if flag_checked == False:
                print(new_config_string)
                check = input(
                    "This is what the new config may look like (can differ beteeen files) - proceed?"
                )

            ## replace for all config files after positive user check
            if check in settings.confirm_options:
                flag_checked = True
                with open(config_path, "w") as config_text:
                    config_text.write(new_config_string)

                print("New config saved for " + dir_name)
            else:
                print("User check failed - aborting.")
                break


class Pype(object):
    """
    The pype is phenopype’s core method that allows running all functions 
    that are available in the program’s library in sequence. Users can execute 
    the pype method on a file_path, an array, or a phenopype directory, which 
    always will trigger three actions:

    1. open the contained yaml configuration with the default OS text editor
    2. parse the contained functions and execute them in the sequence (exceptions
       will be passed, but returned for diagnostics)
    3. open a Python-window showing the processed image.
    
    After one iteration of these steps, users can evaluate the results and decide
    to modify the opened configuration file (e.g. either change function parameters or 
    add new functions), and run the pype again, or to terminate the pype and 
    save all results. The processed image, any extracted phenotypic information, 
    as well as the modified config-file is stored inside the image directory, or
    a user-specified directory. By providing unique names, users can store different
    pype configurations and the associated results side by side. 
    
    Parameters
    ----------

    image: array or str 
        can be either a numpy array or a string that provides the path to 
        source image file or path to a valid phenopype directory
    name: str
        name of pype-config - will be appended to all results files
    config_template: str, optional
        chose from list of provided templates  
        (e.g. ex1, ex2, ...)
    config_path: str, optional
        custom path to a pype template (needs to adhere yaml syntax and 
        phenopype structure)
    delay: int, optional
        time in ms to add between reload attemps of yaml monitor. increase this 
        value if saved changes in config file are not parsed in the first attempt.
    dir_path: str, optional
        path to an existing directory where all output should be stored
    skip: bool, optional
        skip directories that already have "name" as a suffix in the filename
    feedback: bool, optional
        don't open text editor or window, just apply functions and terminate
    max_dim: int, optional
        maximum dimension that window can have 
    kwargs: 
        developer options
    """

    def __init__(
        self,
        image_path,
        tag,
        config_path=None,
        skip=False,
        autosave=True,
        autoload=True,
        fix_names=True,
        feedback=True,
        visualize=True,
        debug=False,
        **kwargs
    ):

        # =============================================================================
        # CHECKS & INIT
        # =============================================================================

        ## kwargs
        global window_max_dim
        window_max_dim = kwargs.get("window_max_dim")
        delay = kwargs.get("delay", 500)
        sleep = kwargs.get("sleep", 0.2)

        ## flags
        self.flags = make_dataclass(
            cls_name="flags",
            fields=[
                ("debug", bool, debug),
                ("autosave", bool, autosave),
                ("autoload", bool, autoload),
                ("feedback", bool, feedback),
                ("fix_names", bool, fix_names),
                ("skip", bool, skip),
                ("terminate", bool, False),
                ("visualize", bool, visualize),
                ("dry_run", bool, kwargs.get("dry_run", False)),
            ],
        )

        ## check version, load container and config
        # if self.flags.dry_run:
        #     self._load_pype_config(tag, config)
        #     self._iterate(config=self.config, annotations=copy.deepcopy(settings._annotation_types),
        #               execute=False, visualize=False, feedback=True)
        # else:

        print("Format path to abspath")
        if image_path.__class__.__name__ == "str":
            image_path = os.path.abspath(image_path)

        ## check name, load container and config
        utils_lowlevel._check_pype_tag(tag)
        self._load_container(image_path=image_path, tag=tag)
        self._load_pype_config(image_path=image_path, tag=tag, config_path=config_path)

        ## check whether directory is skipped
        if self.flags.skip:
            if self._check_directory_skip(
                tag=tag, skip_pattern=skip, dir_path=self.container.dir_path
            ):
                return

        ## load existing annotations through container
        if self.flags.autoload:
            self.container.load()

        ## check pype config for annotations
        self._iterate(
            config=self.config,
            annotations=self.container.annotations,
            execute=False,
            visualize=False,
            feedback=False,
        )
        time.sleep(sleep)

        ## final check before starting pype
        self._check_final()

        # open config file with system viewer
        if self.flags.feedback and self.flags.visualize:
            self._start_file_monitor(delay=delay)

        ## start log
        self.log = []

        # =============================================================================
        # PYPE LOOP
        # =============================================================================

        ## run pype
        while True:

            ## pype restart flag
            _config.pype_restart = False

            ## refresh config
            if self.flags.feedback and self.flags.visualize:

                ## to stop infinite loop without opening new window
                if not self.YFM.content:
                    print("- STILL UPDATING CONFIG (no content)")
                    cv2.destroyWindow("phenopype")
                    time.sleep(1)
                    self.YFM._stop()
                    self._start_file_monitor(delay=delay)
                    continue

                self.config = copy.deepcopy(self.YFM.content)

                if not self.config:
                    print("- STILL UPDATING CONFIG (no config)")
                    continue

            ## run pype config in sequence
            self._iterate(
                config=self.config,
                annotations=self.container.annotations,
                feedback=self.flags.feedback,
                visualize=self.flags.visualize,
            )

            ## terminate
            if self.flags.visualize:
                if self.flags.terminate:
                    if hasattr(self, "YFM"):
                        self.YFM._stop()
                    print("\n\nTERMINATE")
                    break
            else:
                break

        if self.flags.autosave and self.flags.terminate:
            if "export" not in self.config_parsed_flattened:
                export_list = []
            else:
                export_list = self.config_parsed_flattened["export"]
            self.container.save(export_list=export_list)

    def _load_container(self, image_path, tag):
        if image_path.__class__.__name__ == "str":
            if os.path.isfile(image_path):
                image = utils.load_image(image_path)
                dir_path = os.path.dirname(image_path)
                self.container = utils.Container(
                    image=image,
                    dir_path=dir_path,
                    file_prefix=os.path.splitext(os.path.basename(image_path))[0],
                    file_suffix=tag,
                    image_name=os.path.basename(image_path),
                )
            elif os.path.isdir(image_path):
                self.container = utils_lowlevel._load_project_image_directory(
                    dir_path=image_path, tag=tag,
                )
            else:
                raise FileNotFoundError(
                    'Could not find image or image directory: "{}"'.format(
                        os.path.dirname(image_path)
                    )
                )
        elif image_path.__class__.__name__ == "Container":
            self.container = copy.deepcopy(image_path)
        else:
            raise TypeError("Invalid input for image path (str required)")

    def _load_pype_config(self, image_path, tag, config_path):

        if config_path.__class__.__name__ == "NoneType":
            if os.path.isfile(image_path):
                image_name_root = os.path.splitext(os.path.basename(image_path))[0]
                prepend = image_name_root + "_"
            elif os.path.isdir(image_path):
                prepend = ""

            ## generate config path from image file or directory (project)
            config_name = prepend + "pype_config_" + tag + ".yaml"
            config_path = os.path.join(self.container.dir_path, config_name)

        ## load config from config path
        elif config_path.__class__.__name__ == "str":
            if os.path.isfile(config_path):
                pass
            # else:
            #     raise FileNotFoundError(
            #         "Could not read config file from specified config_path: \"{}\"".format(config_path))

        if os.path.isfile(config_path):
            self.config = utils_lowlevel._load_yaml(config_path)
            self.config_path = config_path

            if "template_locked" in self.config:
                if self.config["template_locked"] == True:
                    raise AttributeError(
                        'Attempting to load config from locked template - create config file using "load_template" first.'
                    )
        else:
            raise FileNotFoundError(
                'Could not find config file "{}" in image directory: "{}"'.format(
                    config_name, os.path.dirname(image_path)
                )
            )

    def _start_file_monitor(self, delay):

        if platform.system() == "Darwin":  # macOS
            subprocess.call(("open", self.config_path))
        elif platform.system() == "Windows":  # Windows
            os.startfile(self.config_path)
        else:  # linux variants
            subprocess.call(("xdg-open", self.config_path))

        self.YFM = utils_lowlevel._YamlFileMonitor(self.config_path, delay)

    def _check_directory_skip(self, tag, skip_pattern, dir_path):

        ## skip directories that already contain specified files
        if skip_pattern.__class__.__name__ == "str":
            skip_pattern = [skip_pattern]
        elif skip_pattern.__class__.__name__ in ["list", "CommentedSeq"]:
            skip_pattern = skip_pattern

        file_pattern = []
        for pattern in skip_pattern:
            file_pattern.append(pattern + "_" + tag)

        filepaths, duplicates = utils_lowlevel._file_walker(
            dir_path,
            include=file_pattern,
            include_all=False,
            exclude=["pype_config", "attributes"],
            pype_mode=True,
        )

        if len(filepaths) == len(file_pattern):
            print('\nFound existing files "' + str(file_pattern) + '" - skipped\n')
            return True
        else:
            return False

    def _check_final(self):

        ## check components before starting pype to see if something went wrong
        if (
            not hasattr(self.container, "image")
            or self.container.image.__class__.__name__ == "NoneType"
        ):
            raise AttributeError("No image was loaded")
            return
        if (
            not hasattr(self.container, "dir_path")
            or self.container.dir_path.__class__.__name__ == "NoneType"
        ):
            raise AttributeError("Could not determine dir_path to save output.")
            return
        if not hasattr(self, "config") or self.config.__class__.__name__ == "NoneType":
            raise AttributeError(
                "No config file was provided or loading config did not succeed."
            )
            return

    def _iterate(
        self, config, annotations, execute=True, visualize=True, feedback=True,
    ):

        flags = make_dataclass(
            cls_name="flags",
            fields=[
                ("execute", bool, execute),
                ("visualize", bool, visualize),
                ("feedback", bool, feedback),
            ],
        )

        ## new iteration
        if flags.execute:
            print(
                "\n\n------------+++ new pype iteration "
                + datetime.today().strftime(settings.strftime_format)
                + " +++--------------\n\n"
            )

        # reset values
        if not self.flags.dry_run:
            self.container.reset()
        annotation_counter = dict.fromkeys(settings._annotation_types, -1)

        ## apply pype: loop through steps and contained methods
        step_list = self.config["processing_steps"]
        self.config_updated = copy.deepcopy(self.config)
        self.config_parsed_flattened = {}

        for step_idx, step in enumerate(step_list):

            # =============================================================================
            # STEP
            # =============================================================================

            if step.__class__.__name__ == "str":
                continue

            ## get step name
            step_name = list(dict(step).keys())[0]
            method_list = list(dict(step).values())[0]
            self.config_parsed_flattened[step_name] = []

            if method_list.__class__.__name__ == "NoneType":
                continue

            ## print current step
            if flags.execute:
                print("\n")
                print(step_name.upper())

            if step_name == "visualization" and flags.execute:

                ## check if canvas is selected, and otherwise execute with default values
                vis_list = [
                    list(dict(i).keys())[0] if not isinstance(i, str) else i
                    for i in method_list
                ]
                if (
                    self.container.canvas.__class__.__name__ == "NoneType"
                    and not "select_canvas" in vis_list
                ):
                    print("select_canvas (autoselect)")
                    self.container.run("select_canvas")

            ## iterate through step list
            for method_idx, method in enumerate(method_list):

                # =============================================================================
                # METHOD / EXTRACTION AND CHECK
                # =============================================================================

                ## format method name and arguments
                if method.__class__.__name__ in ["dict", "ordereddict", "CommentedMap"]:
                    method = dict(method)
                    method_name = list(method.keys())[0]
                    if not list(method.values())[0].__class__.__name__ == "NoneType":
                        method_args = dict(list(method.values())[0])
                    else:
                        method_args = {}
                elif method.__class__.__name__ == "str":
                    method_name = method
                    method_args = {}

                ## feedback
                if flags.execute:
                    print(method_name)

                ## check if method exists
                if hasattr(eval(step_name), method_name):
                    self.config_parsed_flattened[step_name].append(method_name)
                    pass
                elif self.flags.fix_names:
                    if method_name in settings._legacy_names[step_name]:
                        method_name_updated = settings._legacy_names[step_name][
                            method_name
                        ]
                        self.config_updated["processing_steps"][step_idx][step_name][
                            method_idx
                        ] = {method_name_updated: method_args}
                        method_name = method_name_updated
                        print("Fixed method name")
                else:
                    print(
                        "phenopype.{} has no function called {} - will attempt to look for similarly named functions - fix the config file!".format(
                            step_name, method_name
                        )
                    )

                # =============================================================================
                # METHOD / ANNOTATION
                # =============================================================================

                ## annotation params
                if method_name in settings._annotation_functions:

                    annotation_counter[settings._annotation_functions[method_name]] += 1

                    if "ANNOTATION" in method_args:
                        annotation_args = dict(method_args["ANNOTATION"])
                        del method_args["ANNOTATION"]
                    else:
                        annotation_args = {}
                        method_args = dict(method_args)

                    if not "type" in annotation_args:
                        annotation_args.update(
                            {"type": settings._annotation_functions[method_name]}
                        )
                    if not "id" in annotation_args:
                        annotation_args.update(
                            {
                                "id": string.ascii_lowercase[
                                    annotation_counter[
                                        settings._annotation_functions[method_name]
                                    ]
                                ]
                            }
                        )
                    if not "edit" in annotation_args:
                        annotation_args.update(
                            {
                                "edit": "overwrite"
                                if method_name
                                in [
                                    "detect_contour",
                                    "detect_shape",
                                    "compute_shape_features",
                                    "compute_texture_features",
                                    "skeletonize",
                                ]
                                else False
                            }
                        )

                    annotation_args = utils_lowlevel._yaml_flow_style(annotation_args)
                    method_args_updated = {"ANNOTATION": annotation_args}
                    method_args_updated.update(method_args)
                    self.config_updated["processing_steps"][step_idx][step_name][
                        method_idx
                    ] = {method_name: method_args_updated}
                else:
                    annotation_args = {}

                # =============================================================================
                # METHOD / EXECUTE
                # =============================================================================

                ## run method with error handling
                if flags.execute:

                    if not flags.feedback:
                        method_args["passive"] = True

                    try:

                        ## excecute
                        self.container.run(
                            fun=method_name,
                            fun_kwargs=method_args,
                            annotation_kwargs=annotation_args,
                            annotation_counter=annotation_counter,
                        )
                        ## feedback cleanup
                        _config.last_print_msg = ""

                    except Exception as ex:
                        if self.flags.debug:
                            raise
                        self.log.append(ex)
                        location = (
                            step_name
                            + "."
                            + method_name
                            + ": "
                            + str(ex.__class__.__name__)
                        )
                        print(location + " - " + str(ex))

                    ## check for pype-restart after config change
                    if _config.pype_restart:
                        print("BREAK")
                        return

        # =============================================================================
        # CONFIG-UPDATE; FEEDBACK; FINAL VISUALIZATION
        # =============================================================================

        if not self.config_updated == self.config:
            utils_lowlevel._save_yaml(self.config_updated, self.config_path)
            print("updating pype config file")

        if flags.execute:
            print(
                "\n\n------------+++ finished pype iteration +++--------------\n"
                "-------(End with Ctrl+Enter or re-run with Enter)--------\n\n"
            )

        if flags.visualize and flags.feedback:
            try:
                print("AUTOSHOW")
                if self.container.canvas.__class__.__name__ == "NoneType":
                    self.container.run(fun="select_canvas")
                    print("- autoselect canvas")

                self.gui = utils_lowlevel._GUI(self.container.canvas)
                self.flags.terminate = self.gui.flags.end_pype

            except Exception as ex:
                print("visualisation: " + str(ex.__class__.__name__) + " - " + str(ex))
        else:
            if flags.execute:
                self.flags.terminate = True
