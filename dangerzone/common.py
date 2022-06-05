class Common(object):
    """
    The Common class is a singleton of shared functionality throughout an open dangerzone window
    """

    def __init__(self):
        # Name of input and out files
        self.input_filename = None
        self.output_filename = None
