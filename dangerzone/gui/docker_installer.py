import os
import subprocess
import shutil
import platform
from PySide2 import QtCore, QtWidgets


class AuthorizationFailed(Exception):
    pass


container_runtime = shutil.which("docker")    


def is_docker_installed():
    return container_runtime is not None


def is_docker_ready(global_common):
    # Run `docker image ls` without an error
    with subprocess.Popen([container_runtime, "image", "ls"]) as p:
        outs, errs = p.communicate()

        # The user canceled, or permission denied
        if p.returncode == 126 or p.returncode == 127:
            raise AuthorizationFailed

        # Return true if it succeeds
        if p.returncode == 0:
            return True
        else:
            print(outs)
            print(errs)
            return False


def launch_docker_windows(global_common):
    docker_desktop_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
    subprocess.Popen(
        [docker_desktop_path], startupinfo=global_common.get_subprocess_startupinfo()
    )


class DockerInstaller(QtWidgets.QDialog):
    def __init__(self, gui_common):
        super(DockerInstaller, self).__init__()

        self.setWindowTitle("Dangerzone")
        self.setWindowIcon(gui_common.get_window_icon())
        # self.setMinimumHeight(170)

        label = QtWidgets.QLabel()
        if platform.system() == "Darwin":
            label.setText("Dangerzone for macOS requires Docker")
        elif platform.system() == "Windows":
            label.setText("Dangerzone for Windows requires Docker")
        label.setStyleSheet("QLabel { font-weight: bold; }")
        label.setAlignment(QtCore.Qt.AlignCenter)

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setWordWrap(True)
        self.task_label.setOpenExternalLinks(True)

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.ok_clicked)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.task_label)
        layout.addLayout(buttons_layout)
        layout.addStretch()
        self.setLayout(layout)

        if platform.system() == "Darwin":
            self.docker_path = "/Applications/Docker.app/Contents/Resources/bin/docker"
        elif platform.system() == "Windows":
            self.docker_path = shutil.which("docker.exe")

    def ok_clicked(self):
        self.accept()

    def start(self):
        if not os.path.exists(self.docker_path):
            self.task_label.setText(
                "<a href='https://www.docker.com/products/docker-desktop'>Download Docker Desktop</a>, install it, and then run Dangerzone again."
            )
            self.task_label.setTextFormat(QtCore.Qt.RichText)
        else:
            self.task_label.setText(
                "Docker Desktop is installed, but you must launch it first. Open Docker, make sure it's running, and then open Dangerzone again."
            )

        return self.exec_() == QtWidgets.QDialog.Accepted
