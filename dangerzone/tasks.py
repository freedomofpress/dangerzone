import subprocess
import time
from PyQt5 import QtCore, QtWidgets, QtGui


class TaskBase(QtCore.QThread):
    thread_finished = QtCore.pyqtSignal()
    update_label = QtCore.pyqtSignal(str)
    update_details = QtCore.pyqtSignal(str)

    def __init__(self):
        super(TaskBase, self).__init__()

    def execute_podman(self, args, watch="stdout"):
        print(f"Executing: {' '.join(args)}")
        output = ""
        with subprocess.Popen(
            args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as p:
            if watch == "stdout":
                pipe = p.stdout
            else:
                pipe = p.stderr

            for line in pipe:
                output += line
                self.update_details.emit(output)

            output += p.stdout.read()
            self.update_details.emit(output)


class PullImageTask(TaskBase):
    def __init__(self, common):
        super(PullImageTask, self).__init__()
        self.common = common

    def run(self):
        self.update_label.emit("Pulling container image")
        self.update_details.emit("")
        args = ["podman", "pull", "ubuntu:18.04"]
        self.execute_podman(args, watch="stderr")
        self.thread_finished.emit()


class BuildContainerTask(TaskBase):
    def __init__(self, common):
        super(BuildContainerTask, self).__init__()
        self.common = common

    def run(self):
        containerfile = self.common.get_resource_path("Containerfile")
        self.update_label.emit("Building container")
        self.update_details.emit("")
        args = ["podman", "build", "-t", "dangerzone", "-f", containerfile]
        self.execute_podman(args)
        self.thread_finished.emit()
