preset1 = """
segmentation:
- blur:
    kernel_size: 15
- threshold:
    method: otsu
- morphology:
    operation: close
    shape: ellipse
    kernel_size: 3
    iterations: 10
- find_contours:
    retrieval: ccomp
    min_diameter: 0
    min_area: 0
measurement:
- colour:
    channels: [gray, rgb]
visualization:
- select_canvas:
    canvas: image
- show_contours:
    line_thickness: 2
    text_thickness: 1
    text_size: 1
    fill: 0.3
- show_mask:
    colour: blue
    line_thickness: 5
"""

preset2 = """
preprocessing:
- create_mask:
    label: mask1
segmentation:
- blur:
    kernel_size: 15
- threshold:
    method: otsu
- morphology:
    operation: close
    shape: ellipse
    kernel_size: 3
    iterations: 10
- find_contours:
    retrieval: ccomp
    min_diameter: 0
    min_area: 0
measurement:
- colour:
    channels: [gray, rgb]
visualization:
- select_canvas:
    canvas: image
- show_contours:
    line_thickness: 2
    text_thickness: 1
    text_size: 1
    fill: 0.3
- show_mask:
    colour: blue
    line_thickness: 5
export:
- save_results:
    overwrite: true
- save_canvas:
    resize: 0.5
    overwrite: true
"""


landmarking1 = """
preprocessing:
- create_mask
measurement:
- landmarks
- polylines
visualization:
- show_landmarks:
    point_size: 25
    point_col: green
    label_size: 3
    label_width: 5
- show_masks:
    colour: blue
    line_thickness: 5
- show_polylines:
    colour: blue
    line_thickness: 5
export:
- save_landmarks
- save_masks
- save_polylines
"""