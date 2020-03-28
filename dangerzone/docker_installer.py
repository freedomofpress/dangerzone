import os
import stat
import requests
import tempfile
import subprocess
import shutil
import time
import platform
from PyQt5 import QtCore, QtGui, QtWidgets

from .container import container_runtime


class AuthorizationFailed(Exception):
    pass


def is_docker_installed(global_common):
    if platform.system() == "Darwin":
        # Does the docker binary exist?
        if os.path.isdir("/Applications/Docker.app") and os.path.exists(
            container_runtime
        ):
            # Is it executable?
            st = os.stat(container_runtime)
            return bool(st.st_mode & stat.S_IXOTH)

    if platform.system() == "Windows":
        return os.path.exists(container_runtime)

    return False


def is_docker_ready(global_common):
    # Run `docker image ls` without an error
    with global_common.exec_dangerzone_container(["image_ls"]) as p:
        p.communicate()

        # The user canceled, or permission denied
        if p.returncode == 126 or p.returncode == 127:
            raise AuthorizationFailed

        # Return true if it succeeds
        if p.returncode == 0:
            return True
        else:
            return False


def launch_docker_windows(global_common):
    docker_desktop_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
    subprocess.Popen(
        [docker_desktop_path], startupinfo=global_common.get_subprocess_startupinfo()
    )


class DockerInstaller(QtWidgets.QDialog):
    def __init__(self, global_common):
        super(DockerInstaller, self).__init__()
        self.global_common = global_common

        self.setWindowTitle("dangerzone")
        self.setWindowIcon(self.global_common.get_window_icon())
        self.setMinimumHeight(170)

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

        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)

        self.open_finder_button = QtWidgets.QPushButton()
        if platform.system() == "Darwin":
            self.open_finder_button.setText("Show in Finder")
        else:
            self.open_finder_button.setText("Show in Explorer")
        self.open_finder_button.setStyleSheet("QPushButton { font-weight: bold; }")
        self.open_finder_button.clicked.connect(self.open_finder_clicked)
        self.open_finder_button.hide()

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_clicked)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.open_finder_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons_layout)
        layout.addStretch()
        self.setLayout(layout)

        if platform.system() == "Darwin":
            self.installer_filename = os.path.join(
                os.path.expanduser("~/Downloads"), "Docker.dmg"
            )
        else:
            self.installer_filename = os.path.join(
                os.path.expanduser("~\\Downloads"), "Docker for Windows Installer.exe"
            )

        # Threads
        self.download_t = None

    def update_progress(self, value, maximum):
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)

    def update_task_label(self, s):
        self.task_label.setText(s)

    def download_finished(self):
        self.task_label.setText(
            "Finished downloading Docker. Install it, make sure it's running, and then open Dangerzone again."
        )
        self.download_t = None
        self.progress.hide()
        self.cancel_button.hide()

        self.open_finder_path = self.installer_filename
        self.open_finder_button.show()

    def download_failed(self, status_code):
        print(f"Download failed: status code {status_code}")
        self.download_t = None

    def download(self):
        self.task_label.setText("Downloading Docker")

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.start_download)
        self.timer.setSingleShot(True)
        self.timer.start(10)

    def start_download(self):
        self.download_t = Downloader(self.installer_filename)
        self.download_t.download_finished.connect(self.download_finished)
        self.download_t.download_failed.connect(self.download_failed)
        self.download_t.update_progress.connect(self.update_progress)
        self.download_t.start()

    def cancel_clicked(self):
        self.reject()

        if self.download_t:
            self.download_t.quit()
            try:
                os.remove(self.installer_filename)
            except:
                pass

    def open_finder_clicked(self):
        if platform.system() == "Darwin":
            subprocess.call(["open", "-R", self.open_finder_path])
        else:
            subprocess.Popen(
                f'explorer.exe /select,"{self.open_finder_path}"', shell=True
            )
        self.accept()

    def start(self):
        if platform.system() == "Darwin":
            docker_app_path = "/Applications/Docker.app"
        else:
            docker_app_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"

        if not os.path.exists(docker_app_path):
            self.download()
        else:
            self.task_label.setText(
                "Docker is installed, but you must launch it first. Open Docker, make sure it's running, and then open Dangerzone again."
            )
            self.progress.hide()
            self.cancel_button.hide()

            self.open_finder_path = docker_app_path
            self.open_finder_button.show()

        return self.exec_() == QtWidgets.QDialog.Accepted


class Downloader(QtCore.QThread):
    download_finished = QtCore.pyqtSignal()
    download_failed = QtCore.pyqtSignal(int)
    update_progress = QtCore.pyqtSignal(int, int)

    def __init__(self, installer_filename):
        super(Downloader, self).__init__()
        self.installer_filename = installer_filename

        if platform.system() == "Darwin":
            self.installer_url = "https://download.docker.com/mac/stable/Docker.dmg"
        elif platform.system() == "Windows":
            self.installer_url = "https://download.docker.com/win/stable/Docker%20for%20Windows%20Installer.exe"

    def run(self):
        print(f"Downloading docker to {self.installer_filename}")
        with requests.get(self.installer_url, stream=True) as r:
            if r.status_code != 200:
                self.download_failed.emit(r.status_code)
                return
            total_bytes = int(r.headers.get("content-length"))
            downloaded_bytes = 0

            with open(self.installer_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        downloaded_bytes += f.write(chunk)

                        self.update_progress.emit(downloaded_bytes, total_bytes)

        self.download_finished.emit()
