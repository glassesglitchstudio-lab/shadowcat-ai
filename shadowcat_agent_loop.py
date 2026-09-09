"""Shadowcat Agent Loop - ReAct Cycle"""

import os, sys, json, time, re, logging, traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("ShadowcatAgentLoop")

MAX_LOOP_ITERATIONS = 10
MAX_TOOL_RETRIES = 2
DEFAULT_TIMEOUT = 30

# �������������������������������������������������������������
# SAB�TLER
