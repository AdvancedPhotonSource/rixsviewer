# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rixsviewer.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenu, QMenuBar, QProgressBar,
    QPushButton, QSizePolicy, QSlider, QSpacerItem,
    QSpinBox, QSplitter, QStatusBar, QTabWidget,
    QTableView, QToolButton, QWidget)

from pyqtgraph import GraphicsLayoutWidget
from pyqtgraph.parametertree import ParameterTree

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1570, 867)
        self.actionLoad_Spec_file = QAction(MainWindow)
        self.actionLoad_Spec_file.setObjectName(u"actionLoad_Spec_file")
        self.actionSet_Tif_folder = QAction(MainWindow)
        self.actionSet_Tif_folder.setObjectName(u"actionSet_Tif_folder")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_11 = QGridLayout(self.centralwidget)
        self.gridLayout_11.setObjectName(u"gridLayout_11")
        self.splitter_4 = QSplitter(self.centralwidget)
        self.splitter_4.setObjectName(u"splitter_4")
        self.splitter_4.setOrientation(Qt.Orientation.Horizontal)
        self.splitter_2 = QSplitter(self.splitter_4)
        self.splitter_2.setObjectName(u"splitter_2")
        self.splitter_2.setOrientation(Qt.Orientation.Vertical)
        self.groupBox = QGroupBox(self.splitter_2)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMaximumSize(QSize(16777215, 16777215))
        self.gridLayout = QGridLayout(self.groupBox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.tableView_scan = QTableView(self.groupBox)
        self.tableView_scan.setObjectName(u"tableView_scan")
        sizePolicy.setHeightForWidth(self.tableView_scan.sizePolicy().hasHeightForWidth())
        self.tableView_scan.setSizePolicy(sizePolicy)
        self.tableView_scan.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableView_scan.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.gridLayout.addWidget(self.tableView_scan, 3, 0, 1, 3)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.pushButton_load_scan = QPushButton(self.groupBox)
        self.pushButton_load_scan.setObjectName(u"pushButton_load_scan")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.pushButton_load_scan.sizePolicy().hasHeightForWidth())
        self.pushButton_load_scan.setSizePolicy(sizePolicy1)
        self.pushButton_load_scan.setMinimumSize(QSize(30, 0))
        self.pushButton_load_scan.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_2.addWidget(self.pushButton_load_scan)

        self.checkBox_autoupdate = QCheckBox(self.groupBox)
        self.checkBox_autoupdate.setObjectName(u"checkBox_autoupdate")

        self.horizontalLayout_2.addWidget(self.checkBox_autoupdate)


        self.gridLayout.addLayout(self.horizontalLayout_2, 2, 0, 1, 3)

        self.toolButton_set_tifffolder = QToolButton(self.groupBox)
        self.toolButton_set_tifffolder.setObjectName(u"toolButton_set_tifffolder")

        self.gridLayout.addWidget(self.toolButton_set_tifffolder, 1, 2, 1, 1)

        self.lineEdit_specfilename = QLineEdit(self.groupBox)
        self.lineEdit_specfilename.setObjectName(u"lineEdit_specfilename")
        sizePolicy1.setHeightForWidth(self.lineEdit_specfilename.sizePolicy().hasHeightForWidth())
        self.lineEdit_specfilename.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.lineEdit_specfilename, 0, 1, 1, 1)

        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.lineEdit = QLineEdit(self.groupBox)
        self.lineEdit.setObjectName(u"lineEdit")
        sizePolicy1.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.lineEdit, 1, 1, 1, 1)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")
        sizePolicy2.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.toolButton_load_specfile = QToolButton(self.groupBox)
        self.toolButton_load_specfile.setObjectName(u"toolButton_load_specfile")

        self.gridLayout.addWidget(self.toolButton_load_specfile, 0, 2, 1, 1)

        self.splitter_2.addWidget(self.groupBox)
        self.groupBox_2 = QGroupBox(self.splitter_2)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy3)
        self.groupBox_2.setMaximumSize(QSize(16777215, 16777215))
        self.gridLayout_2 = QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.tableView_image = QTableView(self.groupBox_2)
        self.tableView_image.setObjectName(u"tableView_image")
        sizePolicy.setHeightForWidth(self.tableView_image.sizePolicy().hasHeightForWidth())
        self.tableView_image.setSizePolicy(sizePolicy)

        self.gridLayout_2.addWidget(self.tableView_image, 0, 0, 1, 1)

        self.splitter_2.addWidget(self.groupBox_2)
        self.splitter_4.addWidget(self.splitter_2)
        self.splitter_3 = QSplitter(self.splitter_4)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Orientation.Vertical)
        self.splitter = QSplitter(self.splitter_3)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.groupBox_2d_scattering = QGroupBox(self.splitter)
        self.groupBox_2d_scattering.setObjectName(u"groupBox_2d_scattering")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(2)
        sizePolicy4.setVerticalStretch(2)
        sizePolicy4.setHeightForWidth(self.groupBox_2d_scattering.sizePolicy().hasHeightForWidth())
        self.groupBox_2d_scattering.setSizePolicy(sizePolicy4)
        self.gridLayout_3 = QGridLayout(self.groupBox_2d_scattering)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.widget_img = GraphicsLayoutWidget(self.groupBox_2d_scattering)
        self.widget_img.setObjectName(u"widget_img")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(3)
        sizePolicy5.setHeightForWidth(self.widget_img.sizePolicy().hasHeightForWidth())
        self.widget_img.setSizePolicy(sizePolicy5)

        self.gridLayout_3.addWidget(self.widget_img, 1, 0, 1, 5)

        self.horizontalSlider_frame_index = QSlider(self.groupBox_2d_scattering)
        self.horizontalSlider_frame_index.setObjectName(u"horizontalSlider_frame_index")
        self.horizontalSlider_frame_index.setOrientation(Qt.Orientation.Horizontal)

        self.gridLayout_3.addWidget(self.horizontalSlider_frame_index, 0, 4, 1, 1)

        self.doubleSpinBox_percentile_cutoff = QDoubleSpinBox(self.groupBox_2d_scattering)
        self.doubleSpinBox_percentile_cutoff.setObjectName(u"doubleSpinBox_percentile_cutoff")
        self.doubleSpinBox_percentile_cutoff.setMinimum(50.000000000000000)
        self.doubleSpinBox_percentile_cutoff.setMaximum(100.000000000000000)
        self.doubleSpinBox_percentile_cutoff.setSingleStep(0.100000000000000)
        self.doubleSpinBox_percentile_cutoff.setValue(99.000000000000000)

        self.gridLayout_3.addWidget(self.doubleSpinBox_percentile_cutoff, 0, 1, 1, 1)

        self.label_6 = QLabel(self.groupBox_2d_scattering)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_3.addWidget(self.label_6, 0, 3, 1, 1)

        self.label_2 = QLabel(self.groupBox_2d_scattering)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_3.addWidget(self.label_2, 0, 0, 1, 1)

        self.line_6 = QFrame(self.groupBox_2d_scattering)
        self.line_6.setObjectName(u"line_6")
        self.line_6.setFrameShape(QFrame.Shape.VLine)
        self.line_6.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_3.addWidget(self.line_6, 0, 2, 1, 1)

        self.splitter.addWidget(self.groupBox_2d_scattering)
        self.groupBox_4 = QGroupBox(self.splitter)
        self.groupBox_4.setObjectName(u"groupBox_4")
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(2)
        sizePolicy6.setHeightForWidth(self.groupBox_4.sizePolicy().hasHeightForWidth())
        self.groupBox_4.setSizePolicy(sizePolicy6)
        self.groupBox_4.setMinimumSize(QSize(0, 300))
        self.gridLayout_8 = QGridLayout(self.groupBox_4)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.gridLayout_8.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_5 = QGridLayout()
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.widget_ptree = ParameterTree(self.groupBox_4)
        self.widget_ptree.setObjectName(u"widget_ptree")
        sizePolicy.setHeightForWidth(self.widget_ptree.sizePolicy().hasHeightForWidth())
        self.widget_ptree.setSizePolicy(sizePolicy)
        self.widget_ptree.setMinimumSize(QSize(100, 200))

        self.gridLayout_5.addWidget(self.widget_ptree, 0, 0, 1, 4)

        self.label_4 = QLabel(self.groupBox_4)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_5.addWidget(self.label_4, 1, 0, 1, 1)

        self.comboBox_metasource = QComboBox(self.groupBox_4)
        self.comboBox_metasource.addItem("")
        self.comboBox_metasource.addItem("")
        self.comboBox_metasource.addItem("")
        self.comboBox_metasource.setObjectName(u"comboBox_metasource")

        self.gridLayout_5.addWidget(self.comboBox_metasource, 1, 1, 1, 1)

        self.pushButton_4 = QPushButton(self.groupBox_4)
        self.pushButton_4.setObjectName(u"pushButton_4")

        self.gridLayout_5.addWidget(self.pushButton_4, 1, 2, 1, 1)

        self.pushButton_3 = QPushButton(self.groupBox_4)
        self.pushButton_3.setObjectName(u"pushButton_3")

        self.gridLayout_5.addWidget(self.pushButton_3, 1, 3, 1, 1)


        self.gridLayout_8.addLayout(self.gridLayout_5, 0, 0, 2, 1)

        self.splitter.addWidget(self.groupBox_4)
        self.splitter_3.addWidget(self.splitter)
        self.tabWidget = QTabWidget(self.splitter_3)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_4 = QGridLayout(self.tab_2)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(1, 1, 1, 1)
        self.widget_binhdl = GraphicsLayoutWidget(self.tab_2)
        self.widget_binhdl.setObjectName(u"widget_binhdl")
        sizePolicy5.setHeightForWidth(self.widget_binhdl.sizePolicy().hasHeightForWidth())
        self.widget_binhdl.setSizePolicy(sizePolicy5)

        self.gridLayout_4.addWidget(self.widget_binhdl, 0, 0, 1, 1)

        self.groupBox_6 = QGroupBox(self.tab_2)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.gridLayout_7 = QGridLayout(self.groupBox_6)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.gridLayout_7.setContentsMargins(1, 1, 1, 1)
        self.line = QFrame(self.groupBox_6)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.VLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line, 0, 3, 1, 1)

        self.line_3 = QFrame(self.groupBox_6)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.VLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_3, 0, 12, 1, 1)

        self.label_7 = QLabel(self.groupBox_6)
        self.label_7.setObjectName(u"label_7")
        sizePolicy2.setHeightForWidth(self.label_7.sizePolicy().hasHeightForWidth())
        self.label_7.setSizePolicy(sizePolicy2)

        self.gridLayout_7.addWidget(self.label_7, 0, 8, 1, 1)

        self.label_energy_interval = QLabel(self.groupBox_6)
        self.label_energy_interval.setObjectName(u"label_energy_interval")
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy7.setHorizontalStretch(0)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.label_energy_interval.sizePolicy().hasHeightForWidth())
        self.label_energy_interval.setSizePolicy(sizePolicy7)

        self.gridLayout_7.addWidget(self.label_energy_interval, 0, 15, 1, 1)

        self.comboBox = QComboBox(self.groupBox_6)
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.setObjectName(u"comboBox")

        self.gridLayout_7.addWidget(self.comboBox, 0, 9, 1, 1)

        self.label_10 = QLabel(self.groupBox_6)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_7.addWidget(self.label_10, 0, 17, 1, 1)

        self.pushButton_process = QPushButton(self.groupBox_6)
        self.pushButton_process.setObjectName(u"pushButton_process")

        self.gridLayout_7.addWidget(self.pushButton_process, 0, 23, 1, 1)

        self.pushButton_save = QPushButton(self.groupBox_6)
        self.pushButton_save.setObjectName(u"pushButton_save")

        self.gridLayout_7.addWidget(self.pushButton_save, 0, 24, 1, 1)

        self.checkBox_show_rawdata = QCheckBox(self.groupBox_6)
        self.checkBox_show_rawdata.setObjectName(u"checkBox_show_rawdata")

        self.gridLayout_7.addWidget(self.checkBox_show_rawdata, 0, 11, 1, 1)

        self.label_11 = QLabel(self.groupBox_6)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_7.addWidget(self.label_11, 0, 20, 1, 1)

        self.label_binpixel = QLabel(self.groupBox_6)
        self.label_binpixel.setObjectName(u"label_binpixel")
        sizePolicy2.setHeightForWidth(self.label_binpixel.sizePolicy().hasHeightForWidth())
        self.label_binpixel.setSizePolicy(sizePolicy2)

        self.gridLayout_7.addWidget(self.label_binpixel, 0, 13, 1, 1)

        self.spinBox_binpixel = QSpinBox(self.groupBox_6)
        self.spinBox_binpixel.setObjectName(u"spinBox_binpixel")
        sizePolicy8 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(0)
        sizePolicy8.setHeightForWidth(self.spinBox_binpixel.sizePolicy().hasHeightForWidth())
        self.spinBox_binpixel.setSizePolicy(sizePolicy8)
        self.spinBox_binpixel.setMinimum(1)

        self.gridLayout_7.addWidget(self.spinBox_binpixel, 0, 14, 1, 1)

        self.progressBar_process = QProgressBar(self.groupBox_6)
        self.progressBar_process.setObjectName(u"progressBar_process")
        sizePolicy9 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy9.setHorizontalStretch(2)
        sizePolicy9.setVerticalStretch(0)
        sizePolicy9.setHeightForWidth(self.progressBar_process.sizePolicy().hasHeightForWidth())
        self.progressBar_process.setSizePolicy(sizePolicy9)
        self.progressBar_process.setValue(0)

        self.gridLayout_7.addWidget(self.progressBar_process, 0, 18, 1, 1)

        self.line_2 = QFrame(self.groupBox_6)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.VLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_2, 0, 10, 1, 1)

        self.line_9 = QFrame(self.groupBox_6)
        self.line_9.setObjectName(u"line_9")
        self.line_9.setFrameShape(QFrame.Shape.VLine)
        self.line_9.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_9, 0, 22, 1, 1)

        self.comboBox_plottarget = QComboBox(self.groupBox_6)
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.addItem("")
        self.comboBox_plottarget.setObjectName(u"comboBox_plottarget")
        sizePolicy10 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy10.setHorizontalStretch(1)
        sizePolicy10.setVerticalStretch(0)
        sizePolicy10.setHeightForWidth(self.comboBox_plottarget.sizePolicy().hasHeightForWidth())
        self.comboBox_plottarget.setSizePolicy(sizePolicy10)

        self.gridLayout_7.addWidget(self.comboBox_plottarget, 0, 21, 1, 1)

        self.line_8 = QFrame(self.groupBox_6)
        self.line_8.setObjectName(u"line_8")
        self.line_8.setFrameShape(QFrame.Shape.VLine)
        self.line_8.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_8, 0, 16, 1, 1)

        self.line_10 = QFrame(self.groupBox_6)
        self.line_10.setObjectName(u"line_10")
        self.line_10.setFrameShape(QFrame.Shape.VLine)
        self.line_10.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_10, 0, 19, 1, 1)


        self.gridLayout_4.addWidget(self.groupBox_6, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tab_2, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout_10 = QGridLayout(self.tab)
        self.gridLayout_10.setObjectName(u"gridLayout_10")
        self.gridLayout_10.setContentsMargins(1, 1, 1, 1)
        self.widget_calibhdl = GraphicsLayoutWidget(self.tab)
        self.widget_calibhdl.setObjectName(u"widget_calibhdl")
        sizePolicy5.setHeightForWidth(self.widget_calibhdl.sizePolicy().hasHeightForWidth())
        self.widget_calibhdl.setSizePolicy(sizePolicy5)

        self.gridLayout_10.addWidget(self.widget_calibhdl, 0, 0, 1, 1)

        self.groupBox_7 = QGroupBox(self.tab)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.gridLayout_9 = QGridLayout(self.groupBox_7)
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.gridLayout_9.setContentsMargins(1, 1, 1, 1)
        self.comboBox_fit_target = QComboBox(self.groupBox_7)
        self.comboBox_fit_target.addItem("")
        self.comboBox_fit_target.addItem("")
        self.comboBox_fit_target.setObjectName(u"comboBox_fit_target")

        self.gridLayout_9.addWidget(self.comboBox_fit_target, 0, 1, 1, 1)

        self.progressBar_calibrate = QProgressBar(self.groupBox_7)
        self.progressBar_calibrate.setObjectName(u"progressBar_calibrate")
        self.progressBar_calibrate.setValue(0)

        self.gridLayout_9.addWidget(self.progressBar_calibrate, 0, 9, 1, 1)

        self.label_9 = QLabel(self.groupBox_7)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_9.addWidget(self.label_9, 0, 8, 1, 1)

        self.label_8 = QLabel(self.groupBox_7)
        self.label_8.setObjectName(u"label_8")
        sizePolicy2.setHeightForWidth(self.label_8.sizePolicy().hasHeightForWidth())
        self.label_8.setSizePolicy(sizePolicy2)

        self.gridLayout_9.addWidget(self.label_8, 0, 0, 1, 1)

        self.comboBox_center_method = QComboBox(self.groupBox_7)
        self.comboBox_center_method.addItem("")
        self.comboBox_center_method.addItem("")
        self.comboBox_center_method.addItem("")
        self.comboBox_center_method.setObjectName(u"comboBox_center_method")

        self.gridLayout_9.addWidget(self.comboBox_center_method, 0, 4, 1, 1)

        self.pushButton_fit_pixel_size = QPushButton(self.groupBox_7)
        self.pushButton_fit_pixel_size.setObjectName(u"pushButton_fit_pixel_size")

        self.gridLayout_9.addWidget(self.pushButton_fit_pixel_size, 0, 10, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_9.addItem(self.horizontalSpacer, 0, 6, 1, 1)

        self.line_5 = QFrame(self.groupBox_7)
        self.line_5.setObjectName(u"line_5")
        self.line_5.setFrameShape(QFrame.Shape.VLine)
        self.line_5.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_9.addWidget(self.line_5, 0, 5, 1, 1)

        self.label_5 = QLabel(self.groupBox_7)
        self.label_5.setObjectName(u"label_5")
        sizePolicy2.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy2)

        self.gridLayout_9.addWidget(self.label_5, 0, 3, 1, 1)

        self.line_4 = QFrame(self.groupBox_7)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setFrameShape(QFrame.Shape.VLine)
        self.line_4.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_9.addWidget(self.line_4, 0, 2, 1, 1)

        self.line_7 = QFrame(self.groupBox_7)
        self.line_7.setObjectName(u"line_7")
        self.line_7.setFrameShape(QFrame.Shape.VLine)
        self.line_7.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_9.addWidget(self.line_7, 0, 7, 1, 1)


        self.gridLayout_10.addWidget(self.groupBox_7, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tab, "")
        self.splitter_3.addWidget(self.tabWidget)
        self.splitter_4.addWidget(self.splitter_3)

        self.gridLayout_11.addWidget(self.splitter_4, 0, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1570, 23))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menuFile.addAction(self.actionLoad_Spec_file)
        self.menuFile.addAction(self.actionSet_Tif_folder)

        self.retranslateUi(MainWindow)
        self.checkBox_autoupdate.toggled.connect(self.pushButton_fit_pixel_size.setDisabled)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"RIXSviewer", None))
        self.actionLoad_Spec_file.setText(QCoreApplication.translate("MainWindow", u"Load Spec file", None))
        self.actionSet_Tif_folder.setText(QCoreApplication.translate("MainWindow", u"Set Tif folder", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Scan List", None))
        self.pushButton_load_scan.setText(QCoreApplication.translate("MainWindow", u"load", None))
        self.checkBox_autoupdate.setText(QCoreApplication.translate("MainWindow", u"AutoUpdate", None))
        self.toolButton_set_tifffolder.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"SpecFile:", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"TiffFolder:", None))
        self.toolButton_load_specfile.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Single Scan", None))
        self.groupBox_2d_scattering.setTitle(QCoreApplication.translate("MainWindow", u"2D Images", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Frame", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Percentile Enhancement", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("MainWindow", u"Metadata", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Source:", None))
        self.comboBox_metasource.setItemText(0, QCoreApplication.translate("MainWindow", u"SpecFile", None))
        self.comboBox_metasource.setItemText(1, QCoreApplication.translate("MainWindow", u"PV", None))
        self.comboBox_metasource.setItemText(2, QCoreApplication.translate("MainWindow", u"USER", None))

        self.pushButton_4.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.pushButton_3.setText(QCoreApplication.translate("MainWindow", u"Load", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("MainWindow", u"Process", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Error Model:", None))
        self.label_energy_interval.setText(QCoreApplication.translate("MainWindow", u"Energy Interval:", None))
        self.comboBox.setItemText(0, QCoreApplication.translate("MainWindow", u"poisson", None))
        self.comboBox.setItemText(1, QCoreApplication.translate("MainWindow", u"gaussian", None))
        self.comboBox.setItemText(2, QCoreApplication.translate("MainWindow", u"none", None))

        self.label_10.setText(QCoreApplication.translate("MainWindow", u"Progress:", None))
        self.pushButton_process.setText(QCoreApplication.translate("MainWindow", u"Apply", None))
        self.pushButton_save.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        self.checkBox_show_rawdata.setText(QCoreApplication.translate("MainWindow", u"Show RawData", None))
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"Plot", None))
        self.label_binpixel.setText(QCoreApplication.translate("MainWindow", u"Bin Pixel:", None))
        self.comboBox_plottarget.setItemText(0, QCoreApplication.translate("MainWindow", u"intensity_norm", None))
        self.comboBox_plottarget.setItemText(1, QCoreApplication.translate("MainWindow", u"intensity_raw", None))
        self.comboBox_plottarget.setItemText(2, QCoreApplication.translate("MainWindow", u"pseudo_cps", None))
        self.comboBox_plottarget.setItemText(3, QCoreApplication.translate("MainWindow", u"i0", None))
        self.comboBox_plottarget.setItemText(4, QCoreApplication.translate("MainWindow", u"i2", None))
        self.comboBox_plottarget.setItemText(5, QCoreApplication.translate("MainWindow", u"mmepin1", None))
        self.comboBox_plottarget.setItemText(6, QCoreApplication.translate("MainWindow", u"mmepin2", None))

        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"Process", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.comboBox_fit_target.setItemText(0, QCoreApplication.translate("MainWindow", u"DeltaD", None))
        self.comboBox_fit_target.setItemText(1, QCoreApplication.translate("MainWindow", u"TiltAngle", None))

        self.label_9.setText(QCoreApplication.translate("MainWindow", u"Progress:", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"OptimizeTarget:", None))
        self.comboBox_center_method.setItemText(0, QCoreApplication.translate("MainWindow", u"gaussian", None))
        self.comboBox_center_method.setItemText(1, QCoreApplication.translate("MainWindow", u"centroid", None))
        self.comboBox_center_method.setItemText(2, QCoreApplication.translate("MainWindow", u"argmax", None))

        self.pushButton_fit_pixel_size.setText(QCoreApplication.translate("MainWindow", u"Calibrate", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Center Model:", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"Calibration", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
    # retranslateUi

