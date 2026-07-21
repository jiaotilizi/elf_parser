"""
MIT License

Copyright (c) 2026 Tom Yang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging

logger = logging.getLogger(__name__)


def calculate_stack_usage_highest(
    stack_start: int,
    stack_end: int,
    stack_highest: int,
    stack_current: int = 0
) -> float:
    if stack_highest == 0 or stack_end == 0:
        return 0.0

    # 安全检查
    if stack_highest < stack_start or stack_highest > stack_end:
        logger.warning("Invalid highest_ptr: 0x%x not in [0x%x, 0x%x]", stack_highest, stack_start, stack_end)
        return 0.0
    
    used = stack_highest - stack_start
    total = stack_end - stack_start
    
    if total == 0:
        return 0.0
        
    return (used / total) * 100.0


def calculate_stack_usage(
    stack_start: int,
    stack_end: int,
    current_sp: int,
    stack_size: int = 0
) -> float:
    if not stack_start or not stack_end:
        return 0.0
    
    if stack_size <= 0:
        stack_size = abs(stack_start - stack_end)
    
    if stack_size <= 0:
        return 0.0
    
    if current_sp:
        used = abs(current_sp - min(stack_start, stack_end))
    else:
        return 0.0
    
    return used / stack_size * 100 if stack_size > 0 else 0.0