# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rixsviewer.ui'
##
## Created by: Qt User Interface Compiler version 6.9.3
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMenu, QMenuBar,
    QPushButton, QSizePolicy, QSpinBox, QStatusBar,
    QTableView, QToolButton, QWidget)

from pyqtgraph import (GraphicsLayoutWidget, ImageView)
from pyqtgraph.parametertree import ParameterTree

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1127, 855)
        self.actionLoad_Spec_file = QAction(MainWindow)
        self.actionLoad_Spec_file.setObjectName(u"actionLoad_Spec_file")
        self.actionSet_Tif_folder = QAction(MainWindow)
        self.actionSet_Tif_folder.setObjectName(u"actionSet_Tif_folder")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_9 = QGridLayout(self.centralwidget)
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.groupBox = QGroupBox(self.centralwidget)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(2)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMaximumSize(QSize(320, 16777215))
        self.gridLayout_6 = QGridLayout(self.groupBox)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.gridLayout_6.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_6.addWidget(self.label_2, 2, 0, 1, 1)

        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_6.addWidget(self.label_5, 2, 2, 1, 1)

        self.spinBox = QSpinBox(self.groupBox)
        self.spinBox.setObjectName(u"spinBox")

        self.gridLayout_6.addWidget(self.spinBox, 2, 1, 1, 1)

        self.comboBox_2 = QComboBox(self.groupBox)
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.setObjectName(u"comboBox_2")

        self.gridLayout_6.addWidget(self.comboBox_2, 2, 3, 1, 1)

        self.tableView_scan = QTableView(self.groupBox)
        self.tableView_scan.setObjectName(u"tableView_scan")

        self.gridLayout_6.addWidget(self.tableView_scan, 1, 0, 1, 4)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.lineEdit_specfilename = QLineEdit(self.groupBox)
        self.lineEdit_specfilename.setObjectName(u"lineEdit_specfilename")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.lineEdit_specfilename.sizePolicy().hasHeightForWidth())
        self.lineEdit_specfilename.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.lineEdit_specfilename, 0, 1, 1, 1)

        self.toolButton_load_specfile = QToolButton(self.groupBox)
        self.toolButton_load_specfile.setObjectName(u"toolButton_load_specfile")

        self.gridLayout.addWidget(self.toolButton_load_specfile, 0, 2, 1, 1)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")
        sizePolicy1.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.lineEdit = QLineEdit(self.groupBox)
        self.lineEdit.setObjectName(u"lineEdit")
        sizePolicy2.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.lineEdit, 1, 1, 1, 1)

        self.toolButton_set_tifffolder = QToolButton(self.groupBox)
        self.toolButton_set_tifffolder.setObjectName(u"toolButton_set_tifffolder")

        self.gridLayout.addWidget(self.toolButton_set_tifffolder, 1, 2, 1, 1)


        self.gridLayout_6.addLayout(self.gridLayout, 0, 0, 1, 4)


        self.gridLayout_9.addWidget(self.groupBox, 0, 0, 3, 1)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.groupBox_2 = QGroupBox(self.centralwidget)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy1.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy1)
        self.groupBox_2.setMaximumSize(QSize(320, 16777215))
        self.gridLayout_2 = QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.tableView_image = QTableView(self.groupBox_2)
        self.tableView_image.setObjectName(u"tableView_image")

        self.gridLayout_2.addWidget(self.tableView_image, 0, 0, 1, 1)


        self.horizontalLayout.addWidget(self.groupBox_2)

        self.groupBox_3 = QGroupBox(self.centralwidget)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy)
        self.gridLayout_3 = QGridLayout(self.groupBox_3)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.widget_imgview = ImageView(self.groupBox_3)
        self.widget_imgview.setObjectName(u"widget_imgview")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(3)
        sizePolicy3.setHeightForWidth(self.widget_imgview.sizePolicy().hasHeightForWidth())
        self.widget_imgview.setSizePolicy(sizePolicy3)

        self.gridLayout_3.addWidget(self.widget_imgview, 0, 0, 1, 1)


        self.horizontalLayout.addWidget(self.groupBox_3)


        self.gridLayout_9.addLayout(self.horizontalLayout, 0, 1, 1, 1)

        self.groupBox_5 = QGroupBox(self.centralwidget)
        self.groupBox_5.setObjectName(u"groupBox_5")
        sizePolicy.setHeightForWidth(self.groupBox_5.sizePolicy().hasHeightForWidth())
        self.groupBox_5.setSizePolicy(sizePolicy)
        self.gridLayout_4 = QGridLayout(self.groupBox_5)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.widget_binhdl = GraphicsLayoutWidget(self.groupBox_5)
        self.widget_binhdl.setObjectName(u"widget_binhdl")
        sizePolicy3.setHeightForWidth(self.widget_binhdl.sizePolicy().hasHeightForWidth())
        self.widget_binhdl.setSizePolicy(sizePolicy3)

        self.gridLayout_4.addWidget(self.widget_binhdl, 0, 0, 1, 1)


        self.gridLayout_9.addWidget(self.groupBox_5, 1, 1, 1, 1)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.groupBox_4 = QGroupBox(self.centralwidget)
        self.groupBox_4.setObjectName(u"groupBox_4")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(1)
        sizePolicy4.setHeightForWidth(self.groupBox_4.sizePolicy().hasHeightForWidth())
        self.groupBox_4.setSizePolicy(sizePolicy4)
        self.groupBox_4.setMinimumSize(QSize(0, 300))
        self.gridLayout_8 = QGridLayout(self.groupBox_4)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.gridLayout_5 = QGridLayout()
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.widget_ptree = ParameterTree(self.groupBox_4)
        self.widget_ptree.setObjectName(u"widget_ptree")
        sizePolicy4.setHeightForWidth(self.widget_ptree.sizePolicy().hasHeightForWidth())
        self.widget_ptree.setSizePolicy(sizePolicy4)
        self.widget_ptree.setMinimumSize(QSize(100, 200))

        self.gridLayout_5.addWidget(self.widget_ptree, 0, 0, 1, 4)

        self.label_4 = QLabel(self.groupBox_4)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_5.addWidget(self.label_4, 1, 0, 1, 1)

        self.comboBox = QComboBox(self.groupBox_4)
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.setObjectName(u"comboBox")

        self.gridLayout_5.addWidget(self.comboBox, 1, 1, 1, 1)

        self.pushButton_4 = QPushButton(self.groupBox_4)
        self.pushButton_4.setObjectName(u"pushButton_4")

        self.gridLayout_5.addWidget(self.pushButton_4, 1, 2, 1, 1)

        self.pushButton_3 = QPushButton(self.groupBox_4)
        self.pushButton_3.setObjectName(u"pushButton_3")

        self.gridLayout_5.addWidget(self.pushButton_3, 1, 3, 1, 1)


        self.gridLayout_8.addLayout(self.gridLayout_5, 0, 0, 2, 1)


        self.horizontalLayout_2.addWidget(self.groupBox_4)

        self.groupBox_6 = QGroupBox(self.centralwidget)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.gridLayout_7 = QGridLayout(self.groupBox_6)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.pushButton_process = QPushButton(self.groupBox_6)
        self.pushButton_process.setObjectName(u"pushButton_process")

        self.gridLayout_7.addWidget(self.pushButton_process, 0, 2, 1, 1)

        self.checkBox_fit_pixel_size = QCheckBox(self.groupBox_6)
        self.checkBox_fit_pixel_size.setObjectName(u"checkBox_fit_pixel_size")
        self.checkBox_fit_pixel_size.setChecked(True)

        self.gridLayout_7.addWidget(self.checkBox_fit_pixel_size, 0, 0, 1, 1)

        self.pushButton = QPushButton(self.groupBox_6)
        self.pushButton.setObjectName(u"pushButton")

        self.gridLayout_7.addWidget(self.pushButton, 2, 0, 1, 3)

        self.checkBox_show_rawdata = QCheckBox(self.groupBox_6)
        self.checkBox_show_rawdata.setObjectName(u"checkBox_show_rawdata")

        self.gridLayout_7.addWidget(self.checkBox_show_rawdata, 0, 1, 1, 1)


        self.horizontalLayout_2.addWidget(self.groupBox_6)


        self.gridLayout_9.addLayout(self.horizontalLayout_2, 2, 1, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1127, 23))
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

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"RIXSviewer", None))
        self.actionLoad_Spec_file.setText(QCoreApplication.translate("MainWindow", u"Load Spec file", None))
        self.actionSet_Tif_folder.setText(QCoreApplication.translate("MainWindow", u"Set Tif folder", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Scans", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Select Index", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"TypeFilter", None))
        self.comboBox_2.setItemText(0, QCoreApplication.translate("MainWindow", u"None", None))
        self.comboBox_2.setItemText(1, QCoreApplication.translate("MainWindow", u"SpectrumScan", None))
        self.comboBox_2.setItemText(2, QCoreApplication.translate("MainWindow", u"SnapshopScan", None))

        self.label.setText(QCoreApplication.translate("MainWindow", u"SpecFile:", None))
        self.toolButton_load_specfile.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"TiffFolder:", None))
        self.toolButton_set_tifffolder.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Image List", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("MainWindow", u"2D Images", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("MainWindow", u"1D Binning", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Destination:", None))
        self.comboBox.setItemText(0, QCoreApplication.translate("MainWindow", u"File", None))
        self.comboBox.setItemText(1, QCoreApplication.translate("MainWindow", u"PV", None))

        self.pushButton_4.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.pushButton_3.setText(QCoreApplication.translate("MainWindow", u"Load", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("MainWindow", u"Process", None))
        self.pushButton_process.setText(QCoreApplication.translate("MainWindow", u"Process Binning", None))
        self.checkBox_fit_pixel_size.setText(QCoreApplication.translate("MainWindow", u"Fit DeltaD", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        self.checkBox_show_rawdata.setText(QCoreApplication.translate("MainWindow", u"Show RawData", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
    # retranslateUi

