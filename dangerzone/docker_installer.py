import os
import stat
import requests
import tempfile
from PyQt5 import QtCore, QtGui, QtWidgets


def is_docker_installed(common):
    # Soes the docker binary exist?
    if os.path.isdir("/Applications/Docker.app") and os.path.exists(
        common.container_runtime
    ):
        # Is it executable?
        st = os.stat(common.container_runtime)
        return bool(st.st_mode & stat.S_IXOTH)
    return False


class DockerInstaller(QtWidgets.QDialog):
    def __init__(self, common):
        super(DockerInstaller, self).__init__()
        self.common = common

        self.setWindowTitle("dangerzone")
        self.setWindowIcon(QtGui.QIcon(self.common.get_resource_path("logo.png")))

        label = QtWidgets.QLabel("Dangerzone for macOS requires Docker")
        label.setStyleSheet("QLabel { font-weight: bold; }")

        self.task_label = QtWidgets.QLabel()

        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)

        self.install_button = QtWidgets.QPushButton("Install Docker")
        self.install_button.setStyleSheet("QPushButton { font-weight: bold; }")
        self.install_button.clicked.connect(self.install_clicked)
        self.install_button.hide()
        self.launch_button = QtWidgets.QPushButton("Launch Docker")
        self.launch_button.setStyleSheet("QPushButton { font-weight: bold; }")
        self.launch_button.clicked.connect(self.launch_clicked)
        self.launch_button.hide()
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel_clicked)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.install_button)
        buttons_layout.addWidget(self.launch_button)
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Threads
        self.download_t = None

    def cancel_clicked(self):
        if self.download_t:
            self.download_t.terminate()
        self.reject()

    def install_clicked(self):
        print("Install clicked")

    def launch_clicked(self):
        print("Launch clicked")

    def update_progress(self, value, maximum):
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)

    def download_finished(self):
        self.task_label.setText("Finished downloading Docker")
        self.download_t = None
        self.install_button.show()

    def download_failed(self, status_code):
        print(f"Download failed: status code {status_code}")
        self.download_t = None

    def download(self):
        self.task_label.setText("Downloading Docker")
        self.download_t = Downloader()
        self.download_t.download_finished.connect(self.download_finished)
        self.download_t.download_failed.connect(self.download_failed)
        self.download_t.update_progress.connect(self.update_progress)
        self.download_t.start()

    def install(self):
        pass

    def launch(self):
        self.download()
        return self.exec_() == QtWidgets.QDialog.Accepted


class Downloader(QtCore.QThread):
    download_finished = QtCore.pyqtSignal()
    download_failed = QtCore.pyqtSignal(int)
    update_progress = QtCore.pyqtSignal(int, int)

    def __init__(self):
        super(Downloader, self).__init__()
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="/tmp/dangerzone-docker-")
        self.dmg_filename = os.path.join(self.tmp_dir.name, "Docker.dmg")

    def run(self):
        print(f"Downloading docker to {self.dmg_filename}")
        with requests.get(
            "https://download.docker.com/mac/stable/Docker.dmg", stream=True
        ) as r:
            if r.status_code != 200:
                self.download_failed.emit(r.status_code)
                return
            total_bytes = int(r.headers.get("content-length"))
            downloaded_bytes = 0

            with open(self.dmg_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        downloaded_bytes += f.write(chunk)

                        self.update_progress.emit(downloaded_bytes, total_bytes)

        self.download_finished.emit()

