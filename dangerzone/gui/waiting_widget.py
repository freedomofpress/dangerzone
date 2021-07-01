from PySide2 import QtCore, QtWidgets


class WaitingWidget(QtWidgets.QWidget):
    vm_started = QtCore.Signal()

    def __init__(self, gui_common, vm):
        super(WaitingWidget, self).__init__()
        self.gui_common = gui_common
        self.vm = vm

        self.vm.vm_state_change.connect(self.vm_state_change)

        self.label = QtWidgets.QLabel(
            "Waiting for the Dangerzone virtual machine to start..."
        )
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("QLabel { font-size: 20px; }")

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addStretch()
        self.setLayout(layout)

    def vm_state_change(self, state):
        if state == self.vm.STATE_ON:
            self.vm_started.emit()
        elif state == self.vm.STATE_FAIL:
            self.label.setText("Dangerzone virtual machine failed to start :(")
