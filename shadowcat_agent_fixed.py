"""Shadowcat Agent - PC Automation"""

import os, sys, subprocess, webbrowser, time, json, re, datetime, threading, tempfile, ctypes
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

OBSDAN_OK = False
try:
    from obsidian_memory import get_obsidian_memory
    OBSDAN_OK = True
except mportError:
    pass

import os
import sys
import subprocess
import webbrowser
import time
import json
import re
import datetime
import threading
import tempfile
import ctypes
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Obsidian Snrsz Hafza
try:
    from obsidian_memory import get_obsidian_memory
    OBSDAN_OK = True
