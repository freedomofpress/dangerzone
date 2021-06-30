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

        self.details = QtWidgets.QLabel()
        self.details.setStyleSheet(
            "QLabel { background-color: #ffffff; font-size: 12px; padding: 10px; }"
        )
        self.details.setFont(self.gui_common.fixed_font)
        self.details.setAlignment(QtCore.Qt.AlignTop)

        self.details_scrollarea = QtWidgets.QScrollArea()
        self.details_scrollarea.setMinimumHeight(200)
        self.details_scrollarea.setWidgetResizable(True)
        self.details_scrollarea.setWidget(self.details)
        self.details_scrollarea.verticalScrollBar().rangeChanged.connect(
            self.scroll_to_bottom
        )

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addWidget(self.details_scrollarea)
        layout.addStretch()
        self.setLayout(layout)

    def vm_state_change(self, state):
        if state == self.vm.STATE_ON:
            self.vm_started.emit()

    def scroll_to_bottom(self, minimum, maximum):
        self.scrollarea.verticalScrollBar().setValue(maximum)
