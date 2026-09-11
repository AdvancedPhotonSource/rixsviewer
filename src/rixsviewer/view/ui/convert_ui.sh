#!/bin/bash
# Copyright © UChicago Argonne LLC
# See LICENSE file for details
pyside6-uic rixsviewer.ui -o rixsviewer_ui.py
sed -i "1a\\
# Copyright © UChicago Argonne LLC\\
# See LICENSE file for details" rixsviewer_ui.py 
